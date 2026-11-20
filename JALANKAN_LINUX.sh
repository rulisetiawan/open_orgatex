#!/usr/bin/env bash
# ==============================================================================
# OpenOrgaTEX Industrial MES - Launcher Linux (Tanpa Docker)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

echo "======================================================================"
echo "  OpenOrgaTEX Industrial MES - Server Mode (Tanpa Docker)"
echo "======================================================================"

# 1. Cek Python3
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 tidak ditemukan. Silakan pasang dengan: sudo apt install python3 python3-pip"
    exit 1
fi

# 2. Cek dependensi
echo "Memeriksa paket uvicorn & fastapi..."
python3 -c "import fastapi, uvicorn" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Memasang dependensi dari open_orgatex/backend/requirements.txt..."
    pip3 install -r open_orgatex/backend/requirements.txt
fi

echo ""
echo "======================================================================"
echo "  Aplikasi berjalan di port 8743"
echo "  - Akses lokal          : http://localhost:8743"
echo "  - Akses jaringan Wi-Fi : http://$(hostname -I | awk '{print $1}'):8743"
echo "======================================================================"
echo ""

python3 -m uvicorn open_orgatex.backend.app:app --host 0.0.0.0 --port 8743
