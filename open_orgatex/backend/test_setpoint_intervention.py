"""
Unit and Integration Test for Setpoint Acquisition, Message Broker, and Operator Intervention Detection.
Runs with mocked TCP responses to verify protocol frames, message broker, differential comparison, and DB persistence.
"""

import sys
import os
import asyncio
import struct
from unittest.mock import patch

# Force SQLite for local testing
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.abspath("open_orgatex/backend/data/orgatex_local.db").replace("\\", "/")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from open_orgatex.backend.services.event_broker import broker, EventMessage
from open_orgatex.backend.services.setex_tcp_client import SetexTcpClient
from open_orgatex.backend.services.intervention_service import InterventionService
from open_orgatex.backend.database import init_db, SessionLocal
from open_orgatex.backend.models.schema_pg import OperatorIntervention

def make_mock_set_response(temp_sp_raw=980, time_sp=45, grad_sp=25, pump_sp=90):
    """Builds a valid 516-byte response for Object 1009 block read."""
    frame = bytearray(516)
    struct.pack_into('<HH', frame, 0, 2, 16 + 40)
    frame[14] = 2   # Response type DATA
    frame[15] = 11  # Service SV_READ_BLOCK
    struct.pack_into('<HH', frame, 16, 1009, 40)  # Obj 1009, 40 bytes (20 words)

    words = [temp_sp_raw, time_sp, grad_sp, pump_sp] + [0] * 16
    for i, w in enumerate(words):
        struct.pack_into('<H', frame, 20 + i * 2, w)
    return bytes(frame)

def make_mock_iw_response():
    """Builds a valid 516-byte response for Object 1025 block read."""
    frame = bytearray(516)
    struct.pack_into('<HH', frame, 0, 2, 16 + 20)
    frame[14] = 2
    frame[15] = 11
    struct.pack_into('<HH', frame, 16, 1025, 20)
    for i in range(10):
        struct.pack_into('<H', frame, 20 + i * 2, 100 + i)
    return bytes(frame)

def mock_exchange(host, port, req, timeout=3.0):
    obj = struct.unpack_from('<H', req, 16)[0]
    if obj == 1009:
        return make_mock_set_response(temp_sp_raw=980, time_sp=45, grad_sp=25, pump_sp=90)
    elif obj == 1025:
        return make_mock_iw_response()
    elif obj == 6:
        # Function 141 response (64 bytes)
        frame = bytearray(516)
        struct.pack_into('<HH', frame, 0, 2, 16 + 64)
        frame[14] = 2
        frame[15] = 1
        struct.pack_into('<HH', frame, 16, 6, 64)
        frame[20] = 0  # Line 0
        struct.pack_into('<H', frame, 21, 141)  # Func 141
        struct.pack_into('<f', frame, 25, 98.0) # P1 Suhu
        struct.pack_into('<f', frame, 33, 2.5)  # P2 Gradien
        struct.pack_into('<f', frame, 41, 45.0) # P3 Waktu
        return bytes(frame)
    else:
        raise ConnectionError(f"Mock unhandled obj {obj}")

async def run_tests():
    print("=== 1. Initialize Local Database ===")
    init_db()
    print("  [SUCCESS] Database initialized.")

    print("\n=== 2. Testing Event Broker ===")
    await broker.start()

    received_events = []
    def on_intervention(msg: EventMessage):
        print(f"  [Subscriber received] Topic: {msg.topic}, Machine: {msg.data.get('machine_no')}")
        received_events.append(msg)

    broker.subscribe("machine.intervention", on_intervention)

    print("\n=== 3. Testing SetexTcpClient Protocol Frames ===")
    f_iw = SetexTcpClient.build_read_frame(1, 1025, 10, 1)
    assert len(f_iw) == 516
    assert f_iw[15] == 1
    print("  [SUCCESS] IW (1025) SV_READ frame verified (516 bytes).")

    f_set = SetexTcpClient.build_read_frame(11, 1009, 1, 20)
    assert len(f_set) == 516
    assert f_set[15] == 11
    print("  [SUCCESS] SET (1009) SV_READ_BLOCK frame verified (516 bytes).")

    # Safety check
    res_blocked = SetexTcpClient.write_setpoint("127.0.0.1", 50000, 1009, 1, 980)
    assert res_blocked["status"] == "blocked"
    print("  [SUCCESS] Safe write guard verified (Write mode blocked by default).")

    print("\n=== 4. Testing End-to-End Operator Intervention Workflow ===")
    # Step A: Establish Initial Baseline (e.g. Recipe initial values)
    InterventionService.set_baseline("TD12", {
        "Target Temperature": 90.0,
        "Holding Time": 30.0,
        "Temperature Gradient": 2.5,
        "Pump Speed": 85.0
    })
    print(f"  [Initial Baseline Set for TD12] {InterventionService.get_baseline('TD12')}")

    # Register listener now with mock exchange active
    with patch.object(SetexTcpClient, '_exchange', side_effect=mock_exchange):
        InterventionService.register_listener()

        # Trigger an intervention event via the Message Broker
        broker.publish_sync("machine.intervention", {
            "machine_no": "TD12",
            "trigger_source": "ALARMS_LOG",
            "alarm_code": 256,
            "alarm_text": "Operator Intervention Request",
            "notes": "Operator pressed intervention button on HMI"
        })

        # Wait briefly for broker async dispatch
        await asyncio.sleep(0.3)

        assert len(received_events) >= 1
        print("  [Broker Delivery Verified] Intervention message delivered via broker.")

        # Trigger evaluate_and_record directly to inspect changes
        changes = InterventionService.evaluate_and_record(
            machine_no="TD12",
            trigger_source="ALARMS_LOG",
            alarm_code=256,
            notes="Operator increased temp to 98C and holding time to 45m"
        )

        print(f"\n=== 5. Verification of Detected Parameter Changes ===")
        print(f"  Total detected changes: {len(changes)}")
        for ch in changes:
            print(f"  --> Parameter: '{ch['parameter_name']}' | "
                  f"Before: {ch['value_before']} {ch['unit']} | "
                  f"After: {ch['value_after']} {ch['unit']} | "
                  f"Delta: {ch['delta']:+}")

        # Assertions
        temp_ch = next((c for c in changes if c["parameter_name"] == "Target Temperature"), None)
        assert temp_ch is not None, "Target Temperature change must be detected"
        assert temp_ch["value_before"] == 90.0
        assert temp_ch["value_after"] == 98.0
        assert temp_ch["delta"] == 8.0

        time_ch = next((c for c in changes if c["parameter_name"] == "Holding Time"), None)
        assert time_ch is not None, "Holding Time change must be detected"
        assert time_ch["value_before"] == 30.0
        assert time_ch["value_after"] == 45.0
        assert time_ch["delta"] == 15.0

    print("\n=== 6. Verification of Database Persistence ===")
    db = SessionLocal()
    records = db.query(OperatorIntervention).filter(
        OperatorIntervention.machine_no == "TD12"
    ).order_by(OperatorIntervention.id.desc()).all()

    assert len(records) >= 2, "Database should contain at least 2 intervention records"
    print(f"  [SUCCESS] {len(records)} records found in PostgreSQL / SQLite operator_interventions table:")
    for r in records[:5]:
        print(f"    - ID {r.id}: [{r.trigger_source}] {r.parameter_name} "
              f"changed from {r.value_before} to {r.value_after} {r.unit} (Delta {r.delta:+})")
    db.close()

    await broker.stop()
    print("\n>>> ALL TESTS COMPLETED & VERIFIED 100% SUCCESSFULLY! <<<")

if __name__ == "__main__":
    asyncio.run(run_tests())
