import io
import ftplib
import struct
import re

HOST = "172.16.110.160"
ftp = ftplib.FTP(timeout=3.0)
ftp.connect(HOST, 21)
ftp.login()

bio = io.BytesIO()
ftp.retrbinary("RETR /Storage/SC777CE/Status/STATUS.ACT", bio.write)
bio.seek(0)
data = bio.read()
ftp.quit()

print(f"STATUS.ACT size: {len(data)}")

# Search for integers around 0x150 - 0x170
for off in range(0x140, 0x180, 2):
    val = struct.unpack_from("<H", data, off)[0]
    print(f"Offset 0x{off:03X} ({off}): {val} (0x{val:04X})")

# Let's inspect where step is stored in da-setex-collector or open_orgatex
