#!/usr/bin/env python3
"""
Server Dashboard Ruang Kakap - RSUD Dr. Soedarso Pontianak
Menyajikan UI Dashboard dan Menyediakan Sinkronisasi Otomatis/Manual dari Google Spreadsheet:
https://docs.google.com/spreadsheets/d/1-5y9GuHIFbHE0OwS5_tfvdC9j9DMLO55i7uQyKpAKhY/edit?usp=sharing
"""

import http.server
import socketserver
import os
import json
import urllib.request
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta

DEFAULT_PORT = 3000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
SYNC_INFO_FILE = os.path.join(DIRECTORY, "sync_info.json")
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1-5y9GuHIFbHE0OwS5_tfvdC9j9DMLO55i7uQyKpAKhY/export?format=xlsx"

SCHEDULE_HOURS = [
    {"hour": 7, "minute": 0, "name": "Shift Pagi", "desc": "Operan Jaga Malam ➔ Pagi"},
    {"hour": 14, "minute": 0, "name": "Shift Sore", "desc": "Operan Jaga Pagi ➔ Sore"},
    {"hour": 20, "minute": 0, "name": "Shift Malam", "desc": "Operan Jaga Sore ➔ Malam"}
]

sync_lock = threading.Lock()
sync_state = {
    "is_syncing": False,
    "last_sync": None,
    "last_status": "idle",
    "last_message": "Server aktif. Jadwal auto-sync shift aktif (07:00, 14:00, 20:00 WIB).",
    "sync_count": 0,
    "history": []
}

