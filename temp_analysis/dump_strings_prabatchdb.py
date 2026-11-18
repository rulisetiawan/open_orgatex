with open(r'C:\Users\ruli_smm\Flashdisk\SC797CE\SecomCE_BackGround_4d.dll', 'rb') as f:
    data = f.read()

idx = 2001500
end = 2004000
chunk = data[idx:end]
s = []
cur = ""
for b in chunk:
    if 32 <= b <= 126:
        cur += chr(b)
    else:
        if len(cur) >= 3:
            s.append(cur)
        cur = ""

for item in s:
    print(item)
