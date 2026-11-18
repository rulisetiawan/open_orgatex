with open(r'C:\Users\ruli_smm\Flashdisk\SC797CE\Config\MACHCONF.CNF', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

print("=== MACHCONF.CNF ===")
print(text[:2000])
