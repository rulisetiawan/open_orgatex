import os, glob

for dll in glob.glob(r'C:\Users\ruli_smm\Flashdisk\SC797CE\*.dll') + [r'C:\Users\ruli_smm\Flashdisk\SC797CE\SC797CE.EXE']:
    try:
        with open(dll, 'rb') as f:
            data = f.read()
            idx = 0
            while True:
                idx = data.find(b'Check_User_Config', idx)
                if idx == -1: break
                context = data[max(0, idx-200):min(len(data), idx+300)]
                print(f"Found in {os.path.basename(dll)} at offset {idx}:")
                # print readable strings around here
                chars = "".join([chr(c) if 32 <= c <= 126 else " " for c in context])
                print("  ", chars)
                idx += len(b'Check_User_Config')
    except Exception as e:
        print(f"Error reading {dll}: {e}")
