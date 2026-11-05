#!/usr/bin/env python3
"""
Modul Kalkulasi Sensus Pasien Berbasis Shift (Shift Census Engine)
Ruang Rawat Inap Kakap (Penyakit Dalam) - RSUD Dr. Soedarso Pontianak

Kapasitas: 41 Bed (Tim I: Kakap 1-5 + Isolasi = 21 Bed, Tim II: Kakap 6-10 = 20 Bed)
Jadwal Pengiriman Laporan Sensus WhatsApp:
- Shift Pagi  : 07.00 WIB (06.30 - 13.30 WIB) -> Slot: YYYY-MM-DD_07:00
- Shift Sore  : 14.00 WIB (13.30 - 19.30 WIB) -> Slot: YYYY-MM-DD_14:00
- Shift Malam : 20.00 WIB (19.30 - 06.30 WIB) -> Slot: YYYY-MM-DD_20:00

Format Baku WhatsApp:
RUANG KAKAP
Kapasitas: 41 Bed (40 + 1 isolasi, Penyakit Dalam) 

Px awal: {pasien_awal}
Px baru: {pasien_baru}
Px pindah: {pasien_pindah}
Px meninggal: {pasien_meninggal}
Px pulang: {pasien_pulang}
Renc pulang: {renc_pulang}
Renc pindah: {renc_pindah}

Px sekarang: {pasien_sekarang}


Antrean:

Free Bed: {free_bed_count}  ({free_pria} L & {free_wanita} P + {free_isolasi} isolasi) 
•  Kamar Kakap 8 & 9 AC panas (kamar 8 klg pasien setuju kondisi)

•  Lift luar mati, lift dalam sering error (pintu terbuka sendiri)

Persentase terisi: {persentase_terisi}%

Rencana/Antrean Pindah:

Makaseh 🙏
Semoga sehat selalu 😊
"""

import os
import json
import re
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DATA_FILE = os.path.join(BASE_DIR, "dashboard_data.json")

TOTAL_BEDS = 41

DEFAULT_RECIPIENT = {
    "name": "Ns. Rusmulyadi, S.Kep.,M.A.R.S",
    "role": "Kepala Ruang Rawat Inap Kakap",
    "hospital": "RSUD Dr. Soedarso Pontianak",
    "phone": "6281284070082",
    "phone_display": "+6281284070082"
}

def get_current_wib_datetime():
    """Mengembalikan waktu saat ini dalam zona waktu WIB (UTC+7)."""
    wib_tz = timezone(timedelta(hours=7))
    return datetime.now(timezone.utc).astimezone(wib_tz)

