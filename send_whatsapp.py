#!/usr/bin/env python3
"""
Sistem Pengirim Laporan Sensus WhatsApp Messenger
Ruang Rawat Inap Kakap (Penyakit Dalam) - RSUD Dr. Soedarso Pontianak

Tujuan : Kepala Ruang Kakap (Ns. Rusmulyadi, S.Kep.,M.A.R.S)
Nomor  : +6281284070082
Jadwal : 07.00 WIB, 14.00 WIB, dan 20.00 WIB
Gateway: Fonnte API (otomatis di background) & fallback WhatsApp Web / wa.me
"""

import os
import sys
import json
import urllib.parse
import urllib.request
import webbrowser
import subprocess
import argparse
import time
from datetime import datetime, timezone, timedelta

# Konfigurasi Penerima Resmi Kepala Ruang Kakap
DEFAULT_RECIPIENT = {
    "name": "Ns. Rusmulyadi, S.Kep.,M.A.R.S",
    "role": "Kepala Ruang Rawat Inap Kakap",
    "hospital": "RSUD Dr. Soedarso Pontianak",
    "phone_raw": "+6281284070082",
    "phone": "6281284070082"
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GATEWAY_CONFIG_PATH = os.path.join(BASE_DIR, "wa_gateway_config.json")
SENT_LOG_PATH = os.path.join(BASE_DIR, "shift_sent_wa.json")

# Master switch pengiriman WhatsApp Ruang Kakap (Aktif)
WHATSAPP_ENABLED = True

# Fallback default token Fonnte
DEFAULT_FONNTE_TOKEN = "Ayfow2x1hFiscQZSphzq"

def get_current_wib_datetime():
    """Mengembalikan datetime dalam zona waktu WIB (UTC+7) secara akurat."""
    wib_tz = timezone(timedelta(hours=7))
    return datetime.now(timezone.utc).astimezone(wib_tz)

def normalize_phone_number(phone: str) -> str:
    """Membersihkan dan menstandarkan nomor HP ke format internasional WhatsApp."""
    cleaned = ''.join(c for c in str(phone or '') if c.isdigit())
    if cleaned.startswith('08'):
        cleaned = '62' + cleaned[1:]
    elif cleaned.startswith('8'):
        cleaned = '62' + cleaned
    return cleaned

def generate_whatsapp_urls(phone: str = None, message: str = "") -> dict:
    """Membuat tautan langsung WhatsApp Web, Aplikasi Desktop, dan wa.me."""
    target_phone = normalize_phone_number(phone or DEFAULT_RECIPIENT["phone"])
    encoded_text = urllib.parse.quote(message)
    return {
        "web_url": f"https://web.whatsapp.com/send?phone={target_phone}&text={encoded_text}",
        "app_url": f"whatsapp://send?phone={target_phone}&text={encoded_text}",
        "wa_me_url": f"https://wa.me/{target_phone}?text={encoded_text}",
        "api_url": f"https://api.whatsapp.com/send?phone={target_phone}&text={encoded_text}"
    }

def load_gateway_config() -> dict:
    """Memuat konfigurasi gateway API jika tersimpan."""
    if os.path.exists(GATEWAY_CONFIG_PATH):
        try:
            with open(GATEWAY_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    token = os.getenv("FONNTE_TOKEN") or DEFAULT_FONNTE_TOKEN
    return {"provider": "fonnte", "token": token}

def save_gateway_config(provider: str, token: str) -> None:
    """Menyimpan konfigurasi gateway API lokal."""
    with open(GATEWAY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"provider": provider, "token": token}, f, indent=2)

def load_sent_log() -> dict:
    """Memuat histori pengiriman WhatsApp agar tidak terjadi duplikasi."""
    if os.path.exists(SENT_LOG_PATH):
        try:
            with open(SENT_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def record_sent_slot(slot_key: str, wib_str: str) -> None:
    """Mencatat slot checkpoint yang telah berhasil dikirim ke WA."""
    data = load_sent_log()
    data[slot_key] = wib_str
    try:
        with open(SENT_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[WARN] Gagal menyimpan log shift_sent_wa.json: {e}")

def check_scheduled_punctuality(window_minutes=25, custom_now=None, allow_catchup=True):
    """
    Memeriksa jadwal resmi sensus WhatsApp Ruang Kakap:
    - Shift Pagi  : 07.00 WIB (06.35 - 07.25 WIB) -> Slot: YYYY-MM-DD_07:00
    - Shift Sore  : 14.00 WIB (13.35 - 14.25 WIB) -> Slot: YYYY-MM-DD_14:00
    - Shift Malam : 20.00 WIB (19.35 - 20.25 WIB) -> Slot: YYYY-MM-DD_20:00
    
    Dilengkapi mode catch-up jika laptop/server baru aktif setelah jam jadwal
    agar laporan sensus tidak terlewat.
    """
    now_wib = custom_now if custom_now is not None else get_current_wib_datetime()
    hour = now_wib.hour
    minute = now_wib.minute
    cur_date_str = now_wib.strftime("%Y-%m-%d")
    wib_str = now_wib.strftime("%Y-%m-%d %H:%M:%S")

    total_minutes = hour * 60 + minute

    # 1. Pengecekan On-Time Window
    schedule_slots = [
        (7 * 60,  f"{cur_date_str}_07:00", "pagi"),
        (14 * 60, f"{cur_date_str}_14:00", "sore"),
        (20 * 60, f"{cur_date_str}_20:00", "malam"),
    ]
    for sched_total, slot_key, sh_key in schedule_slots:
        if (sched_total - window_minutes) <= total_minutes <= (sched_total + window_minutes):
            return True, slot_key, sh_key, wib_str, "on-time"

    # 2. Pengecekan Catch-up
    if allow_catchup:
        sent_log = load_sent_log()

        # Rentang Pagi: 06.35 - 13.34 WIB (target slot 07:00)
        if (6 * 60 + 35) <= total_minutes < (13 * 60 + 35):
            target_slot = f"{cur_date_str}_07:00"
            if target_slot not in sent_log:
                return True, target_slot, "pagi", wib_str, "catch-up (Shift Pagi 07.00)"

        # Rentang Sore: 13.35 - 19.34 WIB (target slot 14:00)
        elif (13 * 60 + 35) <= total_minutes < (19 * 60 + 35):
            target_slot = f"{cur_date_str}_14:00"
            if target_slot not in sent_log:
                return True, target_slot, "sore", wib_str, "catch-up (Shift Sore 14.00)"

        # Rentang Malam: 19.35 - 06.34 WIB (target slot 20:00)
        else:
            if total_minutes >= (19 * 60 + 35):
                target_slot = f"{cur_date_str}_20:00"
            else:
                prev_date_str = (now_wib - timedelta(days=1)).strftime("%Y-%m-%d")
                target_slot = f"{prev_date_str}_20:00"

            if target_slot not in sent_log:
                return True, target_slot, "malam", wib_str, "catch-up (Shift Malam 20.00)"

    return False, None, None, wib_str, "out-of-schedule"

def send_via_gateway(phone: str, message: str, token: str = None, provider: str = "fonnte") -> dict:
    """
    Mengirim pesan WhatsApp secara otomatis di latar belakang melalui Fonnte API Gateway.
    Dilengkapi automatic retry (3x), timeout 30 detik, serta curl fallback.
    """
    target_phone = normalize_phone_number(phone)
    active_token = token or os.getenv("FONNTE_TOKEN") or load_gateway_config().get("token") or DEFAULT_FONNTE_TOKEN

    if not active_token:
        return {
            "status": "error",
            "error": "API Token Gateway belum diisi. Masukkan token Fonnte untuk pengiriman otomatis."
        }

    max_retries = 3
    last_error = ""

    if provider == "fonnte":
        url = "https://api.fonnte.com/send"
        data = urllib.parse.urlencode({
            "target": target_phone,
            "message": message,
            "countryCode": "62"
        }).encode("utf-8")

        for attempt in range(1, max_retries + 1):
            try:
                req = urllib.request.Request(url, data=data, headers={"Authorization": active_token})
                with urllib.request.urlopen(req, timeout=30) as res:
                    body = res.read().decode("utf-8")
                    return {"status": "success", "provider": "fonnte", "response": json.loads(body)}
            except Exception as e:
                last_error = str(e)
                time.sleep(2)

        # Fallback menggunakan curl sistem macOS jika urllib timeout / ssl handshake issue
        try:
            curl_cmd = [
                "curl", "-s", "--max-time", "35", "--retry", "2",
                "-X", "POST", url,
                "-H", f"Authorization: {active_token}",
                "-d", f"target={target_phone}",
                "-d", "countryCode=62",
                "--data-urlencode", f"message={message}"
            ]
            c_res = subprocess.run(curl_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=40)
            if c_res.returncode == 0 and c_res.stdout.strip():
                resp_json = json.loads(c_res.stdout)
                return {"status": "success", "provider": "fonnte", "response": resp_json}
            else:
                last_error = c_res.stderr or "Curl failed without stdout"
        except Exception as ce:
            last_error = f"{last_error} | curl error: {ce}"

        return {"status": "error", "provider": "fonnte", "error": last_error}

    return {"status": "error", "error": f"Provider '{provider}' tidak didukung."}

def send_whatsapp_local(phone: str = None, message: str = "", mode: str = "web", launch_browser: bool = True) -> dict:
    """Membuka tautan WhatsApp Web / App / wa.me langsung di browser atau aplikasi desktop."""
    target_phone = normalize_phone_number(phone or DEFAULT_RECIPIENT["phone"])
    urls = generate_whatsapp_urls(target_phone, message)
    
    selected_url = urls["web_url"]
    if mode == "app":
        selected_url = urls["app_url"]
    elif mode == "universal":
        selected_url = urls["wa_me_url"]

    result = {
        "status": "success",
        "timestamp": get_current_wib_datetime().strftime("%Y-%m-%d %H:%M:%S"),
        "recipient": DEFAULT_RECIPIENT,
        "mode": mode,
        "selected_url": selected_url,
        "urls": urls,
        "launched": False
    }

    if launch_browser:
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", selected_url], check=True)
                result["launched"] = True
                result["launch_method"] = "macos_open"
            else:
                webbrowser.open(selected_url)
                result["launched"] = True
                result["launch_method"] = "webbrowser_module"
        except Exception as e:
            result["launched"] = False
            result["launch_error"] = str(e)

    return result

def main():
    if not WHATSAPP_ENABLED:
        print("[INFO] Pengiriman pesan WhatsApp ke Kepala Ruang dinonaktifkan (WHATSAPP_ENABLED = False).")
        return

    parser = argparse.ArgumentParser(description="Kirim Laporan Sensus WhatsApp ke Kepala Ruang Kakap")
    parser.add_argument("-m", "--message", default=None, help="Isi pesan kustom")
    parser.add_argument("--sensus", action="store_true", default=True, help="Gunakan template resmi laporan sensus WhatsApp Ruang Kakap")
    parser.add_argument("--shift", choices=["pagi", "sore", "malam", "auto"], default="auto", help="Pilih shift laporan (default: auto)")
    parser.add_argument("--date", default=None, help="Pilih tanggal laporan YYYY-MM-DD")
    parser.add_argument("-p", "--phone", default=DEFAULT_RECIPIENT["phone"], help="Nomor tujuan (default: 6281284070082)")
    parser.add_argument("--mode", choices=["web", "app", "universal"], default="web", help="Mode peluncuran lokal: web, app, universal")
    parser.add_argument("--gateway", choices=["fonnte", "wablas"], default="fonnte", help="Kirim melalui Gateway API di background (default: fonnte)")
    parser.add_argument("--token", default=None, help="API Token Fonnte")
    parser.add_argument("--save-token", action="store_true", help="Simpan token gateway ke wa_gateway_config.json")
    parser.add_argument("--scheduled-only", action="store_true", help="Kirim HANYA jika waktu sesuai jadwal shift (07.00, 14.00, 20.00 WIB) atau catch-up")
    parser.add_argument("--force", action="store_true", help="Paksa kirim mengabaikan filter jam dan deduplikasi")
    parser.add_argument("--test", "--no-send", dest="test_only", action="store_true", help="Hanya susun pesan dan tampilkan di terminal tanpa mengirim")
    parser.add_argument("--json", action="store_true", help="Output format JSON")

    args = parser.parse_args()

    slot_key = None
    shift_key = args.shift

    # On-Time Guard & Deduplikasi untuk run terjadwal
    if args.scheduled_only and not args.force:
        is_allowed, slot_key, detected_shift, wib_str, send_type = check_scheduled_punctuality(window_minutes=25, allow_catchup=True)
        if not is_allowed:
            print(f"[ON-TIME GUARD] Waktu saat ini: {wib_str} WIB.")
            print("[ON-TIME GUARD] Bukan jam jadwal resmi (07.00 / 14.00 / 20.00 WIB) atau laporan shift hari ini sudah terkirim. Pengiriman dibatalkan.")
            return

        sent_log = load_sent_log()
        if slot_key and slot_key in sent_log:
            print(f"[DEDUP GUARD] Laporan sensus slot {slot_key} sudah terkirim pada {sent_log[slot_key]}.")
            print("[DEDUP GUARD] Pengiriman diabaikan untuk mencegah duplikasi pesan ke Kepala Ruang.")
            return

        if shift_key == "auto":
            shift_key = detected_shift

        print(f"[SCHEDULE GUARD] Waktu: {wib_str} WIB | Status: {send_type} | Target Slot: {slot_key} | Shift: {shift_key}")

    # Susun Pesan Sensus Ruang Kakap
    import shift_census_calculator
    census_res = shift_census_calculator.compute_kakap_census(
        target_date=args.date,
        shift=shift_key
    )
    final_message = args.message if args.message else census_res["message"]
    effective_slot = slot_key or census_res.get("slot_key")

    if args.save_token and args.token:
        save_gateway_config(args.gateway, args.token)
        print(f"[INFO] Token gateway {args.gateway} berhasil disimpan ke wa_gateway_config.json")

    # Mode Test: tampilkan pesan tanpa mengirim
    if args.test_only:
        print("=" * 68)
        print(f" [MODE TEST / DRY-RUN] Sensus Ruang Kakap - {census_res['shift_name']}")
        print(f" Target  : {DEFAULT_RECIPIENT['name']} (+{args.phone})")
        print(f" Slot    : {effective_slot}")
        print("=" * 68)
        print(final_message)
        print("=" * 68)
        return

    # Kirim melalui Fonnte Gateway API
    if args.gateway:
        gw_res = send_via_gateway(
            phone=args.phone,
            message=final_message,
            token=args.token,
            provider=args.gateway
        )

        if args.json:
            print(json.dumps(gw_res, indent=2, ensure_ascii=False))
        else:
            print("=" * 68)
            print(" PENGIRIMAN LAPORAN SENSUS KAKAP VIA FONNTE WHATSAPP GATEWAY")
            print("=" * 68)
            print(f" Penerima : {DEFAULT_RECIPIENT['name']} ({DEFAULT_RECIPIENT['role']})")
            print(f" Nomor HP : +{args.phone}")
            print(f" Shift    : {census_res['shift_name']}")
            print(f" Status   : {gw_res.get('status')}")
            if gw_res.get("status") == "success":
                print(" Hasil    : [BERHASIL TERKIRIM] Pesan langsung masuk ke WhatsApp Kepala Ruang.")
                now_str = get_current_wib_datetime().strftime("%Y-%m-%d %H:%M:%S")
                if effective_slot:
                    record_sent_slot(effective_slot, now_str)
                    print(f" Catatan  : Slot {effective_slot} tercatat di shift_sent_wa.json")
            else:
                print(f" Error    : {gw_res.get('error')}")
                print(" Fallback : Membuka tautan manual WhatsApp...")
                send_whatsapp_local(phone=args.phone, message=final_message, mode=args.mode)
            print("=" * 68)
    else:
        # Fallback lokal
        send_whatsapp_local(phone=args.phone, message=final_message, mode=args.mode)

if __name__ == "__main__":
    main()
