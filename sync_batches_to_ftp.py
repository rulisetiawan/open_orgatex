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
from open_orgatex.backend.database import get_db
from open_orgatex.backend.models.schema_pg import BatchHeader, MachineQueue
from open_orgatex.backend.utils.secom_codec import create_batchref_binary, build_minimal_prg, generate_queue_btd
from open_orgatex.backend.routes.programs import get_compiled_prg_bytes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_ftp_batches")

FTP_HOST = "192.168.1.95"
FTP_PORT = 21
FTP_BASE_BATCH_DIR = "/Network/F/OT/BATCH"
LOCAL_DATA_DIR = os.path.abspath("./open_orgatex/backend/data")
LOCAL_BATCH_DIR = os.path.join(LOCAL_DATA_DIR, "OT", "BATCH")


def sync_all_batches_to_ftp(ftp_host: str = FTP_HOST, ftp_port: int = FTP_PORT):
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

    except Exception as e:
        logger.error(f"Gagal koneksi ke FTP {ftp_host}:{ftp_port}: {e}")
        ftp = None

    results = []

    # 3. Proses setiap batch
    for b in batches:
        ref_no = str(b.batch_ref_no).strip().zfill(6)
        prog_no = int(b.program_no or 1)
        prg_name = f"M_{prog_no:04d}.PRG"
        mach_no = str(b.machine_no or "DA01").strip().upper()
        batch_no = str(b.batch_no or f"LOT-{ref_no}").strip()
        recipe_title = str(b.recipe_name or f"Program {prog_no}")

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
        if ftp and mach_no == "DA01":
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
                logger.info(f"[SUKSES] Folder FTP dibuat: {target_ftp_dir}/ -> [BATCHREF.REF, {prg_name}]")
            except Exception as fe:
                logger.error(f"[GAGAL] FTP upload {ref_no}: {fe}")
        elif ftp:
            logger.info(f"[MODE AMAN] Lewati penulisan FTP untuk batch {ref_no} mesin {mach_no} (hanya DA01 yang diizinkan menulis).")

        results.append(status_item)

    # 4. Sinkronisasi Antrean Mesin (QUEUE.BTD) ke FTP dan Lokal
    machine_batches = {}
    for b in batches:
        m = str(b.machine_no or "DA01").strip().upper()
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


if __name__ == "__main__":
    sync_all_batches_to_ftp()
