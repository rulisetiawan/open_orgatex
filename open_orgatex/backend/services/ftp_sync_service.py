"""
Sinkronisasi Batch dari Database ke FTP Controller OrgaTEX (192.168.1.95)
Menjadikan setiap batch_ref_no sebagai folder baru di:
ftp://192.168.1.95/Network/F/OT/BATCH/<batch_ref_no>/
dengan isi:
- BATCHREF.REF (762 byte Secom biner)
- M_<prog_no:04d>.PRG (program celup biner)

Serta mencadangkan ke lokal di:
open_orgatex/backend/data/OT/BATCH/<batch_ref_no>/
"""

import os
import io
import struct
import ftplib
import logging
from typing import List, Dict, Any

from ..database import get_db
from ..models.schema_pg import BatchHeader, MachineQueue
from ..utils.secom_codec import create_batchref_binary, build_minimal_prg, generate_queue_btd
from ..routes.programs import get_compiled_prg_bytes

logger = logging.getLogger("sync_ftp_batches")

FTP_HOST = "192.168.1.95"
FTP_PORT = 21
FTP_BASE_BATCH_DIR = "/Network/F/OT/BATCH"
LOCAL_DATA_DIR = os.path.abspath("./open_orgatex/backend/data")
LOCAL_BATCH_DIR = os.path.join(LOCAL_DATA_DIR, "OT", "BATCH")
USERCONF_TEMPLATE_SRC = os.path.abspath("./open_orgatex/backend/data/USERCONF.CNF")


