import ftplib

ftp = ftplib.FTP(timeout=5)
ftp.connect('172.16.110.160', 21)
ftp.login('', '')

def list_dir(path):
    print(f"\n--- Listing {path} ---")
    try:
        ftp.cwd(path)
        lines = []
        ftp.dir(lines.append)
        for l in lines[:30]:
            print(l)
    except Exception as e:
        print(f"Error listing {path}: {e}")

list_dir('/Network/F')
list_dir('/Network/F/OT')
list_dir('/Network/F/OT/10B')
list_dir('/Network/F/OT/BATCH')

ftp.quit()