def load_sync_info():
    global sync_state
    if os.path.exists(SYNC_INFO_FILE):
        try:
            with open(SYNC_INFO_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                sync_state["last_sync"] = saved.get("last_sync")
                sync_state["last_status"] = saved.get("last_status", "success")
                sync_state["last_message"] = saved.get("last_message", "Tersinkronisasi")
                sync_state["sync_count"] = saved.get("sync_count", 0)
                sync_state["history"] = saved.get("history", [])[-20:]
        except Exception as e:
            print(f"[WARN] Gagal membaca sync_info.json: {e}")

def save_sync_info():
    try:
        with open(SYNC_INFO_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "last_sync": sync_state["last_sync"],
                "last_status": sync_state["last_status"],
                "last_message": sync_state["last_message"],
                "sync_count": sync_state["sync_count"],
                "history": sync_state["history"][-20:]
            }, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Gagal menyimpan sync_info.json: {e}")

def get_next_scheduled_sync(now=None):
    if now is None:
        now = datetime.now()
    candidates = []
    for s in SCHEDULE_HOURS:
        t_today = now.replace(hour=s["hour"], minute=s["minute"], second=0, microsecond=0)
        if t_today > now:
            candidates.append((t_today, s["name"], s["desc"]))
        else:
            t_tomorrow = t_today + timedelta(days=1)
            candidates.append((t_tomorrow, s["name"], s["desc"]))
    candidates.sort(key=lambda x: x[0])
    target_dt, shift_name, shift_desc = candidates[0]
    diff = target_dt - now
    total_seconds = int(diff.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return {
        "next_sync_datetime": target_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "shift_name": shift_name,
        "shift_desc": shift_desc,
        "countdown_seconds": total_seconds,
        "countdown_human": f"{hours} jam {minutes} menit lagi",
        "schedule_targets": ["07:00 WIB", "14:00 WIB", "20:00 WIB"]
    }

def execute_sync(trigger_type="manual"):
    global sync_state
    if not sync_lock.acquire(blocking=False):
        return {
            "success": False,
            "error": "Sinkronisasi sedang berlangsung oleh proses lain.",
            "is_syncing": True
        }

    sync_state["is_syncing"] = True
    start_time = datetime.now()
    log_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n========================================================")
    print(f"[SYNC START] ({trigger_type.upper()}) pada {log_time_str}")
    print(f"========================================================")

    try:
        dest_xlsx = os.path.join(DIRECTORY, "kakap_data.xlsx")
        print(f"[SYNC] Mengunduh data terbaru dari Google Sheets...")
        req = urllib.request.Request(
            SPREADSHEET_URL,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        )
        with urllib.request.urlopen(req, timeout=45) as resp, open(dest_xlsx, "wb") as f:
            f.write(resp.read())
        print(f"[SYNC] Berhasil diunduh: {os.path.getsize(dest_xlsx)} bytes")

        print(f"[SYNC] Menjalankan parser data (run_build_data.py)...")
        script_path = os.path.join(DIRECTORY, "run_build_data.py")
        res = subprocess.run([sys.executable, script_path], cwd=DIRECTORY, capture_output=True, text=True, check=True)
        print(f"[SYNC] Hasil build:\n{res.stdout.strip()}")

        duration = (datetime.now() - start_time).total_seconds()
        sync_state["last_sync"] = log_time_str
        sync_state["last_status"] = "success"
        sync_state["last_message"] = f"Sukses sinkronisasi {trigger_type} ({duration:.1f} detik)"
        sync_state["sync_count"] += 1
        sync_state["history"].append({
            "timestamp": log_time_str,
            "trigger": trigger_type,
            "status": "success",
            "duration": f"{duration:.1f}s"
        })
        save_sync_info()
        print(f"[SYNC FINISH] Berhasil dalam {duration:.1f}s")
        return {"success": True, "timestamp": log_time_str, "duration": f"{duration:.1f}s"}

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        err_msg = str(e)
        print(f"[SYNC ERROR] {err_msg}")
        sync_state["last_sync"] = log_time_str
        sync_state["last_status"] = "error"
        sync_state["last_message"] = f"Gagal: {err_msg}"
        sync_state["history"].append({
            "timestamp": log_time_str,
            "trigger": trigger_type,
            "status": "error",
            "error": err_msg
        })
        save_sync_info()
        return {"success": False, "error": err_msg}
    finally:
        sync_state["is_syncing"] = False
        sync_lock.release()

class DashboardRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/sync-schedule"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            schedule_info = get_next_scheduled_sync()
            payload = {
                "sync_state": {
                    "is_syncing": sync_state["is_syncing"],
                    "last_sync": sync_state["last_sync"],
                    "last_status": sync_state["last_status"],
                    "last_message": sync_state["last_message"],
                    "sync_count": sync_state["sync_count"]
                },
                "schedule": schedule_info,
                "history": sync_state["history"][-5:]
            }
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            return

        super().do_GET()

    def do_POST(self):
        if self.path == "/api/sync":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"
            trigger = "manual_web"
            try:
                body = json.loads(post_data.decode("utf-8"))
                if "trigger" in body: trigger = body["trigger"]
            except:
                pass

            result = execute_sync(trigger_type=trigger)
            status_code = 200 if result.get("success") else 500
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

def background_scheduler_worker():
    print(f"[SCHEDULER] Background worker aktif untuk shift 07:00, 14:00, dan 20:00 WIB.")
    last_triggered_date_hour = None
    while True:
        now = datetime.now()
        cur_h = now.hour
        cur_m = now.minute
        cur_tag = f"{now.strftime('%Y-%m-%d')}_{cur_h}"
        for s in SCHEDULE_HOURS:
            if cur_h == s["hour"] and cur_m in [0, 1] and cur_tag != last_triggered_date_hour:
                last_triggered_date_hour = cur_tag
                print(f"[SCHEDULER] Memicu auto-sync untuk {s['name']} ({s['desc']})...")
                execute_sync(trigger_type=f"auto_{s['name'].lower().replace(' ', '_')}")
        time.sleep(30)

def run_server():
    load_sync_info()
    sched_thread = threading.Thread(target=background_scheduler_worker, daemon=True)
    sched_thread.start()

    port = DEFAULT_PORT
    server = None
    for attempt in range(5):
        try:
            socketserver.TCPServer.allow_reuse_address = True
            server = socketserver.TCPServer(("", port), DashboardRequestHandler)
            break
        except OSError:
            print(f"[INFO] Port {port} sedang digunakan, mencoba port {port + 1}...")
            port += 1

    if not server:
        print("[ERROR] Tidak dapat mengikat port server.")
        return

    url = f"http://localhost:{port}"
    print(f"\n========================================================")
    print(f"🏥 DASHBOARD RUANG KAKAP - RSUD DR. SOEDARSO")
    print(f"🌐 Akses Web : {url}")
    print(f"📊 Auto-Sync : Aktif setiap 07:00, 14:00, 20:00 WIB")
    print(f"========================================================\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Server dihentikan.")
        server.server_close()

if __name__ == "__main__":
    run_server()