def sync_userconf_to_ftp(ftp: Optional[ftplib.FTP]):
    """
    Sinkronisasi USERCONF.CNF (9,216 byte) ke FTP server Controller:
    - /Network/F/OT/PROCEDUR/100/USERCONF.CNF (wajib untuk PRABatchDB Check_User_Config)
    - /Network/F/OT/PROCEDUR/001..016/USERCONF.CNF
    - /Network/F/OT/CFG/USER/USERCONF.CNF
    Serta cermin lokal di open_orgatex/backend/data/OT/PROCEDUR/100/.
    Mencegah error 'Invalid userconf file' pada HMI.
    """
    userconf_bytes = None
    candidates = [
        USERCONF_TEMPLATE_SRC,
        os.path.abspath("./WORKSPACE_PROGRAM_MESIN/MESIN_DA01/01_CONFIG_DARI_HMI/USERCONF.CNF"),
        r"C:\Users\ruli_smm\Flashdisk\SC797CE\Config\USERCONF.CNF"
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                with open(c, "rb") as f:
                    data = f.read()
                    if len(data) >= 512:
                        userconf_bytes = data
                        break
            except Exception:
                pass

    if not userconf_bytes:
        logger.warning("Template USERCONF.CNF tidak ditemukan. Melewati sinkronisasi USERCONF.")
        return

    # 1. Simpan cermin lokal
    for sub in ["100", "001", "002"]:
        local_pdir = os.path.join(LOCAL_DATA_DIR, "OT", "PROCEDUR", sub)
        os.makedirs(local_pdir, exist_ok=True)
        with open(os.path.join(local_pdir, "USERCONF.CNF"), "wb") as f_u:
            f_u.write(userconf_bytes)

    local_cfg_user = os.path.join(LOCAL_DATA_DIR, "OT", "CFG", "USER")
    os.makedirs(local_cfg_user, exist_ok=True)
    with open(os.path.join(local_cfg_user, "USERCONF.CNF"), "wb") as f_u:
        f_u.write(userconf_bytes)

    # 2. Upload ke FTP jika terhubung
    if not ftp:
        return

    target_dirs = [
        "/Network/F/OT/PROCEDUR/100",
        "/Network/F/OT/PROCEDUR/001",
        "/Network/F/OT/CFG/USER"
    ]

    for t_dir in target_dirs:
        try:
            parts = t_dir.strip("/").split("/")
            curr = ""
            for p in parts:
                curr += "/" + p
                try:
                    ftp.cwd(curr)
                except Exception:
                    try:
                        ftp.mkd(curr)
                    except Exception:
                        pass
            ftp.cwd(t_dir)
            ftp.storbinary("STOR USERCONF.CNF", io.BytesIO(userconf_bytes))
            logger.info(f"[SUKSES] USERCONF.CNF ({len(userconf_bytes)} byte) terunggah ke {t_dir}/USERCONF.CNF")
        except Exception as ue:
            logger.error(f"[GAGAL] Upload USERCONF.CNF ke {t_dir}: {ue}")


def sync_all_batches_to_ftp(ftp_host: str = FTP_HOST, ftp_port: int = FTP_PORT) -> List[Dict[str, Any]]:
    """
    Sinkronisasi seluruh batch dari database ke folder /Network/F/OT/BATCH/<ref>/
    dan susun QUEUE.BTD di /Network/F/OT/MACHINES/DA01/BATCHES/QUEUE.BTD (khusus DA01).
    """
    # 1. Ambil seluruh batch dari database
    batches = []
    for db in get_db():
        batches = db.query(BatchHeader).order_by(BatchHeader.id.asc()).all()
        break

    if not batches:
        logger.warning("Tidak ada batch yang ditemukan di database.")
        return []

    logger.info(f"Ditemukan {len(batches)} batch di database. Memulai sinkronisasi ke FTP {ftp_host}:{ftp_port}...")

    # 2. Koneksi ke FTP server
    ftp = None
    try:
        ftp = ftplib.FTP(timeout=10)
        ftp.connect(ftp_host, ftp_port)
        ftp.login()
        logger.info(f"Berhasil login ke FTP {ftp_host}")
        try:
            ftp.set_pasv(True)
        except Exception:
            pass

        # Pastikan direktori dasar /Network/F/OT/BATCH ada
        try:
            ftp.cwd(FTP_BASE_BATCH_DIR)
        except Exception:
            for part in ["/Network", "/Network/F", "/Network/F/OT", FTP_BASE_BATCH_DIR]:
                try:
                    ftp.mkd(part)
                except Exception:
                    pass
            ftp.cwd(FTP_BASE_BATCH_DIR)

        # Sinkronisasi USERCONF.CNF ke FTP untuk mencegah 'Invalid userconf file'
        sync_userconf_to_ftp(ftp)

    except Exception as e:
        logger.error(f"Gagal koneksi ke FTP {ftp_host}:{ftp_port}: {e}")
        ftp = None

    results = []
    synced_refs = set()

    # 3. Proses setiap batch
    for b in batches:
        ref_no = str(b.batch_ref_no).strip().zfill(6)
        prog_no = int(b.program_no or 1)
        prg_name = f"M_{prog_no:04d}.PRG"
        mach_no = str(b.machine_no or "DA01").strip().upper()
        batch_no = str(b.batch_no or f"LOT-{ref_no}").strip()
        recipe_title = str(b.recipe_name or f"Program {prog_no}")
        b_status = (b.status or "QUEUED").strip().upper()

        # Buat binary BATCHREF.REF (762 byte)
        batchref_bytes = create_batchref_binary(
            reference_no=ref_no,
            machine_no=mach_no,
            batch_no=batch_no,
            program_no=prog_no,
            recipe_no=b.recipe_name or "",
            customer=b.customer or "",
            article=b.article or "",
            color_code=b.color_code or "",
            color_name=b.color_name or "",
            fabric_weight=float(b.fabric_weight_kg or 350.0),
            program_title=recipe_title
        )

        # Ambil binary program M_xxxx.PRG
        prg_bytes = None
        try:
            prg_bytes = get_compiled_prg_bytes(prog_no)
        except Exception:
            pass
        if not prg_bytes or len(prg_bytes) < 65:
            prg_bytes = build_minimal_prg(prog_no, recipe_title)

        # 3A. Simpan ke mirror LOKAL: open_orgatex/backend/data/OT/BATCH/<ref_no>/
        local_target_folder = os.path.join(LOCAL_BATCH_DIR, ref_no)
        os.makedirs(local_target_folder, exist_ok=True)
        with open(os.path.join(local_target_folder, "BATCHREF.REF"), "wb") as f_ref:
            f_ref.write(batchref_bytes)
        with open(os.path.join(local_target_folder, prg_name), "wb") as f_prg:
            f_prg.write(prg_bytes)

        status_item = {
            "batch_ref_no": ref_no,
            "batch_no": batch_no,
            "machine_no": mach_no,
            "program_no": prog_no,
            "prg_file": prg_name,
            "local_path": local_target_folder,
            "ftp_path": f"{FTP_BASE_BATCH_DIR}/{ref_no}/",
            "ftp_synced": False
        }

        # 3B. Buat folder dan upload ke FTP Controller (192.168.1.95) - HANYA UNTUK MESIN DA01
        # Hanya upload jika bukan PLANNING
        if ftp and mach_no == "DA01" and b_status != "PLANNING":
            try:
                target_ftp_dir = f"{FTP_BASE_BATCH_DIR}/{ref_no}"
                try:
                    ftp.mkd(target_ftp_dir)
                except Exception:
                    pass  # Folder sudah ada

                ftp.cwd(target_ftp_dir)

                # Upload BATCHREF.REF
                ftp.storbinary("STOR BATCHREF.REF", io.BytesIO(batchref_bytes))

                # Upload M_xxxx.PRG
                ftp.storbinary(f"STOR {prg_name}", io.BytesIO(prg_bytes))

                status_item["ftp_synced"] = True
                synced_refs.add(ref_no)
                logger.info(f"[SUKSES] Folder FTP dibuat: {target_ftp_dir}/ -> [BATCHREF.REF, {prg_name}]")
            except Exception as fe:
                logger.error(f"[GAGAL] FTP upload {ref_no}: {fe}")
        elif ftp and mach_no != "DA01":
            logger.info(f"[MODE AMAN] Lewati penulisan FTP untuk batch {ref_no} mesin {mach_no} (hanya DA01 yang diizinkan menulis).")

        results.append(status_item)

    # 4. Sinkronisasi Antrean Mesin (QUEUE.BTD) ke FTP dan Lokal
    # Filter ketat: Pastikan batch yang masuk ke QUEUE.BTD terkonfirmasi memiliki file biner di FTP
    machine_batches = {}
    for b in batches:
        b_status = (b.status or "QUEUED").strip().upper()
        if b_status == "PLANNING":
            continue  # Jangan masukkan tahap PLANNING ke QUEUE.BTD
        m = str(b.machine_no or "DA01").strip().upper()
        ref_no = str(b.batch_ref_no).strip().zfill(6)
        
        # Jika terkoneksi FTP ke mesin DA01, hanya masukkan batch yang benar-benar berhasil terunggah
        if ftp and m == "DA01" and ref_no not in synced_refs:
            logger.warning(f"Batch {ref_no} dilewati dari QUEUE.BTD DA01 karena berkasnya belum terunggah ke FTP.")
            continue

        machine_batches.setdefault(m, []).append(b)

    logger.info(f"Memproses QUEUE.BTD untuk {len(machine_batches)} mesin...")
    for mach_code, m_list in machine_batches.items():
        # Pastikan antrean tercatat di MachineQueue database
        for db in get_db():
            for idx, b in enumerate(sorted(m_list, key=lambda x: (int(x.position or 1), str(x.batch_ref_no))), start=1):
                mq = db.query(MachineQueue).filter(
                    MachineQueue.machine_no == mach_code,
                    MachineQueue.batch_ref_no == b.batch_ref_no
                ).first()
                if not mq:
                    db.add(MachineQueue(
                        machine_no=mach_code,
                        batch_ref_no=b.batch_ref_no,
                        batch_no=b.batch_no,
                        program_no=b.program_no or 1,
                        recipe_name=b.recipe_name,
                        customer=b.customer,
                        article=b.article,
                        color_code=b.color_code,
                        color_name=b.color_name,
                        fabric_weight_kg=b.fabric_weight_kg,
                        liquor_ratio=b.liquor_ratio,
                        total_water_l=b.total_water_l,
                        position=idx,
                        status=b.status or "QUEUED"
                    ))
            db.commit()
            break

        # Susun 759-byte records
        q_records = []
        for idx, b in enumerate(sorted(m_list, key=lambda x: (int(x.position or 1), str(x.batch_ref_no))), start=1):
            ref_no = str(b.batch_ref_no).strip().zfill(6)
            prog_no = int(b.program_no or 1)
            bref = create_batchref_binary(
                reference_no=ref_no,
                machine_no=mach_code,
                batch_no=b.batch_no or f"LOT-{ref_no}",
                program_no=prog_no,
                recipe_no=b.recipe_name or "",
                customer=b.customer or "",
                article=b.article or "",
                color_code=b.color_code or "",
                color_name=b.color_name or "",
                fabric_weight=float(b.fabric_weight_kg or 350.0),
                program_title=b.recipe_name or f"Prog {prog_no}"
            )
            q_rec = bytearray(bref[:759])
            struct.pack_into("<HH", q_rec, 755, 0, idx)
            q_records.append(bytes(q_rec))

        q_bytes = generate_queue_btd(q_records, mach_code)
        if q_bytes:
            # Simpan cermin lokal
            local_mach_dir = os.path.join(LOCAL_DATA_DIR, "OT", "MACHINES", mach_code, "BATCHES")
            os.makedirs(local_mach_dir, exist_ok=True)
            with open(os.path.join(local_mach_dir, "QUEUE.BTD"), "wb") as f_q:
                f_q.write(q_bytes)

            # Upload ke FTP Controller - HANYA UNTUK MESIN DA01
            if ftp and mach_code == "DA01":
                try:
                    ftp_queue_dir = f"/Network/F/OT/MACHINES/{mach_code}/BATCHES"
                    try:
                        ftp.cwd(ftp_queue_dir)
                    except Exception:
                        for part in ["/Network", "/Network/F", "/Network/F/OT", "/Network/F/OT/MACHINES", f"/Network/F/OT/MACHINES/{mach_code}", ftp_queue_dir]:
                            try:
                                ftp.mkd(part)
                            except Exception:
                                pass
                        ftp.cwd(ftp_queue_dir)

                    ftp.storbinary("STOR QUEUE.BTD", io.BytesIO(q_bytes))
                    logger.info(f"[SUKSES] QUEUE.BTD ({len(q_records)} batch antrean) diunggah ke FTP: {ftp_queue_dir}/QUEUE.BTD")
                except Exception as qe:
                    logger.error(f"[GAGAL] Upload QUEUE.BTD ke FTP {mach_code}: {qe}")
            elif ftp:
                logger.info(f"[MODE AMAN] Lewati penulisan QUEUE.BTD ke FTP untuk mesin {mach_code} (hanya DA01 yang diizinkan menulis).")

    if ftp:
        try:
            ftp.quit()
        except Exception:
            try:
                ftp.close()
            except Exception:
                pass

    logger.info(f"Sinkronisasi selesai! Total {len(results)} folder batch telah diproses.")
    return results
