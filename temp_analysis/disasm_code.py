import struct

with open(r'C:\Users\ruli_smm\Flashdisk\SC797CE\SecomCE_BackGround_4d.dll', 'rb') as f:
    data = f.read()

# Let's check code around 0xd6400 .. 0xd6600
chunk = data[0xd6400:0xd6700]
print("Code around 0xd6400 (hex):")
print(chunk[:128].hex(' '))
