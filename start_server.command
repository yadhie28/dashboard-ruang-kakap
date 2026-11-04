#!/bin/bash
cd "$(dirname "$0")"
echo "======================================================"
echo "    DASHBOARD RUANG KAKAP - LOCAL SERVER"
echo "    RSUD Dr. Soedarso Pontianak"
echo "======================================================"
echo "Lokasi Folder : $(pwd)"
echo "Jadwal Sync   : Otomatis jam 07.00, 14.00, 20.00 WIB"
echo "------------------------------------------------------"
echo "Membuka browser otomatis di http://localhost:3000..."
echo "Tekan Ctrl + C untuk menghentikan server jika selesai."
echo "======================================================"
(sleep 2 && open "http://localhost:3000") &
python3 server.py

