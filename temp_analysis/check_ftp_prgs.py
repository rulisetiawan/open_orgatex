import ftplib

HOST = "172.16.110.160"
ftp = ftplib.FTP(timeout=3.0)
ftp.connect(HOST, 21)
ftp.login()

for p in ["/Storage/SC777CE/Programs", "/sc777ce/Programs", "/Programs", "/Storage/SC777CE", "/"]:
    try:
        files = ftp.nlst(p)
        print(f"Path '{p}': {len(files)} files/folders")
        prgs = [f for f in files if f.upper().endswith(".PRG") or f.upper().endswith(".PMU")]
        if prgs:
            print("  PRG/PMU sample:", prgs[:10])
    except Exception as e:
        print(f"Path '{p}' error: {e}")

ftp.quit()
