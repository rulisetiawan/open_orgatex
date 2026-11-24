import ftplib

HOST = "172.16.110.160"
ftp = ftplib.FTP(timeout=5.0)
ftp.connect(HOST, 21)
ftp.login()

files = ftp.nlst("/Storage/SC777CE/Programs")
print("Files in /Storage/SC777CE/Programs:")
for f in sorted(files):
    print(" ", f)

ftp.quit()
