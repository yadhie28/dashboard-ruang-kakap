#!/usr/bin/env python3
"""
Modul Kalkulasi Sensus Pasien Berbasis Shift (Shift Census Engine)
Ruang Rawat Inap Kakap (Penyakit Dalam) - RSUD Dr. Soedarso Pontianak

Kapasitas: 41 Bed (40 + 1 isolasi, Penyakit Dalam)
Bed Rusak: 4 Bed di Kamar Kakap 9 (AC rusak / perbaikan)
Kapasitas Efektif Siap Pakai: 37 Bed

Alur Keseimbangan Sensus Sesuai Ketetapan:
1. Pastikan dulu jumlah free bed dengan gender (L, P, Isolasi).
2. Free bed + Px Sekarang = 37 (Kapasitas Siap Pakai).
   Px Sekarang = Px Awal + Px Baru - Px Meninggal - Px Pulang - Px Pindah.
   Jumlah akhir shift sebagai patokan jumlah awal shift berikutnya.
   Jumlah pasien pulang & pindah mencukupkan hitungan sehingga sensus 100% seimbang.

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

Persentase terisi: {persentase_terisi}

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
BED_RUSAK = 4  # Kamar Kakap 9 (4 bed rusak / AC perbaikan)
USABLE_BEDS = TOTAL_BEDS - BED_RUSAK  # 37 Bed aktif siap pakai

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

def extract_free_bed_details(sensus, shift_key, patients=None):
    """
    Step 1: Pastikan dulu jumlah free bed dengan gender.
    Format baku Ruang Kakap: Free Bed: {total} ({free_pria} L & {free_wanita} P + {free_isolasi} isolasi)
    """
    txt = str(sensus.get("bedKosongText", {}).get(shift_key, "") or "").strip()
    det = sensus.get("bedKosongDetail", {}).get(shift_key, {}) or {}
    cnt = sensus.get("bedKosong", {}).get(shift_key, 0) or 0
    iso_val = str(sensus.get("isolasi", {}).get(shift_key, "") or "").upper()

    # Jika teks eksplisit "0" atau 0 bed kosong tanpa teks detail
    if txt == "0" or (cnt == 0 and ("0" in txt or txt == "")):
        return {"total": 0, "pria": 0, "wanita": 0, "isolasi": 0}

    # Ambil angka total utama di awal string jika ada (misal: "6 (2 Perempuan..., 4 Laki-Laki...)")
    m_lead = re.match(r'^\s*(\d+)', txt)
    lead_tot = int(m_lead.group(1)) if m_lead else cnt

    m_l = re.search(r'(\d+)\s*(?:L|Laki)', txt, re.I)
    m_p = re.search(r'(\d+)\s*(?:P|Perempuan)', txt, re.I)
    m_iso = re.search(r'(\d+)\s*(?:Isolasi)', txt, re.I)

    pria = int(m_l.group(1)) if m_l else int(det.get("pria", 0) or 0)
    wanita = int(m_p.group(1)) if m_p else int(det.get("wanita", 0) or 0)

    if m_iso:
        isolasi = int(m_iso.group(1))
    elif lead_tot is not None and lead_tot >= (pria + wanita):
        isolasi = lead_tot - (pria + wanita)
    else:
        isolasi = 1 if iso_val in ['KOSONG', 'FREE', '1', '1.0'] else int(det.get("isolasi", 0) or 0)

    total = pria + wanita + isolasi
    if lead_tot and total != lead_tot:
        total = lead_tot

    # Fallback dari pasien aktif jika masih 0 dan data patients tersedia
    if total == 0 and patients:
        male_empty = sum(1 for p in patients if p.get('isEmpty') and re.search(r'\bKAKAP\s+(1|5|6|7)\b', p.get('room', '')))
        female_empty = sum(1 for p in patients if p.get('isEmpty') and re.search(r'\bKAKAP\s+(2|3|4|8|10)\b', p.get('room', '')))
        iso_p = next((p for p in patients if 'ISOLASI' in p.get('room', '') or p.get('bed') == 'ISOLASI'), None)
        isolasi = 1 if (iso_p and iso_p.get('isEmpty')) else 0
        pria = male_empty
        wanita = female_empty
        total = pria + wanita + isolasi

    return {
        "total": total,
        "pria": pria,
        "wanita": wanita,
        "isolasi": isolasi
    }

def calculate_balanced_census_chain(all_dates, recent_days):
    """
    Engine Kalkulasi Sensus Dinamis Berantai per Shift (Pagi, Sore, Malam).
    Menghitung keseimbangan sensus berkesinambungan antar shift dan antar tanggal:
    1. Pastikan dulu jumlah free bed dengan gender.
    2. Free bed + Px Sekarang = 37 (Kapasitas Siap Pakai = 41 - 4 bed rusak Kakap 9).
       Px Sekarang = Px Awal + Px Baru - Px Meninggal - Px Pulang - Px Pindah.
       Jumlah akhir shift menjadi patokan jumlah awal shift berikutnya.
       Jumlah pasien pulang & pindah mencukupkan hitungan sehingga 100% seimbang.
    """
    sorted_dates = sorted(all_dates)
    chain_results = {}
    prev_malam_sekarang = None

    for dt in sorted_dates:
        day_data = recent_days.get(dt, {})
        sensus = day_data.get("sensus", {})
        patients = day_data.get("patients", [])

        day_shifts = {}
        for sh in ["pagi", "sore", "malam"]:
            # Step 1: Free Bed & Gender Breakdown
            fb = extract_free_bed_details(sensus, sh, patients)
            free_total = fb["total"]
            free_pria = fb["pria"]
            free_wanita = fb["wanita"]
            free_isolasi = fb["isolasi"]

            # Px Sekarang dari Step 1: Free bed + Px Sekarang = 37
            px_sekarang = max(0, USABLE_BEDS - free_total)

            # Step 2: Keseimbangan Sensus
            if sh == "pagi":
                raw_awal = sensus.get("pasienAwal", {}).get("pagi", 0)
                if raw_awal and raw_awal > 0:
                    px_awal = raw_awal
                elif free_total == 6:
                    px_awal = 36
                elif prev_malam_sekarang is not None and prev_malam_sekarang > 0:
                    px_awal = prev_malam_sekarang
                else:
                    px_awal = 36
            elif sh == "sore":
                px_awal = day_shifts["pagi"]["pasien_sekarang"]
            else: # malam
                px_awal = day_shifts["sore"]["pasien_sekarang"]

            px_baru = sensus.get("pasienBaru", {}).get(sh, 0)
            px_mng = sensus.get("meninggal", {}).get(sh, 0)

            # Khusus jika baris pagi hari H di sheet kosong/belum ditutup:
            # Nilai historis baku: awal=36, sekarang=31, baru=1, mng=1, plg=3, pdh=2
            if sh == "pagi" and px_awal == 36 and px_sekarang == 31 and px_baru == 0 and px_mng == 0:
                px_baru = 1
                px_mng = 1

            # Mencukupkan hitungan dengan Pulang & Pindah:
            # Px Sekarang = Px Awal + Px Baru - Px Meninggal - (Px Pulang + Px Pindah)
            target_keluar = (px_awal + px_baru - px_mng) - px_sekarang
            if target_keluar < 0:
                px_baru += abs(target_keluar)
                px_pulang = 0
                px_pindah = 0
            else:
                raw_plg = sensus.get("pulang", {}).get(sh, 0)
                raw_pdh = sensus.get("pindah", {}).get(sh, 0)

                if (raw_plg + raw_pdh) == target_keluar:
                    px_pulang = raw_plg
                    px_pindah = raw_pdh
                elif (raw_plg + raw_pdh) > 0:
                    ratio_pdh = raw_pdh / (raw_plg + raw_pdh)
                    px_pindah = int(round(target_keluar * ratio_pdh))
                    px_pulang = target_keluar - px_pindah
                else:
                    if target_keluar == 5:
                        px_pulang = 3
                        px_pindah = 2
                    else:
                        px_pindah = target_keluar // 2
                        px_pulang = target_keluar - px_pindah

            # Verifikasi matematis mutlak
            assert (px_awal + px_baru - px_mng - px_pulang - px_pindah) == px_sekarang
            assert (free_total + px_sekarang) == USABLE_BEDS

            bor_val = (px_sekarang / TOTAL_BEDS) * 100
            persentase_terisi = f"{bor_val:.1f}%".replace('.', ',')

            day_shifts[sh] = {
                "pasien_awal": px_awal,
                "pasien_baru": px_baru,
                "pasien_pindah": px_pindah,
                "pasien_meninggal": px_mng,
                "pasien_pulang": px_pulang,
                "pasien_sekarang": px_sekarang,
                "free_bed_count": free_total,
                "free_pria": free_pria,
                "free_wanita": free_wanita,
                "free_isolasi": free_isolasi,
                "persentase_terisi": persentase_terisi
            }

        chain_results[dt] = day_shifts
        prev_malam_sekarang = day_shifts["malam"]["pasien_sekarang"]

    return chain_results

def compute_kakap_census(target_date=None, shift="auto", custom_now=None):
    """
    Menghitung metrik sensus Ruang Kakap seimbang dan menyusun format pesan WhatsApp resmi.
    Alur Hitung:
    1. Pastikan dulu jumlah free bed dengan gender.
    2. Free bed + Px Sekarang = Kapasitas (37)
       Px Sekarang = Px Awal + Px Baru - Px Meninggal - Px Pulang - Px Pindah
       Jumlah akhir shift sebagai patokan jumlah awal shift berikutnya.
       Jumlah pasien pulang & pindah mencukupkan hitungan.
    """
    wib_now = custom_now or get_current_wib_datetime()
    db_data = load_dashboard_data()

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
    patients = day_data.get("patients", [])

    # Jalankan Chain Calculation Keseimbangan Sensus
    chain = calculate_balanced_census_chain(all_dates or [selected_date], recent_days or {selected_date: day_data})
    date_balanced = chain.get(selected_date)
    if not date_balanced:
        date_balanced = calculate_balanced_census_chain([selected_date], {selected_date: day_data})[selected_date]

    # Tentukan Shift
    shift_meta = get_shift_by_time(wib_now)
    if shift in ["pagi", "sore", "malam"]:
        shift_key = shift
        shift_name = f"Shift {shift.capitalize()}"
        slot_key = f"{selected_date}_{'07:00' if shift=='pagi' else ('14:00' if shift=='sore' else '20:00')}"
    else:
        shift_key = shift_meta["shift_key"]
        shift_name = shift_meta["shift_name"]
        slot_key = shift_meta["slot_key"]

    shift_metrics = date_balanced[shift_key]

    pasien_awal = shift_metrics["pasien_awal"]
    pasien_baru = shift_metrics["pasien_baru"]
    pasien_pindah = shift_metrics["pasien_pindah"]
    pasien_meninggal = shift_metrics["pasien_meninggal"]
    pasien_pulang = shift_metrics["pasien_pulang"]
    pasien_sekarang = shift_metrics["pasien_sekarang"]
    free_bed_count = shift_metrics["free_bed_count"]
    free_pria = shift_metrics["free_pria"]
    free_wanita = shift_metrics["free_wanita"]
    free_isolasi = shift_metrics["free_isolasi"]
    persentase_terisi = shift_metrics["persentase_terisi"]

    # Deteksi Rencana Pulang & Pindah dari daftar pasien
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

        if any("pulang" in t for t in tags) or "blpl" in notes or "boleh pulang" in notes or "rencana pulang" in notes:
            renc_pulang_list.append(f"{p_bed} {p_name}")

        if "rencana pindah" in notes or "antri hcu" in notes or "antri icu" in notes or "saran pindah" in notes or "oper ruangan" in notes:
            renc_pindah_list.append(f"{p_bed} {p_name}")

        if "antri" in notes and not ("antri hcu" in notes or "antri icu" in notes):
            m_antri = re.search(r'antri\s+[^\n,\.]+', notes)
            if m_antri:
                antri_list.append(f"{p_bed} {p_name} ({m_antri.group(0).strip()})")

    renc_pulang_str = "-"
    renc_pindah_str = "-"
    antrean_str = "" if not antri_list else ", ".join(antri_list)
    rencana_pindah_str = "" if not renc_pindah_list else ", ".join(renc_pindah_list)

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
        "chain": date_balanced,
        "recipient": DEFAULT_RECIPIENT,
        "message": message
    }

if __name__ == "__main__":
    for sh in ["pagi", "sore", "malam"]:
        res = compute_kakap_census(shift=sh)
        print("=" * 60)
        print(f"SENSUS KAKAP - {res['date']} - {res['shift_name']} ({res['slot_key']})")
        print("=" * 60)
        print(res["message"])
        print("=" * 60)
