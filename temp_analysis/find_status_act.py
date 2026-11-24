import ftplib
import io

ftp = ftplib.FTP(timeout=5)
ftp.connect('172.16.110.160', 21)
ftp.login('', '')

for p in [
    "/Storage/sc777ce/STATUS/ALARM.ACT",
    "/Storage/sc777ce/STATUS/ALARMS.LOG"
]:
    bio = io.BytesIO()
    try:
        ftp.retrbinary(f"RETR {p}", bio.write, blocksize=1024)
        print(f"FOUND: {p} (bytes={len(bio.getvalue())})")
    except Exception as e:
        print(f"NOT FOUND: {p} ({e})")

ftp.close()
