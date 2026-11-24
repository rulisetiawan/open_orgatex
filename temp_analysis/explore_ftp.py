import ftplib

ftp = ftplib.FTP(timeout=5)
ftp.connect('172.16.110.160', 21)
ftp.login('', '')
print("Connected to FTP 172.16.110.160!")

def list_dir(path):
    print(f"\n--- Listing {path} ---")
    try:
        ftp.cwd(path)
        lines = []
        ftp.dir(lines.append)
        for l in lines[:20]:
            print(l)
    except Exception as e:
        print(f"Error listing {path}: {e}")

list_dir('/')
list_dir('/Flashdisk')
list_dir('/Flashdisk/SC797CE')
list_dir('/Flashdisk/SC797CE/BATCH')

ftp.quit()
