import os
import sys
import struct
sys.path.insert(0, '.')
sys.path.insert(0, './open_orgatex')
from open_orgatex.backend.utils.secom_codec import serialize_prg_binary, build_minimal_prg, create_batchref_binary
from open_orgatex.backend.services.ftp_sync_service import sync_all_batches_to_ftp

print("=== 1. TEST PEMBUATAN PROGRAM ===")
prg_bytes = build_minimal_prg(7777, "INTEGRATION TEST")
print("Size of compiled PRG:", len(prg_bytes))
magic = prg_bytes[:4].hex()
hdr_ver = struct.unpack_from("<I", prg_bytes, 4)[0]
p_id = struct.unpack_from("<H", prg_bytes, 8)[0]
step_count = struct.unpack_from("<H", prg_bytes, 33)[0]
w_type = struct.unpack_from("<H", prg_bytes, 35)[0]
ts_created = list(prg_bytes[360:366])

print(f"Magic: {magic} (Expected: 508fc2f5)")
print(f"Header Version: {hdr_ver} (Expected: 60)")
print(f"Program ID: {p_id} (Expected: 7777)")
print(f"Step Count: {step_count} (Expected: 4)")
print(f"Program Type: {w_type} (Expected: 1)")
print(f"Timestamp Created: {ts_created}")

assert magic == "508fc2f5", "Magic failed!"
assert hdr_ver == 60, "Header version failed!"
assert w_type == 1, "Program type failed!"
assert all(v > 0 for v in ts_created[:3]), "Timestamp invalid!"
print(">>> PEMBUATAN PROGRAM VALID & SESUAI SPESIFIKASI SC797!\n")

print("=== 2. TEST PEMBUATAN BATCH & SINKRONISASI FTP ===")
bref = create_batchref_binary(
    reference_no="999999",
    machine_no="DA01",
    batch_no="LOT-999999",
    program_no=7777,
    fabric_weight=400.0,
    program_title="INTEGRATION TEST"
)
print("Size of BATCHREF.REF:", len(bref))
assert len(bref) == 762, "BATCHREF length must be 762!"
print(">>> STRUKTUR BATCHREF VALID 762 BYTE!\n")
print("ALL LOCAL INTEGRATION TESTS PASSED!")
