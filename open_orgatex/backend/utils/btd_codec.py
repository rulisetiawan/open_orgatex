"""
Pure Python Btrieve QUEUE.BTD Decoder & Builder for SETEX Controller HMI
Tidak memerlukan QueueTool.exe maupun BtrieveInterface.dll sehingga
berjalan lancar di Linux (Docker) dan Windows host secara cross-platform.
"""

import os
import re
import struct
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("btd_codec")

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))
QUEUE_50_TPL = os.path.join(DATA_DIR, "QUEUE_50.template.BTD")
QUEUE_STD_TPL = os.path.join(DATA_DIR, "QUEUE.template.BTD")


def read_queue_btd(b: bytes) -> List[Dict[str, Any]]:
    """
    Membaca seluruh antrean batch dari berkas biner QUEUE.BTD (Btrieve 6.x)
    secara murni di Python tanpa ketergantungan QueueTool.
    """
    if not b or len(b) < 1024:
        return []

    try:
        page_size = struct.unpack_from("<H", b, 8)[0]
        rec_len = struct.unpack_from("<H", b, 22)[0]
        active_count = struct.unpack_from("<I", b, 0x1a)[0] // 65536
    except Exception:
        return []

    if page_size != 1024 or rec_len != 759:
        return []

    records = []
    total_pages = len(b) // page_size

    def _txt(chunk: bytes) -> str:
        return chunk.split(b"\0", 1)[0].decode("cp1252", errors="replace").strip()

    for page in range(1, total_pages):
        off = page * page_size + 6
        r = b[off:off + rec_len]
        if len(r) == rec_len and re.fullmatch(rb"\d{6}\x00", r[1:8]):
            ref = r[1:7].decode("ascii")
            prog_no = struct.unpack_from("<H", r, 26)[0]
            pos = struct.unpack_from("<H", r, 757)[0]
            batch_no = _txt(r[28:49])
            prog_title = _txt(r[427:448])
            customer = _txt(r[49:70])
            article = _txt(r[70:91])
            color_code = _txt(r[175:196])
            color_name = _txt(r[196:217])
            mach = _txt(r[748:753])

            weight = 0.0
            try:
                weight = struct.unpack_from("<f", r, 448)[0]
            except Exception:
                pass

            records.append({
                "page": page,
                "position": pos,
                "batch_ref_no": ref,
                "ref": ref,
                "batch_no": batch_no,
                "program_no": prog_no,
                "recipe_name": prog_title or f"Prog {prog_no}",
                "customer": customer,
                "article": article,
                "color_code": color_code,
                "color_name": color_name,
                "fabric_weight_kg": weight,
                "machine_no": mach,
                "raw_record": bytes(r)
            })

    records.sort(key=lambda x: x["position"])

    if active_count > 0 and len(records) > active_count:
        records = [r for r in records if r["position"] <= active_count]
        records = records[:active_count]

    return records


def inspect_btd_refs(b: bytes) -> List[str]:
    """
    Mengembalikan daftar nomor referensi 6 digit berurutan dari QUEUE.BTD.
    Drop-in replacement 100% Python murni untuk versi lama yang memanggil QueueTool.exe.
    """
    recs = read_queue_btd(b)
    return [r["ref"] for r in recs]


def build_queue_btd_python(
    records_759: List[bytes],
    machine_no: str = "DA01",
    base_btd: Optional[bytes] = None
) -> Optional[bytes]:
    """
    Mengompilasi berkas biner QUEUE.BTD (Btrieve 6.x) secara murni di Python
    dengan memanfaatkan template Btrieve yang valid.
    """
    N = len(records_759)
    template_data = None

    if base_btd and len(base_btd) >= (7 + N) * 1024:
        template_data = base_btd
    elif os.path.exists(QUEUE_50_TPL):
        with open(QUEUE_50_TPL, "rb") as f:
            template_data = f.read()
    elif os.path.exists(QUEUE_STD_TPL):
        with open(QUEUE_STD_TPL, "rb") as f:
            template_data = f.read()

    if not template_data:
        logger.error("Template QUEUE.BTD tidak ditemukan!")
        return None

    b = bytearray(template_data)
    page_size = 1024
    total_pages = len(b) // page_size

    # Peta halaman data dan placeholder referensi per posisi
    pos_to_page = {}
    for p in range(1, total_pages):
        chunk = b[p * page_size:(p + 1) * page_size]
        r = chunk[6:6 + 759]
        if r[1:7].isdigit():
            pos = struct.unpack_from("<H", r, 757)[0]
            pos_to_page[pos] = (p, p * page_size + 6, r[1:7].decode("ascii"))

    # 1. Bersihkan slot yang tidak terpakai (pos > N)
    for pos, (p_num, rec_off, ph_ref) in pos_to_page.items():
        if pos > N:
            b[rec_off:rec_off + 759] = b"\0" * 759

    # 2. Tulis setiap record baru ke halaman posisinya dan update referensi
    for idx, rec in enumerate(records_759, start=1):
        if idx not in pos_to_page:
            break

        p_num, rec_off, ph_ref = pos_to_page[idx]
        q_rec = bytearray(rec[:759])
        struct.pack_into("<HH", q_rec, 755, 0, idx)

        new_ref = q_rec[1:7].decode("ascii", errors="replace")

        # Tulis 759 bytes ke halaman data
        b[rec_off:rec_off + 759] = q_rec

        # Ganti placeholder ref lama dengan ref baru di seluruh berkas
        b = bytearray(bytes(b).replace(ph_ref.encode("ascii"), new_ref.encode("ascii")))

    # 3. Update hitungan record aktif di Page 0 dan Index Pages
    struct.pack_into("<I", b, 0x1a, N * 65536)
    if len(b) >= 1024 + 8:
        struct.pack_into("<H", b, 1024 + 6, N)
    if len(b) >= 2048 + 8:
        struct.pack_into("<H", b, 2048 + 6, N)
    if len(b) >= 5120 + 8:
        struct.pack_into("<H", b, 5120 + 6, N)

    return bytes(b)
