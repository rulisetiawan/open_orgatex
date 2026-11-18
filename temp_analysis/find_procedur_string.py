with open(r'C:\Users\ruli_smm\Flashdisk\SC797CE\SecomCE_BackGround_4d.dll', 'rb') as f:
    data = f.read()

idx = 0
while True:
    idx = data.find(b'PROCEDUR', idx)
    if idx == -1: break
    print(f"PROCEDUR at {idx}:", data[max(0, idx-50):min(len(data), idx+100)])
    idx += len(b'PROCEDUR')

idx = 0
while True:
    idx = data.find(b'USERCONF', idx)
    if idx == -1: break
    print(f"USERCONF at {idx}:", data[max(0, idx-50):min(len(data), idx+100)])
    idx += len(b'USERCONF')
