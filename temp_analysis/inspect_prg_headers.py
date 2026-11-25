import os, struct, glob

roots = [
    "WORKSPACE_PROGRAM_MESIN/MESIN_10B/03_CONTOH_PRG_DARI_HMI",
    "WORKSPACE_PROGRAM_MESIN/MESIN_1A/03_CONTOH_PRG_DARI_HMI",
    "services/data/OT/BATCH",
    "services/data/compiled_prg",
    "open_orgatex/backend/data/OT/BATCH",
]
for r in roots:
    files = glob.glob(os.path.join(r, "**", "*.PRG"), recursive=True)
    print(f"== {r}: {len(files)} PRG")
    for f in files[:12]:
        d = open(f, "rb").read()
        if len(d) < 384:
            continue
        pno = struct.unpack_from("<H", d, 8)[0]
        name = d[10:31].split(b"\0")[0].decode("cp1252", "ignore").strip()
        steps = struct.unpack_from("<H", d, 33)[0]
        # look for other ascii in header (program code like PKO838)
        import re
        txt = [s.decode("latin1") for s in re.findall(rb"[A-Z0-9 ._-]{4,}", d[:384])]
        print(f"  {os.path.relpath(f, r)}: prog_no={pno} name='{name}' steps={steps} hdr_strings={txt[:6]}")
