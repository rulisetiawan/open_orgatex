import os
import io
import ftplib
import time

TARGETS = [
    ("3E", "172.16.120.103", False),
    ("5E", "172.16.120.105", False),
    ("8E", "172.16.120.108", False),
    ("2E", "172.16.120.102", True),
    ("4F", "172.16.120.154", True),
    ("9E", "172.16.120.109", True),
    ("1B", "172.16.110.151", False),
]

WANTED_FILES = {
    "TYPECONF.CNF",
    "CONFTEXT.CNF",
    "MACHCONF.CNF",
    "FNLEGEND.CNF",
    "TYPECONT.CNF",
    "USERCONF.CNF",
    "TYPEFORM.CNF",
    "CP14.AWL",
}

def fetch_one_machine(m_no, ip, is_797):
    out_dir = os.path.join("WORKSPACE_PROGRAM_MESIN", f"MESIN_{m_no}", "01_CONFIG_DARI_HMI")
    os.makedirs(out_dir, exist_ok=True)

    ftp = None
    try:
        ftp = ftplib.FTP(timeout=4.0)
        ftp.connect(ip, 21)
        ftp.login("", "")
        ftp.set_pasv(True)

        # Single session: try primary Config path, then alternate (in case a machine is 797CE)
        dir_candidates = (
            ["/Flashdisk/SC797CE/Config", "/Flashdisk/SC797CE/CONFIG", "/Storage/sc777ce/Config", "/Storage/SC777CE/Config"]
            if is_797 else
            ["/Storage/sc777ce/Config", "/Storage/SC777CE/Config", "/Flashdisk/SC797CE/Config", "/Flashdisk/SC797CE/CONFIG"]
        )

        found_dir = None
        for d in dir_candidates:
            try:
                ftp.cwd(d)
                found_dir = d
                break
            except Exception:
                continue

        if not found_dir:
            # Check root to report what folder exists
            try:
                ftp.cwd("/")
                root_items = ftp.nlst()
            except Exception:
                root_items = []
            return (m_no, ip, "NO_CONFIG_DIR", f"Root: {root_items[:10]}", [])

        files = ftp.nlst()
        downloaded = []
        for fn in files:
            base = os.path.basename(fn.replace("\\", "/"))
            if base.upper() in WANTED_FILES:
                bio = io.BytesIO()
                try:
                    ftp.retrbinary(f"RETR {base}", bio.write)
                    data = bio.getvalue()
                    if data:
                        with open(os.path.join(out_dir, base.upper()), "wb") as f_out:
                            f_out.write(data)
                        downloaded.append(f"{base.upper()} ({len(data)}B)")
                except Exception as e_dl:
                    downloaded.append(f"{base.upper()}:ERR({e_dl})")

        return (m_no, ip, "OK", found_dir, downloaded)
    except Exception as e:
        return (m_no, ip, "FTP_ERROR", str(e).strip(), [])
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
    for m_no, ip, is_797 in TARGETS:
        res = fetch_one_machine(m_no, ip, is_797)
        m, ip_s, st, info, dls = res
        print(f"{m:<4} | {ip_s:<15} | {st:<13} | {info}")
        if dls:
            print(f"     Downloaded ({len(dls)}): {', '.join(dls)}")
        time.sleep(0.5)

if __name__ == "__main__":
    main()
