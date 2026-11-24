import socket
import struct
import ftplib
import io
import json

HOST = "172.16.110.160"
PORT = 50000

print("=== 1. CHECK LIVE TCP CONTROLLER 10B (172.16.110.160) ===")
# Query TCP Service 11 Object 1025 (IW)
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3.0)
    s.connect((HOST, PORT))
    
    payload = struct.pack('<HH', 1, 50)
    header = bytearray(20)
    struct.pack_into('<H', header, 0, 2)
    struct.pack_into('<H', header, 2, len(payload) + 16)
    struct.pack_into('<H', header, 9, 1)
    header[14] = 1
    header[15] = 11
    struct.pack_into('<H', header, 16, 1025)
    struct.pack_into('<H', header, 18, len(payload))
    req = (header + payload).ljust(516, b'\x00')
    s.sendall(req)
    resp = s.recv(516)
    s.close()
    
    if len(resp) >= 20 and resp[14] == 2:
        words = [struct.unpack_from('<H', resp, 20 + i*2)[0] for i in range(50)]
        print(f"TCP IW1 (Temp PV raw): {words[0]} -> {words[0]/66.6667:.1f} C")
        print(f"TCP IW2 (Time raw): {words[1]}")
        print(f"TCP IW10 (Temp SV raw): {words[9]} -> {words[9]/66.66:.1f} C")
except Exception as e:
    print(f"TCP Error: {e}")

print("\n=== 2. CHECK FTP STATUS.ACT ON CONTROLLER ===")
try:
    ftp = ftplib.FTP(timeout=3.0)
    ftp.connect(HOST, 21)
    ftp.login()
    
    bio = io.BytesIO()
    # Try different paths for STATUS.ACT
    for p in ["STATUS.ACT", "/Storage/SC777CE/Status/STATUS.ACT", "/sc777ce/STATUS.ACT", "/STATUS.ACT"]:
        try:
            bio = io.BytesIO()
            ftp.retrbinary(f"RETR {p}", bio.write)
            bio.seek(0)
            data = bio.read()
            print(f"Read {p}: {len(data)} bytes")
            # Parse STATUS.ACT
            # Format: PRG: 4 bytes, Step: 2 bytes, Batch: 8 bytes, etc.
            print("Hex dump (first 64 bytes):", data[:64].hex())
            break
        except Exception:
            continue
    ftp.quit()
except Exception as e:
    print(f"FTP Error: {e}")

print("\n=== 3. CHECK DATABASE pt_smm_scada (192.168.100.30:5433) ===")
try:
    import psycopg2
    conn = psycopg2.connect("postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada")
    cur = conn.cursor()
    cur.execute("SELECT active_batch_code, active_step_no, state, program_metadata, updated_at FROM asset_snapshot WHERE asset_id = 'JF-LB-10'")
    row = cur.fetchone()
    if row:
        print(f"asset_snapshot: Batch={row[0]}, Step={row[1]}, State={row[2]}, UpdatedAt={row[4]}")
        prog = row[3]
        if prog:
            steps = prog.get("steps", [])
            print(f"Program metadata: Total steps={len(steps)}, ProgramName={prog.get('name')}")
            if steps and len(steps) >= row[1]:
                curr = steps[row[1] - 1] if row[1] > 0 else None
                print(f"Current step in snapshot program: {curr}")
    conn.close()
except Exception as e:
    print(f"DB Error: {e}")
