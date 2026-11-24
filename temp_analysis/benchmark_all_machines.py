import time
import sys
import os

# Set path to da-batch-worker
sys.path.insert(0, r'C:\Users\ruli_smm\DA-TEX\services\da-batch-worker')

from worker import run_cycle, init_mqtt

print("Inisialisasi MQTT...")
init_mqtt()
time.sleep(1)

print("Memulai 1 siklus penuh pemindaian seluruh 71 mesin pabrik...")
t0 = time.time()
run_cycle()
t_total = time.time() - t0
print(f"\n>>> BENCHMARK SELESAI: 71 mesin selesai diproses dalam {t_total:.2f} detik! <<<")
