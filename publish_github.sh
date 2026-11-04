#!/bin/bash
echo "==> Mendorong (Push) kode Dashboard Ruang Kakap ke GitHub..."
git push -u origin main

if [ $? -eq 0 ]; then
    echo "================================================================"
    echo "✅ Berhasil dipublish ke GitHub!"
    echo "URL Repositori: https://github.com/yadhie28/dashboard-ruang-kakap"
    echo "URL Live Demo: https://yadhie28.github.io/dashboard-ruang-kakap/"
    echo "================================================================"
else
    echo "❌ Gagal push ke GitHub. Pastikan repositori 'dashboard-ruang-kakap' sudah dibuat di https://github.com/new"
fi
