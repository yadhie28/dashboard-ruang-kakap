#!/bin/bash
LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -n 1)
PORT=3000
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=================================================================="
echo "    PILIHAN TAUTAN SHARING DASHBOARD RUANG KAKAP"
echo "    RSUD Dr. Soedarso Pontianak"
echo "=================================================================="
echo ""
echo "1. JARINGAN WI-FI / LAN SAMA (RSUD Dr. Soedarso):"
echo "   http://${LOCAL_IP}:${PORT}/"
echo ""
echo "2. TAUTAN ONLINE INTERNET CLOUDFLARE (HTTPS):"
echo "   Bisa dibuka dari Smartphone / Kuota Data sejawat di mana saja."
echo "=================================================================="
if command -v cloudflared &> /dev/null; then
    cloudflared tunnel --url http://localhost:${PORT}
else
    echo "Cloudflared belum terpasang. Gunakan URL LAN lokal di atas untuk akses dari jaringan yang sama."
fi

