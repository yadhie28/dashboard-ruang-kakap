#!/bin/bash
# ==============================================================================
# Auto Sync & Sensus WhatsApp Dispatcher - Ruang Rawat Inap Kakap
# RSUD Dr. Soedarso Pontianak
# Jadwal Resmi Sensus WA: 07.00 WIB, 14.00 WIB, 20.00 WIB
# Target: Ns. Rusmulyadi, S.Kep.,M.A.R.S (+6281284070082)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="$SCRIPT_DIR/auto_sync.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "================================================================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Memulai Sinkronisasi Sensus Ruang Kakap..."
echo "================================================================================"

# 1. Unduh Spreadsheet Kakap Terbaru & Bangun Data
echo "[STEP 1] Mengunduh data Google Spreadsheet Ruang Kakap..."
python3 run_build_data.py --download

# 2. Kirim Laporan Sensus WhatsApp ke Kepala Ruang Kakap (Terjadwal 07.00, 14.00, 20.00 WIB)
echo "[STEP 2] Memeriksa & Mengirim Laporan Sensus WhatsApp ke Kepala Ruang Kakap..."
python3 send_whatsapp.py --sensus --scheduled-only --gateway fonnte || {
    echo "[WARN] Pengiriman gateway mengembalikan peringatan (mungkin di luar jadwal atau slot sudah terkirim)."
}

# 3. Commit dan Sinkronkan ke GitHub Repository (jika ada perubahan)
if [ -d ".git" ]; then
    echo "[STEP 3] Memeriksa perubahan data untuk repositori GitHub..."
    if ! git diff --quiet dashboard_data.json hospital_indicators.json kakap_data.xlsx shift_sent_wa.json 2>/dev/null; then
        echo "[GIT] Menyimpan pembaruan data sensus..."
        git add dashboard_data.json hospital_indicators.json kakap_data.xlsx shift_sent_wa.json
        git commit -m "chore(auto-sync): update sensus & data Ruang Kakap [skip ci]" || echo "[GIT] Tidak ada perubahan untuk dicommit."
        git push origin main || echo "[GIT] Push ditunda/dilewati."
    else
        echo "[GIT] Data sensus lokal sudah sinkron dengan repositori."
    fi
fi

echo "================================================================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sinkronisasi Sensus Ruang Kakap Selesai."
echo "================================================================================"
