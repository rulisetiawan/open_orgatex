import ftplib

ftp = ftplib.FTP(timeout=5)
ftp.connect('172.16.110.160', 21)
ftp.login('', '')

for d in [
    "/Storage/sc777ce/STATUS",
    "/Storage/SC777CE/STATUS",
    "/Storage/sc777ce/status",
    "/Storage/SC777CE/Status"
]:
    try:
        ftp.cwd(d)
        print(f"SUCCESS cwd to: {d}")
    except Exception as e:
        print(f"FAILED cwd to: {d} ({e})")

ftp.close()