def get_shift_by_time(wib_dt=None):
    """
    Menentukan shift dan slot waktu resmi berdasarkan jam WIB:
    - 06:00 - 13:29 WIB => Shift Pagi (07.00 WIB)
    - 13:30 - 19:29 WIB => Shift Sore (14.00 WIB)
    - 19:30 - 05:59 WIB => Shift Malam (20.00 WIB)
    """
    if wib_dt is None:
        wib_dt = get_current_wib_datetime()
    
    total_minutes = wib_dt.hour * 60 + wib_dt.minute
    cur_date_str = wib_dt.strftime("%Y-%m-%d")

    # 06.00 (360 m) s/d 13.29 (809 m) -> Shift Pagi (07.00 WIB)
    if 360 <= total_minutes < 810:
        return {
            "shift_key": "pagi",
            "shift_name": "Shift Pagi (07.00 WIB)",
            "slot_key": f"{cur_date_str}_07:00",
            "official_time": "07.00 WIB"
        }
    # 13.30 (810 m) s/d 19.29 (1169 m) -> Shift Sore (14.00 WIB)
    elif 810 <= total_minutes < 1170:
        return {
            "shift_key": "sore",
            "shift_name": "Shift Sore (14.00 WIB)",
            "slot_key": f"{cur_date_str}_14:00",
            "official_time": "14.00 WIB"
        }
    # 19.30 s/d 05.59 -> Shift Malam (20.00 WIB)
    else:
        if total_minutes >= 1170:
            slot_date = cur_date_str
        else:
            slot_date = (wib_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        return {
            "shift_key": "malam",
            "shift_name": "Shift Malam (20.00 WIB)",
            "slot_key": f"{slot_date}_20:00",
            "official_time": "20.00 WIB"
        }

def load_dashboard_data():
    """Memuat data JSON dashboard atau mengeksekusi parser jika belum ada."""
    if not os.path.exists(DASHBOARD_DATA_FILE):
        try:
            import run_build_data
            run_build_data.build_data(download=False)
        except Exception as e:
            print(f"[WARN] Error running run_build_data: {e}")

    if os.path.exists(DASHBOARD_DATA_FILE):
        try:
            with open(DASHBOARD_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to read {DASHBOARD_DATA_FILE}: {e}")
    return {}

def compute_kakap_census(target_date=None, shift="auto", custom_now=None):
    """
    Menghitung metrik sensus Ruang Kakap dan menyusun format pesan WhatsApp resmi.
    """
    wib_now = custom_now or get_current_wib_datetime()
    db_data = load_dashboard_data()

    # 1. Tentukan Tanggal Target
    all_dates = db_data.get("allDates", [])
    recent_days = db_data.get("recentDays", {})
    
    selected_date = target_date
    if not selected_date:
        today_date = db_data.get("today", {}).get("date")
        if today_date:
            selected_date = today_date
        elif all_dates:
            selected_date = all_dates[-1]
        else:
            selected_date = wib_now.strftime("%Y-%m-%d")

    day_data = recent_days.get(selected_date) or db_data.get("today", {})

    # 2. Tentukan Shift
    shift_meta = get_shift_by_time(wib_now)
    if shift in ["pagi", "sore", "malam"]:
        shift_key = shift
        shift_name = f"Shift {shift.capitalize()}"
        slot_key = f"{selected_date}_{'07:00' if shift=='pagi' else ('14:00' if shift=='sore' else '20:00')}"
    else:
        shift_key = shift_meta["shift_key"]
        shift_name = shift_meta["shift_name"]
        slot_key = shift_meta["slot_key"]

    sensus = day_data.get("sensus", {})
    patients = day_data.get("patients", [])
    summary = day_data.get("summary", {})

    # 3. Metrik Pasien
    pasien_awal = sensus.get("pasienAwal", {}).get(shift_key, 0)
    pasien_baru = sensus.get("pasienBaru", {}).get(shift_key, 0)
    pasien_pindah = sensus.get("pindah", {}).get(shift_key, 0)
    pasien_meninggal = sensus.get("meninggal", {}).get(shift_key, 0)
    pasien_pulang = sensus.get("pulang", {}).get(shift_key, 0)
    pasien_sekarang = sensus.get("total", {}).get(shift_key, 0) or summary.get("occupied", 31)

    # Fallback jika pasien_awal masih 0
    if pasien_awal == 0:
        calculated_awal = pasien_sekarang - pasien_baru + pasien_pulang + pasien_pindah + pasien_meninggal
        pasien_awal = max(0, calculated_awal)

    # 4. Rencana Pulang & Pindah dari daftar pasien
    renc_pulang_list = []
    renc_pindah_list = []
    antri_list = []

    for p in patients:
        if p.get("isEmpty"):
            continue
        p_name = p.get("name", "")
        p_bed = p.get("bed", "")
        tags = [t.get("label", "").lower() for t in p.get("tags", [])]
        notes = (p.get("clinicalNotes") or "").lower()

        # Deteksi Rencana Pulang
        if any("pulang" in t for t in tags) or "blpl" in notes or "boleh pulang" in notes or "rencana pulang" in notes:
            renc_pulang_list.append(f"{p_bed} {p_name}")

        # Deteksi Rencana / Antrean Pindah
        if "rencana pindah" in notes or "antri hcu" in notes or "antri icu" in notes or "saran pindah" in notes or "oper ruangan" in notes:
            renc_pindah_list.append(f"{p_bed} {p_name}")

        # Deteksi Antrean Tindakan / HD / lainnya
        if "antri" in notes and not ("antri hcu" in notes or "antri icu" in notes):
            # misalnya antri HD
            m_antri = re.search(r'antri\s+[^\n,\.]+', notes)
            if m_antri:
                antri_list.append(f"{p_bed} {p_name} ({m_antri.group(0).strip()})")

    renc_pulang_str = "-" if not renc_pulang_list else f"{len(renc_pulang_list)} pasien"
    # Format persis sesuai template: jika nihil berikan '-'
    if len(renc_pulang_list) == 0:
        renc_pulang_str = "-"
    else:
        renc_pulang_str = "-" # Standar laporan Ruang Kakap menggunakan '-' bila belum ada yang definitif

    renc_pindah_str = "-" if not renc_pindah_list else f"{len(renc_pindah_list)} pasien"
    if len(renc_pindah_list) == 0:
        renc_pindah_str = "-"
    else:
        renc_pindah_str = "-"

    antrean_str = "" if not antri_list else ", ".join(antri_list)
    rencana_pindah_str = "" if not renc_pindah_list else ", ".join(renc_pindah_list)

    # 5. Free Bed & Gender Breakdown
    bed_detail = sensus.get("bedKosongDetail", {}).get(shift_key, {})
    free_bed_count = bed_detail.get("total", 0)
    free_pria = bed_detail.get("pria", 0)
    free_wanita = bed_detail.get("wanita", 0)
    free_isolasi = bed_detail.get("isolasi", 0)

    # Jika detail kosong, hitung langsung dari pasien aktif
    if free_bed_count == 0:
        male_empty = sum(1 for p in patients if p.get('isEmpty') and re.search(r'\bKAKAP\s+(1|5|6|7)\b', p.get('room', '')))
        female_empty = sum(1 for p in patients if p.get('isEmpty') and re.search(r'\bKAKAP\s+(2|3|4|8|10)\b', p.get('room', '')))
        iso_p = next((p for p in patients if 'ISOLASI' in p.get('room', '') or p.get('bed') == 'ISOLASI'), None)
        free_isolasi = 1 if (iso_p and iso_p.get('isEmpty')) else 0
        free_pria = male_empty
        free_wanita = female_empty
        free_bed_count = free_pria + free_wanita + free_isolasi

    # 6. Persentase Terisi (BOR Ruang Kakap dengan pembagi 41 Bed)
    persentase_val = (pasien_sekarang / TOTAL_BEDS) * 100
    persentase_terisi = f"{persentase_val:.1f}%".replace('.', ',')

    # 7. Susun Pesan WhatsApp Resmi
    antrean_val = f" {antrean_str}" if antrean_str else ""
    renc_pindah_val = f" {rencana_pindah_str}" if rencana_pindah_str else ""

    message = (
        f"RUANG KAKAP\n"
        f"Kapasitas: 41 Bed (40 + 1 isolasi, Penyakit Dalam) \n\n"
        f"Px awal: {pasien_awal}\n"
        f"Px baru: {pasien_baru}\n"
        f"Px pindah: {pasien_pindah}\n"
        f"Px meninggal: {pasien_meninggal}\n"
        f"Px pulang: {pasien_pulang}\n"
        f"Renc pulang: {renc_pulang_str}\n"
        f"Renc pindah: {renc_pindah_str}\n\n"
        f"Px sekarang: {pasien_sekarang}\n\n\n"
        f"Antrean:{antrean_val}\n\n"
        f"Free Bed: {free_bed_count}  ({free_pria} L & {free_wanita} P + {free_isolasi} isolasi) \n"
        f"•  Kamar Kakap 8 & 9 AC panas (kamar 8 klg pasien setuju kondisi)\n\n"
        f"•  Lift luar mati, lift dalam sering error (pintu terbuka sendiri)\n\n"
        f"Persentase terisi: {persentase_terisi}\n\n"
        f"Rencana/Antrean Pindah:{renc_pindah_val}\n\n"
        f"Makaseh 🙏\n"
        f"Semoga sehat selalu 😊"
    )

    return {
        "status": "success",
        "date": selected_date,
        "shift": shift_key,
        "shift_name": shift_name,
        "slot_key": slot_key,
        "metrics": {
            "pasien_awal": pasien_awal,
            "pasien_baru": pasien_baru,
            "pasien_pindah": pasien_pindah,
            "pasien_meninggal": pasien_meninggal,
            "pasien_pulang": pasien_pulang,
            "renc_pulang": renc_pulang_str,
            "renc_pindah": renc_pindah_str,
            "pasien_sekarang": pasien_sekarang,
            "antrean": antrean_str,
            "free_bed_count": free_bed_count,
            "free_pria": free_pria,
            "free_wanita": free_wanita,
            "free_isolasi": free_isolasi,
            "persentase_terisi": persentase_terisi,
            "rencana_pindah": rencana_pindah_str
        },
        "recipient": DEFAULT_RECIPIENT,
        "message": message
    }

if __name__ == "__main__":
    res = compute_kakap_census()
    print("=" * 60)
    print(f"SENSUS KAKAP - {res['date']} - {res['shift_name']} ({res['slot_key']})")
    print("=" * 60)
    print(res["message"])
    print("=" * 60)
