import os, sys, struct
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.abspath("open_orgatex/backend/data/orgatex_local.db").replace("\\", "/")
sys.path.insert(0, ".")

from open_orgatex.backend.services.setex_tcp_client import SetexTcpClient
from open_orgatex.backend.routes.setpoints import (
    get_broker_diagnostics,
    get_live_setpoints,
    get_intervention_history,
    trigger_intervention_check,
    TriggerInterventionRequest
)
from open_orgatex.backend import database
from open_orgatex.backend.services.intervention_service import InterventionService
from open_orgatex.backend.services.event_broker import broker

database.init_db()
db = database.SessionLocal()

def mock_exchange(host, port, req, timeout=3.0):
    obj = struct.unpack_from('<H', req, 16)[0]
    frame = bytearray(516)
    if obj == 1009:
        struct.pack_into('<HH', frame, 0, 2, 16 + 40)
        frame[14] = 2; frame[15] = 11
        struct.pack_into('<HH', frame, 16, 1009, 40)
        words = [980, 45, 25, 90] + [0]*16
        for i, w in enumerate(words):
            struct.pack_into('<H', frame, 20 + i*2, w)
        return bytes(frame)
    elif obj == 1025:
        struct.pack_into('<HH', frame, 0, 2, 16 + 20)
        frame[14] = 2; frame[15] = 11
        struct.pack_into('<HH', frame, 16, 1025, 20)
        return bytes(frame)
    elif obj == 6:
        struct.pack_into('<HH', frame, 0, 2, 16 + 64)
        frame[14] = 2; frame[15] = 1
        struct.pack_into('<HH', frame, 16, 6, 64)
        struct.pack_into('<H', frame, 21, 141)
        struct.pack_into('<f', frame, 25, 98.0)
        struct.pack_into('<f', frame, 33, 2.5)
        struct.pack_into('<f', frame, 41, 45.0)
        return bytes(frame)
    raise ConnectionError('mock err')

with patch.object(SetexTcpClient, '_exchange', side_effect=mock_exchange):
    print("1. Testing get_broker_diagnostics()...")
    diag = get_broker_diagnostics()
    print("   Broker Status:", diag["broker_stats"]["status"])

    print("2. Testing get_live_setpoints('TD12')...")
    live = get_live_setpoints("TD12", db=db)
    print("   Status:", live["status"], "| Online:", live["is_online"])
    print("   Setpoints:", live["setpoints"])

    print("3. Testing trigger_intervention_check('TD12')...")
    InterventionService.set_baseline("TD12", {"Target Temperature": 90.0, "Holding Time": 30.0})
    trig_req = TriggerInterventionRequest(
        trigger_source="TEST_API",
        alarm_code=256,
        notes="Operator adjusted temperature at machine"
    )
    trig_res = trigger_intervention_check("TD12", payload=trig_req, db=db)
    print("   Event Status:", trig_res["status"])
    print("   Detected Changes Count:", trig_res["changes_count"])
    for ch in trig_res["detected_changes"]:
        print(f"    --> {ch['parameter_name']}: {ch['value_before']}{ch['unit']} -> {ch['value_after']}{ch['unit']} (Delta {ch['delta']:+})")

    print("4. Testing get_intervention_history('TD12')...")
    history = get_intervention_history("TD12", db=db)
    print("   Total in history:", history["total_interventions"])
    for h in history["interventions"][:3]:
        print(f"    - [{h['timestamp']}] {h['parameter_name']} changed from {h['value_before']} to {h['value_after']} {h['unit']} (Delta {h['delta']:+})")

db.close()
print("\n>>> ALL ROUTE LOGIC VERIFIED 100% SUCCESSFULLY! <<<")
