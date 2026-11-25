import socket
import ftplib
import psycopg2
from concurrent.futures import ThreadPoolExecutor, as_completed

DB_URL = "postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow"

def test_machine_ftp(row):
    m_no, ip, port = row
    port = int(port) if port else 21
    # 1. Fast TCP port 21 reachability check
    try:
        with socket.create_connection((ip, port), timeout=0.6):
            pass
    except Exception:
        return (m_no, ip, port, "OFFLINE", "Port 21 tidak merespons / mesin mati")

    # 2. Single clean FTP anonymous login test (guaranteed quit + close)
    ftp = None
    try:
        ftp = ftplib.FTP(timeout=3.0)
        ftp.connect(ip, port)
        ftp.login("", "")
        return (m_no, ip, port, "OK", "Anonymous login OK")
    except Exception as e:
        err = str(e).strip()
        if "421" in err:
            status = "FAIL_421"
        elif "530" in err:
            status = "FAIL_530"
        else:
            status = "FAIL_OTHER"
        return (m_no, ip, port, status, err)
    finally:
        if ftp:
            try:
                ftp.quit()
            except Exception:
                pass
            try:
                ftp.close()
            except Exception:
                pass

def main():
    conn = psycopg2.connect(DB_URL, connect_timeout=5)
    cur = conn.cursor()
    cur.execute("""
        SELECT machine_no, ip_address, ftp_port
        FROM machines
        WHERE ip_address IS NOT NULL AND TRIM(ip_address) != ''
          AND ip_address NOT IN ('127.0.0.1', 'localhost', '0.0.0.0')
        ORDER BY machine_no
    """)
    machines = cur.fetchall()
    conn.close()

    print(f"Total mesin ber-IP di database: {len(machines)}")

    results = []
    # Deduplicate by IP so we never open >1 connection to the same IP
    seen_ips = {}
    unique_rows = []
    for m_no, ip, port in machines:
        ip_c = ip.strip()
        if ip_c not in seen_ips:
            seen_ips[ip_c] = [m_no]
            unique_rows.append((m_no, ip_c, port))
        else:
            seen_ips[ip_c].append(m_no)

    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = [ex.submit(test_machine_ftp, r) for r in unique_rows]
        for fut in as_completed(futs):
            results.append(fut.result())

    results.sort(key=lambda x: (x[3], x[0]))

    ok_list = [r for r in results if r[3] == "OK"]
    fail_list = [r for r in results if r[3].startswith("FAIL_")]
    off_list = [r for r in results if r[3] == "OFFLINE"]

    print(f"\nRINGKASAN: OK={len(ok_list)} | GAGAL_LOGIN={len(fail_list)} | OFFLINE={len(off_list)}")

    print("\n=== GAGAL LOGIN ANONYMOUS (Port 21 OPEN tapi ditolak/macet) ===")
    for m_no, ip, port, st, msg in fail_list:
        ms = ",".join(seen_ips[ip])
        print(f"  {ms:<10} | {ip:<15} | {st:<10} | {msg}")

    print("\n=== BERHASIL LOGIN ANONYMOUS ===")
    for m_no, ip, port, st, msg in ok_list:
        ms = ",".join(seen_ips[ip])
        print(f"  {ms:<10} | {ip:<15} | OK")

    print("\n=== OFFLINE / PORT 21 CLOSED ===")
    for m_no, ip, port, st, msg in off_list:
        ms = ",".join(seen_ips[ip])
        print(f"  {ms:<10} | {ip:<15} | OFFLINE")

if __name__ == "__main__":
    main()
