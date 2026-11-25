"""
Verification test for Third-Party Batch Import API:
- POST /api/v1/thirdparty/batches/import (verify_api_key + import_batches)
- POST /api/BatchService/ImportBatches (OrgaTEX parity alias)
- Windows COLORREF 4-byte RGB validation & conversion
- ImportState == 4 (QUEUED + MachineQueue) vs ImportState != 4 (PLANNING)
- Duplicate (Dyelot, Redye) handling vs Redye increment
- Binary BATCHREF.REF Parameter1, 11, 15, 16, 17, 18, 20 & Note1 verification
"""

import os
import sys
import struct
import tempfile
from unittest.mock import patch

tmp_dir = tempfile.mkdtemp(prefix="otx_import_test_")
tmp_db = os.path.join(tmp_dir, "test_orgatex.db").replace("\\", "/")
os.environ["OFFLINE_MODE"] = "true"
os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db}"
os.environ["ORGATEX_API_KEY"] = "test-secret-key"

sys.path.insert(0, os.path.abspath("."))

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from open_orgatex.backend.routes import third_party_api, orgatex_exact_api, planning
from open_orgatex.backend.routes.third_party_api import (
    OrgaTexImportBatchItem,
    import_batches,
    verify_api_key
)
from open_orgatex.backend.routes.orgatex_exact_api import otx_import_batches
from open_orgatex.backend.services.db_sync_service import DBSyncService
from open_orgatex.backend.database import ensure_batch_header_columns
from open_orgatex.backend.models.schema_pg import Base, BatchHeader, MachineQueue, ProgramHeader
from open_orgatex.backend.utils.secom_codec import (
    create_batchref_binary,
    build_batchref_custom_params,
    colorref_to_hex
)

engine = create_engine(f"sqlite:///{tmp_db}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
ensure_batch_header_columns(engine, is_postgres=False)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

with TestingSessionLocal() as seed_db:
    seed_db.add(ProgramHeader(program_no=401, program_name="REACTIVE COTTON 60C", fabric_type="COTTON"))
    seed_db.commit()


def run_tests():
    # 1. COLORREF conversion sanity check
    assert colorref_to_hex(255) == "#FF0000", "Pure red COLORREF mismatch"
    assert colorref_to_hex(65280) == "#00FF00", "Pure green COLORREF mismatch"
    assert colorref_to_hex(16711680) == "#0000FF", "Pure blue COLORREF mismatch"
    assert colorref_to_hex(0x00800080) == "#800080", "Purple COLORREF mismatch"

    # 2. Auth dependency check
    try:
        verify_api_key(x_api_key=None, authorization=None)
        raise AssertionError("Expected 401 for missing API key")
    except HTTPException as exc:
        assert exc.status_code == 401
    assert verify_api_key(x_api_key="test-secret-key", authorization=None) is True

    sample_raw = [
        {
            "Dyelot": "DL-2026-001",
            "Customer": "PT. ARTA PERMAI",
            "Article": "CM 30S RIB",
            "ColourNo": "1650159",
            "ColourDescript": "UNGU TUA",
            "Color": 8388736,  # 0x00800080 -> #800080
            "Redye": 0,
            "Machine": "TD12",
            "ProcedureNo": "REACTIVE COTTON 60C",
            "Weight": 350.5,
            "ImportState": 4,
            "LiquorQuantity": 2103,
            "Note1": "LOT-001A,LOT-001B",
            "TypeOfProcedureNo": 1,
            "ProcessType1": 1,
            "ProcessType2": 1,
            "LiquorRatio": 6,
            "Length": 200,
            "Parameter11": 2,
            "Parameter15": 12.5,
            "Parameter16": 45.0,
            "Parameter17": 3.75,
            "Parameter18": 150.0,
            "Parameter20": 6
        },
        {
            "Dyelot": "DL-2026-002",
            "Customer": "PT. SINAR JAYA",
            "Article": "PE 24S",
            "ColourNo": "99001",
            "ColourDescript": "MERAH CABE",
            "Color": 255,  # 0x000000FF -> #FF0000
            "Redye": 0,
            "Machine": "TD12",
            "ProcedureNo": "0503",
            "Weight": 200,
            "ImportState": 1,  # Not 4 -> PLANNING
            "LiquorQuantity": 1200,
            "Note1": "LOT-002A",
            "TypeOfProcedureNo": 1,
            "ProcessType1": 1,
            "ProcessType2": 1,
            "LiquorRatio": 6,
            "Length": 200,
            "Parameter11": 2,
            "Parameter15": 8.0,
            "Parameter16": 30.0,
            "Parameter17": 1.2,
            "Parameter18": 80.0,
            "Parameter20": 6
        }
    ]

    # 3. Invalid COLORREF (bit 24..31 non-zero -> ValidationError)
    try:
        OrgaTexImportBatchItem(**dict(sample_raw[0], Color=0x010000FF))
        raise AssertionError("Expected ValidationError for invalid COLORREF")
    except ValidationError:
        pass

    # 4. Valid bulk array import via /api/v1/thirdparty/batches/import handler
    items = [OrgaTexImportBatchItem(**row) for row in sample_raw]
    with TestingSessionLocal() as db:
        body = import_batches(payload=items, db=db)

    assert body["status"] == "success"
    assert body["total_imported"] == 2
    assert body["total_failed"] == 0

    item0 = body["imported"][0]
    item1 = body["imported"][1]
    assert item0["program_no"] == 401, f"Expected resolved program_no 401, got {item0['program_no']}"
    assert item0["status"] == "QUEUED"
    assert item0["color_hex"] == "#800080"
    assert item0["liquor_quantity"] == 2103.0
    assert item1["program_no"] == 503
    assert item1["status"] == "PLANNING"
    assert item1["color_hex"] == "#FF0000"

    # 5. Verify DB rows & MachineQueue (only ImportState=4 in MachineQueue)
    with TestingSessionLocal() as db:
        bh0 = db.query(BatchHeader).filter(BatchHeader.batch_no == "DL-2026-001").first()
        assert bh0 is not None
        assert bh0.color_rgb == 8388736
        assert bh0.note1 == "LOT-001A,LOT-001B"
        assert float(bh0.fabric_length) == 200.0

        mq_all = db.query(MachineQueue).all()
        assert len(mq_all) == 1 and mq_all[0].batch_no == "DL-2026-001"

        # 6. Verify BATCHREF.REF binary packing for Parameter1, 11, 15..18, 20 & Note1
        c_params = build_batchref_custom_params(float(bh0.fabric_weight_kg), bh0.parameters_json)
        bref = create_batchref_binary(
            reference_no=bh0.batch_ref_no,
            machine_no=bh0.machine_no,
            batch_no=bh0.batch_no,
            program_no=bh0.program_no,
            customer=bh0.customer,
            article=bh0.article,
            color_code=bh0.color_code,
            color_name=bh0.color_name,
            fabric_weight=float(bh0.fabric_weight_kg),
            custom_texts={8: bh0.note1},
            custom_params=c_params
        )
        assert len(bref) == 762
        p1 = struct.unpack_from("<f", bref, 448 + 0 * 4)[0]
        p11 = struct.unpack_from("<f", bref, 448 + 10 * 4)[0]
        p15 = struct.unpack_from("<f", bref, 448 + 14 * 4)[0]
        p16 = struct.unpack_from("<f", bref, 448 + 15 * 4)[0]
        p17 = struct.unpack_from("<f", bref, 448 + 16 * 4)[0]
        p18 = struct.unpack_from("<f", bref, 448 + 17 * 4)[0]
        p20 = struct.unpack_from("<f", bref, 448 + 19 * 4)[0]
        assert abs(p1 - 350.5) < 1e-3
        assert abs(p11 - 2.0) < 1e-3
        assert abs(p15 - 12.5) < 1e-3
        assert abs(p16 - 45.0) < 1e-3
        assert abs(p17 - 3.75) < 1e-3
        assert abs(p18 - 150.0) < 1e-3
        assert abs(p20 - 6.0) < 1e-3

        slot8_txt = bref[28 + 21 * 7 : 28 + 21 * 8].split(b"\0", 1)[0].decode("cp1252")
        assert slot8_txt == "LOT-001A,LOT-001B"

    # 7. Duplicate (Dyelot, Redye=0) rejected, while Redye=1 allowed via OrgaTEX alias handler
    dup_and_redye = [
        OrgaTexImportBatchItem(**sample_raw[0]),
        OrgaTexImportBatchItem(**dict(sample_raw[0], Redye=1))
    ]
    with TestingSessionLocal() as db:
        alias_body = otx_import_batches(payload=dup_and_redye, db=db)
    assert alias_body["status"] == "partial_success"
    assert alias_body["total_imported"] == 1
    assert alias_body["total_failed"] == 1
    assert alias_body["imported"][0]["redye"] == 1

    print(">>> ALL BATCH IMPORT API & BATCHREF.REF BINARY TESTS PASSED 100%! <<<")


if __name__ == "__main__":
    with patch.object(DBSyncService, "mirror_batch_to_sqlite", return_value=None), \
         patch.object(planning, "_sync_planning_json", return_value=None):
        run_tests()
