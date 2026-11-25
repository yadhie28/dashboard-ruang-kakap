"""
Data Build Pipeline for Dashboard Ruang Kakap (RSUD Dr. Soedarso Pontianak)
Unified parser for Google Spreadsheet:
https://docs.google.com/spreadsheets/d/1-5y9GuHIFbHE0OwS5_tfvdC9j9DMLO55i7uQyKpAKhY/edit?usp=sharing

Features:
- Single-workbook parser with 41-bed capacity (Kakap 1-10 @ 4 beds + 1 Isolasi)
- Tim I (Kakap 1-5 & Isolasi = 21 Bed) and Tim II (Kakap 6-10 = 20 Bed)
- Cell fill color detection for discharges / status
- Automatic SENSUS metrics extraction (Perawat, Pasien Awal, Baru, Pulang, Pindah, Meninggal, Total)
- EWS / NEWS2 physiological scoring from clinical notes
- Hospital Quality Indicators (BOR, AVLOS, TOI, BTO, NDR, GDR, Barber-Johnson)
"""

import zipfile
import xml.etree.ElementTree as ET
import re
import json
import os
import urllib.request
from datetime import datetime, date, timedelta, timezone
from collections import defaultdict
import crypto_vault

WIB_TZ = timezone(timedelta(hours=7))

TOTAL_BEDS = 41
TIM1_BEDS = 21 # Kakap 1-5 (20 bed) + Isolasi (1 bed)
TIM2_BEDS = 20 # Kakap 6-10 (20 bed)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1-5y9GuHIFbHE0OwS5_tfvdC9j9DMLO55i7uQyKpAKhY/export?format=xlsx"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
XLSX_PATH = os.path.join(BASE_DIR, "kakap_data.xlsx")
DASHBOARD_DATA_JSON = os.path.join(BASE_DIR, "dashboard_data.json")
HOSPITAL_INDICATORS_JSON = os.path.join(BASE_DIR, "hospital_indicators.json")
CLINICAL_PATHWAYS_JSON = os.path.join(BASE_DIR, "clinical_pathways.json")

HEADER_COLORS = {'FF1F4E78', 'FF356854', 'FF38761D', 'FF6AA84F', 'FF073763', 'FF0B5394'}
IGNORE_COLORS = {'FFFFFFFF', 'FF000000', 'FFF8F9FA', 'FFF6F8F9', 'FFF3F3F3', 'FFEFEFEF', 'FFF2F2F2', 'FFFFFF99', None}

# Warna status pasien (hanya dibaca dari kolom pasien D/G/H/I/J, BUKAN kolom kamar A)
COLOR_STATUS_MAP = {
    'meninggal': {'FFEAD1DC', 'FFFF0000', 'FFEA9999', 'FFF4CCCC', 'FFE06666', 'FFCC0000', 'FFDD7E6B'},
    'aps': {'FFFF9900', 'FFF6B26B', 'FFE69138', 'FFFFB347'},
    'pindah': {'FFFFFF00', 'FFFFE599', 'FFFFF2CC', 'FFF1C232'},
    'blpl': {'FF00FF00', 'FFD9EAD3', 'FFB6D7A8', 'FF93C47D', 'FF6AA84F', 'FF34A853'}
}

# Doctor Name Canonical Map (diperluas mencakup seluruh DPJP & konsulen Ruang Kakap)
DOCTOR_CANONICAL = {
    "IVAN": "dr. Ivan Lumban Toruan, Sp.PD-KHOM",
    "SONY": "dr. R. Sony Yusuf Wibisono, Sp.PD-KGH",
    "DARMAWAN": "dr. Darmawan, M.Kes., Sp.PD-KGH, FINASIM",
    "DECKY": "dr. Decky Andrea, Sp.PD",
    "APRIANI": "dr. Apriani, M.Ked(PD), Sp.PD",
    "HARRY": "dr. Harry Andhika, Sp.PD",
    "YUSTAR": "dr. Yustar Mulyadi, Sp.PD",
    "MUHARDANI": "dr. Muhardani Iqbal, M.Ked(PD), Sp.PD",
    "DANAR": "dr. Danar Anggrahini K.D., Sp.PD-KGH, FINASIM",
    "ZAINUL": "dr. Zainul Naim, Sp.B-KBD",
    "RETNO": "dr. Retno Mustikaningsih, M.Kes., Sp.K",
    "DINI": "dr. Dini, Sp.N",
    "OKTAV": "dr. Oktavianus, Sp.OT (Spine)",
    "GERALD": "dr. Gerald, Sp.B",
    "YANCE": "dr. Yance, Sp.U",
    "TEMI": "dr. Temi, Sp.JP",
    "DANAYU": "dr. Danayu, Sp.JP"
}

def mask_patient_name_py(name):
    if not name or any(k in name for k in ['Bed Kosong', 'Kosong', 'Rusak', 'BAU']):
        return name
    m = re.match(r'^(Tn\.|Ny\.|An\.|By\.|Sdr\.|Sdri\.|Nn\.)\s*(.*)', name, re.I)
    if m:
        title = m.group(1)
        rest = m.group(2).strip()
        parts = [p[0] + '***' for p in rest.split() if p]
        return f"{title} {' '.join(parts)}".strip()
    parts = [p[0] + '***' for p in name.split() if p]
    return ' '.join(parts)

def mask_mr_py(mr):
    s = re.sub(r'\D', '', str(mr or ''))
    if not s:
        return '-'
    if len(s) > 4:
        return s[:4] + '****'
    return '****'

def normalize_diagnosis_text(raw):
    if not raw or str(raw).strip() in ['-', '', 'None']:
        return '-'
    cleaned = re.sub(r'\s+', ' ', str(raw).replace('\n', ' ')).strip()
    # Rapikan salah ketik umum
    cleaned = re.sub(r'\banemi\b', 'Anemia', cleaned, flags=re.I)
    cleaned = re.sub(r'\bdispepsia\b', 'Dyspepsia', cleaned, flags=re.I)
    cleaned = re.sub(r'\bpempenigus\b', 'Pemfigus', cleaned, flags=re.I)
    cleaned = re.sub(r'\bvugaris\b', 'Vulgaris', cleaned, flags=re.I)
    cleaned = re.sub(r'\bckd\b', 'CKD', cleaned, flags=re.I)
    cleaned = re.sub(r'\baki\b', 'AKI', cleaned, flags=re.I)
    cleaned = re.sub(r'\bdm\b', 'DM', cleaned, flags=re.I)
    cleaned = re.sub(r'\bchf\b', 'CHF', cleaned, flags=re.I)
    cleaned = re.sub(r'\bht\b', 'HT', cleaned, flags=re.I)
    return cleaned

def normalize_doctor(raw):
    if not raw or str(raw).strip() in ['-', '', 'None']:
        return '-'
    cleaned = str(raw).strip()
    first_line = re.sub(r'\s+', ' ', cleaned.split('\n')[0]).strip()
    if first_line.upper() in ['DOKTER', 'DOKTER (DPJP)', 'DPJP']:
        return '-'
    u = first_line.upper()
    for k, v in DOCTOR_CANONICAL.items():
        if k in u:
            return v
    return first_line

def clean_insurance(raw):
    if not raw or str(raw).strip() in ['-', '', 'None']:
        return 'BPJS Kelas 3'
    u = re.sub(r'\s+', ' ', str(raw).strip()).upper()
    if u == 'JAMINAN':
        return '-'
    if 'BPJS' in u and ('1' in u or 'I ' in u): return 'BPJS Kelas 1'
    if 'BPJS' in u and ('2' in u or 'II' in u): return 'BPJS Kelas 2'
    if 'BPJS' in u and ('3' in u or 'III' in u): return 'BPJS Kelas 3'
    if 'BANSOS' in u or 'JAMKESDA' in u or 'SKTM' in u: return 'Bansos / Jamkesda'
    if 'UMUM' in u or 'MANDIRI' in u: return 'Umum / Mandiri'
    if 'ASURANSI' in u or 'SWASTA' in u or 'JASA RAHARJA' in u: return 'Asuransi Swasta'
    if 'BPJS' in u or 'SEP' in u: return 'BPJS Kelas 3'
    return re.sub(r'\s+', ' ', str(raw).strip())

def excel_date_to_str(val):
    if not val:
        return ""
    val_str = str(val).strip()
    try:
        f = float(val_str)
        if 40000 < f < 50000:
            d = date(1899, 12, 30) + timedelta(days=int(f))
            return d.strftime("%d/%m/%Y")
    except:
        pass
    return val_str

def parse_shared_strings(z):
    shared_strings = []
    if "xl/sharedStrings.xml" not in z.namelist():
        return shared_strings
    xml_data = z.read("xl/sharedStrings.xml")
    root = ET.fromstring(xml_data)
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    for si in root.findall(f"{ns}si"):
        text_parts = [t.text for t in si.iter(f"{ns}t") if t.text]
        shared_strings.append("".join(text_parts))
    return shared_strings

def load_style_fills(z):
    styles_root = ET.fromstring(z.read('xl/styles.xml'))
    ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    fills = styles_root.findall('ns:fills/ns:fill', ns)
    fill_colors = []
    for f in fills:
        pf = f.find('ns:patternFill', ns)
        if pf is not None:
            fg = pf.find('ns:fgColor', ns)
            fill_colors.append(fg.attrib if fg is not None else None)
        else:
            fill_colors.append(None)
    
    xfs = styles_root.findall('ns:cellXfs/ns:xf', ns)
    xf_to_color = {}
    for i, xf in enumerate(xfs):
        fid = int(xf.get('fillId', 0))
        fcol = fill_colors[fid] if fid < len(fill_colors) else None
        if fcol:
            rgb = fcol.get('rgb')
            if rgb and rgb not in IGNORE_COLORS and rgb not in HEADER_COLORS:
                xf_to_color[i] = rgb
            else:
                xf_to_color[i] = None
        else:
            xf_to_color[i] = None
    return xf_to_color

def calculate_ews(patient_notes, diagnosis=""):
    """
    Calculate Royal College of Physicians NEWS2 / EWS Score from clinical telemetry.
    Returns: {score: int, level: 'low'|'medium'|'high', params: dict}
    """
    combined = f"{diagnosis} {patient_notes.get('pagi', '')} {patient_notes.get('sore', '')} {patient_notes.get('malam', '')}".upper()
    
    # Defaults
    rr = 18
    spo2 = 98
    o2_therapy = False
    sys_bp = 120
    hr = 80
    consciousness = 'Alert' # Alert, Voice, Pain, Unresponsive
    temp = 36.8

    # Extract Respirations
    rr_m = re.search(r'(?:RR|RESP|PERNAPASAN)\s*[:=]?\s*(\d{2})', combined)
    if rr_m: rr = int(rr_m.group(1))

    # Extract SpO2
    spo2_m = re.search(r'(?:SPO2|SATURASI)\s*[:=]?\s*(\d{2,3})%?', combined)
    if spo2_m: spo2 = int(spo2_m.group(1))

    # Oxygen therapy
    if any(k in combined for k in ['NASAL KANUL', 'NK ', 'NRM', 'O2 ', 'OKSIGEN', 'VENTILATOR']):
        o2_therapy = True

    # Blood Pressure (Systolic)
    bp_m = re.search(r'(?:TD|TENSI|BP)\s*[:=]?\s*(\d{2,3})\s*/\s*(\d{2,3})', combined)
    if bp_m: sys_bp = int(bp_m.group(1))

    # Heart Rate
    hr_m = re.search(r'(?:NADI|HR|PULSE)\s*[:=]?\s*(\d{2,3})', combined)
    if hr_m: hr = int(hr_m.group(1))

    # Temperature
    t_m = re.search(r'(?:SUHU|TEMP|T)\s*[:=]?\s*(\d{2}[.,]\d{1,2})', combined)
    if t_m: temp = float(t_m.group(1).replace(',', '.'))

    # Consciousness / Neurological
    if any(k in combined for k in ['MERACAU', 'DELIRIUM', 'GELISAH', 'SOPOR', 'APATIS', 'SOMNOLEN']):
        consciousness = 'Confused / Altered'
    elif any(k in combined for k in ['KOMA', 'UNRESPONSIVE']):
        consciousness = 'Unresponsive'

    # Score calculation
    score = 0
    # RR
    if rr <= 8 or rr >= 25: score += 3
    elif 21 <= rr <= 24: score += 2
    elif 9 <= rr <= 11: score += 1

    # SpO2
    if spo2 <= 91: score += 3
    elif 92 <= spo2 <= 93: score += 2
    elif 94 <= spo2 <= 95: score += 1

    # O2 therapy
    if o2_therapy: score += 2

    # Systolic BP
    if sys_bp <= 90 or sys_bp >= 220: score += 3
    elif 91 <= sys_bp <= 100: score += 2
    elif 101 <= sys_bp <= 110: score += 1

    # Heart Rate
    if hr <= 40 or hr >= 131: score += 3
    elif 111 <= hr <= 130: score += 2
    elif 41 <= hr <= 50 or 91 <= hr <= 110: score += 1

    # Consciousness
    if consciousness != 'Alert': score += 3

    # Temp
    if temp <= 35.0: score += 3
    elif temp >= 39.1: score += 2
    elif 38.1 <= temp <= 39.0 or 35.1 <= temp <= 36.0: score += 1

    # Clinical condition baseline adjustment
    if any(k in combined for k in ['SYOK', 'KAD', 'HHS', 'EDEMA PULMO', 'APLASTIK']):
        score = max(score, 5)
    elif any(k in combined for k in ['TRANSFUSI', 'ANEMIA GRAVIS', 'MELENA']):
        score = max(score, 3)

    level = 'low'
    if score >= 7: level = 'critical'
    elif score >= 5: level = 'medium'
    elif score >= 1: level = 'low'
    else: level = 'normal'

    return {
        "score": score,
        "level": level,
        "parameters": {
            "rr": rr,
            "spo2": spo2,
            "o2_therapy": o2_therapy,
            "sys_bp": sys_bp,
            "hr": hr,
            "temp": temp,
            "consciousness": consciousness
        }
    }

def categorize_diagnosis(diag_str):
    u = (diag_str or '').upper()
    if any(k in u for k in ["CKD", "AKI", "GINJAL", "NEFRO", "RENAL", "URETER", "HIDRONEFROSIS", "HEMATURIA", "BSK", "GNA"]):
        return "Nefrologi & Urologi"
    if any(k in u for k in ["CA ", "CANCER", "CARCINOMA", "TUMOR", "MYELOMA", "LEUKEMIA", "AML", "CML", "APLASTIK", "THALASEMIA", "ITP", "MALIGNANCY"]):
        return "Hematologi & Onkologi"
    if any(k in u for k in ["DM", "DIABETES", "HIPERKALEMIA", "HIPONATREMIA", "KAD", "HHS", "ANASARKA", "EDEMA", "ELEKTROLIT", "RTA", "HIPOALBUMIN"]):
        return "Penyakit Dalam (Metabolik)"
    if any(k in u for k in ["APP", "ABDOMEN", "ABD PAIN", "CHOLE", "KOLE", "HEPATIS", "PANCREA", "ILEUS", "HEMATOCHEZIA", "VOMITUS", "MELENA", "GASTRO", "DYSPEPSIA"]):
        return "Gastroenterologi & Digestif"
    if any(k in u for k in ["PNEUMONIA", "TB", "SESAK", "THORAX", "EFFUSI", "BRONKITIS"]):
        return "Pulmonologi / Paru"
    if any(k in u for k in ["SPONDIL", "OA ", "FRACTURE", "FRAKTUR", "TKR", "ORIF", "TENDON", "SPINE"]):
        return "Ortopedi & Traumatologi"
    if any(k in u for k in ["PJK", "CHF", "JANTUNG", "TROPONIN", "ECHO"]):
        return "Kardiologi"
    if any(k in u for k in ["PEMFIGUS", "KULIT"]):
        return "Dermatologi"
    return "Penyakit Dalam (Umum)"

def extract_tags(notes_dict, diag_str, is_empty=False, is_colored=False):
    if is_empty: return []
    tags = []
    combined = f"{diag_str}\n{notes_dict.get('pagi', '')}\n{notes_dict.get('sore', '')}\n{notes_dict.get('malam', '')}".upper()

    if any(k in combined for k in ["PULANG HARI INI", "ACC BLPL", "ACC PULANG", "ACC RAWAT JALAN", "KRS HARI INI"]) or re.search(r'\b(?:BLPL\s+JAM|PULANG\s*$|PULANG\s*\n)\b', combined):
        tags.append({"label": "Pulang Hari Ini", "color": "emerald"})
    elif any(k in combined for k in ["PULANG", "BLPL", "KRS", "RAJAL", "RENCANA PULANG"]):
        tags.append({"label": "Rencana Pulang", "color": "green"})

    if any(k in combined for k in ["HD", "HEMODIALISA", "CDL", "CIMINO", "CUCI DARAH"]):
        tags.append({"label": "Hemodialisa (HD)", "color": "purple"})
    if any(k in combined for k in ["TRANSFUSI", "PRC", "TF ", "TF:", "KOLF", "TC ", "TROMBO"]):
        tags.append({"label": "Transfusi Darah", "color": "red"})
    if any(k in combined for k in ["POST OP", "PRO OP", "POD", "OPERASI", "DEBRIDEMENT", "BEDAH"]):
        tags.append({"label": "Bedah / Operasi", "color": "orange"})
    if any(k in combined for k in ["CA ", "CANCER", "KANKER", "CHEMO", "KEMO", "ONKOLOGI", "RADIOTERAPI"]):
        tags.append({"label": "Onkologi", "color": "pink"})
    if any(k in combined for k in ["PUASA", "PRE OP", "PRE-OP"]):
        tags.append({"label": "Puasa Pre-Op", "color": "amber"})
    if any(k in combined for k in ["ISOLASI"]):
        tags.append({"label": "Bed Isolasi", "color": "purple"})

    return tags

def parse_patient_block(row_cells, current_room, current_iso_date, xf_to_color):
    """
    Parses a single row into standard Patient Model
    Row format:
    A: KAMAR
    B: BED
    C: TGL MASUK
    D: NAMA (+ No. MR)
    E: JAMINAN
    F: DOKTER (DPJP)
    G: DIAGNOSA
    H: PAGI
    I: SORE
    J: MALAM
    """
    bed_raw = str(row_cells.get('B') or '').strip()
    kamar_raw = str(row_cells.get('A') or current_room or '').strip()
    tgl_raw = excel_date_to_str(row_cells.get('C'))
    nama_raw = str(row_cells.get('D') or '').strip()
    jaminan_raw = str(row_cells.get('E') or '').strip()
    dokter_raw = str(row_cells.get('F') or '').strip()
    diag_raw = str(row_cells.get('G') or '').strip()
    pagi = str(row_cells.get('H') or '').strip()
    sore = str(row_cells.get('I') or '').strip()
    malam = str(row_cells.get('J') or '').strip()

    notes = {'pagi': pagi, 'sore': sore, 'malam': malam}
    is_colored = bool(row_cells.get('_isColored'))
    color_hex = row_cells.get('_colorHex')

    # Normalize bed identifier
    bed_clean = bed_raw.replace('\n', ' ').strip()
    # E.g. KAKAP 1.1 -> 1.1
    m_b = re.search(r'(\d{1,2}\.\d|ISOLASI)', bed_clean, re.IGNORECASE)
    bed_id = m_b.group(1).upper() if m_b else bed_clean

    # Determine room name & team directly from bed identifier to prevent merged/empty Column A bleed
    m_r = re.search(r'KAKAP\s*(\d{1,2})', bed_clean, re.IGNORECASE)
    if not m_r and '.' in bed_id:
        m_r = re.search(r'(\d{1,2})\.', bed_id)

    if m_r:
        k_num = int(m_r.group(1))
        gender_hint = "♂" if k_num in [1, 5, 6, 7, 9] else "♀"
        room_name = f"Kakap {k_num} ({gender_hint})"
        team = "Tim II" if (6 <= k_num <= 10) else "Tim I"
    elif 'ISOLASI' in bed_clean.upper() or 'ISOLASI' in bed_id:
        room_name = "Isolasi"
        team = "Tim I"
    else:
        room_name = kamar_raw.replace('\n', ' ').strip()
        team = "Tim I"

    # Empty bed detection
    is_empty = False
    status = "Terisi"
    if (not nama_raw and not diag_raw) or any(k in (bed_raw + nama_raw).upper() for k in ["KOSONG", "RUSAK", "BAU"]):
        is_empty = True
        status = "Kosong"
    elif "ANTRIAN" in nama_raw.upper() and not diag_raw:
        status = "Antrian / Transit"

    # Name and MR parsing
    clean_name = nama_raw
    mr_no = ""
    age = ""
    gender = "L" if any(clean_name.startswith(p) for p in ["Tn.", "An. L", "By. L", "Sdr."]) else "P"

    mr_match = re.search(r"(?:NO\.?\s*MR|MR)\s*[:.]?\s*([0-9]+)", nama_raw, re.IGNORECASE)
    if mr_match:
        mr_no = mr_match.group(1)
        clean_name = re.sub(r"(?:NO\.?\s*MR|MR)\s*[:.]?\s*[0-9]+", "", clean_name, flags=re.IGNORECASE).strip()

    age_match = re.search(r"/\s*([0-9]+)\s*(?:th|tahun|yahun)?", clean_name, re.IGNORECASE)
    if age_match:
        age = age_match.group(1) + " th"
        clean_name = re.sub(r"/\s*[0-9]+\s*(?:th|tahun|yahun)?", "", clean_name, flags=re.IGNORECASE).strip()

    clean_name = re.sub(r"\s+", " ", clean_name).strip()
    if not clean_name and not is_empty:
        clean_name = f"Pasien Bed {bed_id}"

    # LOS calculation
    los_days = 1
    tgl_masuk_clean = tgl_raw
    try:
        m_d = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", tgl_raw)
        if m_d:
            p1, p2, year = int(m_d.group(1)), int(m_d.group(2)), int(m_d.group(3))
            if year < 100: year += 2000
            curr_d = datetime.fromisoformat(current_iso_date).date()
            
            # Try standard day=p1, month=p2 first
            admit_date = None
            try:
                cand1 = date(year, p2, p1)
                diff1 = (curr_d - cand1).days
                if 0 <= diff1 <= 90:
                    admit_date = cand1
            except:
                pass
            
            # If invalid or diff too large (e.g. US date flip), try day=p2, month=p1
            if not admit_date:
                try:
                    cand2 = date(year, p1, p2)
                    diff2 = (curr_d - cand2).days
                    if 0 <= diff2 <= 90:
                        admit_date = cand2
                except:
                    pass
            
            if not admit_date:
                admit_date = date(year, p2, p1)
                
            diff = (curr_d - admit_date).days
            los_days = max(1, diff + 1)
            tgl_masuk_clean = admit_date.strftime("%d/%m/%Y")
    except:
        pass

    dpjp_primary = normalize_doctor(dokter_raw)
    insurance = clean_insurance(jaminan_raw)
    diag_clean = normalize_diagnosis_text(diag_raw)
    category = categorize_diagnosis(diag_clean) if not is_empty else "-"
    tags = extract_tags(notes, diag_clean, is_empty, is_colored)
    ews = calculate_ews(notes, diag_clean) if not is_empty else {"score": 0, "level": "normal", "parameters": {}}

    # Deteksi 4 jenis status keluar pasien (BLPL, APS, Pindah, Meninggal) dari warna kolom status (bukan kolom kamar) & catatan klinis
    combined_notes_u = f"{diag_clean}\n{pagi}\n{sore}\n{malam}".upper()
    discharge_type = None
    status_color = None
    if not is_empty:
        if (color_hex in COLOR_STATUS_MAP['meninggal']) or re.search(r'\b(MENINGGAL|EXPIRED|DOA|WAFAT|TUTUP USIA)\b', combined_notes_u):
            discharge_type = 'meninggal'
            status_color = 'red'
            status = 'Meninggal'
        elif (color_hex in COLOR_STATUS_MAP['aps']) or re.search(r'\b(PULANG APS|ATAS PERMINTAAN SENDIRI|PULANG PAKSA|\bAPS\b)\b', combined_notes_u):
            discharge_type = 'aps'
            status_color = 'orange'
            status = 'Pulang APS'
        elif (color_hex in COLOR_STATUS_MAP['pindah']) or re.search(r'\b(PINDAH RUANG|TRANSFER KE|PINDAH ICU|PINDAH HCU|PINDAH PJT|PINDAH KE RUANG)\b', combined_notes_u):
            discharge_type = 'pindah'
            status_color = 'yellow'
            status = 'Pindah / Transfer'
        elif (color_hex in COLOR_STATUS_MAP['blpl']) or any(t['label'] == 'Pulang Hari Ini' for t in tags):
            discharge_type = 'blpl'
            status_color = 'green'
            status = 'Pulang BLPL'

    is_discharged = discharge_type is not None
    if is_discharged:
        if not nama_raw or nama_raw == '-' or 'BED KOSONG' in nama_raw.upper():
            is_empty = True

    return {
        "bed": bed_id,
        "room": room_name,
        "team": team,
        "status": status,
        "dischargeType": discharge_type,
        "statusColor": status_color,
        "isEmpty": is_empty,
        "isDischargedToday": is_discharged,
        "dischargeColor": color_hex,
        "name": clean_name if (not is_empty or is_discharged) else "Bed Kosong",
        "mrNo": mr_no,
        "gender": gender if not is_empty else "-",
        "age": age,
        "admissionDate": tgl_masuk_clean if not is_empty else "-",
        "los": los_days if not is_empty else 0,
        "insurance": insurance if not is_empty else "-",
        "doctor": dpjp_primary if not is_empty else "-",
        "doctorPrimary": dpjp_primary if not is_empty else "-",
        "diagnosis": diag_clean if not is_empty else "-",
        "category": category,
        "notes": notes,
        "tags": tags,
        "ews": ews
    }

def get_full_41_bed_layout():
    """Generates standard template of 41 beds for Ruang Kakap."""
    beds = []
    # Kakap 1 to 10 @ 4 beds
    for k in range(1, 11):
        room_name = f"Kakap {k}"
        gender_hint = "♂" if k in [1, 5, 6, 7, 9] else "♀"
        room_label = f"{room_name} ({gender_hint})"
        team = "Tim I" if k <= 5 else "Tim II"
        for b in range(1, 5):
            beds.append({
                "bed": f"{k}.{b}",
                "room": room_label,
                "team": team,
                "status": "Kosong",
                "isEmpty": True,
                "isDischargedToday": False,
                "name": "Bed Kosong",
                "mrNo": "",
                "gender": "-",
                "age": "",
                "admissionDate": "-",
                "los": 0,
                "insurance": "-",
                "doctor": "-",
                "doctorPrimary": "-",
                "diagnosis": "-",
                "category": "-",
                "notes": {"pagi": "", "sore": "", "malam": ""},
                "tags": [],
                "ews": {"score": 0, "level": "normal", "parameters": {}}
            })
    # Isolasi (Bed 41)
    beds.append({
        "bed": "ISOLASI",
        "room": "Isolasi (Khusus)",
        "team": "Tim I",
        "status": "Kosong",
        "isEmpty": True,
        "isDischargedToday": False,
        "name": "Bed Kosong",
        "mrNo": "",
        "gender": "-",
        "age": "",
        "admissionDate": "-",
        "los": 0,
        "insurance": "-",
        "doctor": "-",
        "doctorPrimary": "-",
        "diagnosis": "-",
        "category": "-",
        "notes": {"pagi": "", "sore": "", "malam": ""},
        "tags": [],
        "ews": {"score": 0, "level": "normal", "parameters": {}}
    })
    return beds

def parse_day_sheet(z, target_file, shared_strings, xf_to_color, iso_date):
    """Parses a full day sheet into patients list and sensus metrics."""
    xml_data = z.read(target_file)
    sheet_root = ET.fromstring(xml_data)
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

    # First pass: read rows
    rows_data = {}
    for row in sheet_root.findall(f".//{ns}row"):
        r_idx = int(row.attrib.get('r'))
        cells = {}
        row_colored = False
        row_color_hex = None
        for c in row.findall(f"{ns}c"):
            col_letter = re.match(r"([A-Z]+)", c.attrib.get('r', '')).group(1)
            t = c.attrib.get('t')
            s_id = int(c.attrib.get('s', 0))
            col_info = xf_to_color.get(s_id)
            # Warna status hanya dibaca dari kolom data pasien (D, G, H, I, J), BUKAN kolom kamar (A/B)
            if col_info and col_letter in ('D', 'G', 'H', 'I', 'J'):
                row_colored = True
                row_color_hex = col_info
            v_el = c.find(f"{ns}v")
            val = v_el.text if v_el is not None else None
            if t == 's' and val is not None:
                val = shared_strings[int(val)]
            cells[col_letter] = val
        if cells:
            cells['_isColored'] = row_colored
            cells['_colorHex'] = row_color_hex
            rows_data[r_idx] = cells

    # Split between patient rows and sensus rows
    sensus_start_row = 9999
    for r_idx in sorted(rows_data.keys()):
        g_val = str(rows_data[r_idx].get('G') or '').strip().upper()
        if 'SENSUS' in g_val or 'PERAWAT 1' in g_val or 'PASIEN AWAL' in g_val:
            sensus_start_row = r_idx
            break

    # Parse Patients
    patients_parsed = []
    current_kamar = ""
    for r_idx in sorted(rows_data.keys()):
        if r_idx < 4: continue  # Row 4 adalah Kakap 1.1 (jangan dilewati)
        if r_idx >= sensus_start_row: break
        c = rows_data[r_idx]
        if c.get('A'):
            current_kamar = str(c.get('A')).strip()
        bed_val = str(c.get('B') or '').strip()
        nama_val = str(c.get('D') or '').strip()
        dok_val = str(c.get('F') or '').strip().upper()
        # Lewati baris judul header tabel (misal: KAMAR | BED | TGL MASUK | NAMA | JAMINAN | DOKTER)
        if bed_val.upper() == 'BED' or nama_val.upper() in ('NAMA', 'NAMA PASIEN') or dok_val in ('DOKTER', 'DOKTER (DPJP)'):
            continue
        if bed_val or nama_val:
            p = parse_patient_block(c, current_kamar, iso_date, xf_to_color)
            if p: patients_parsed.append(p)

    # Standardize to exactly 41 beds layout
    standard_layout = get_full_41_bed_layout()
    bed_map = {}
    for p in patients_parsed:
        b_key = str(p['bed']).upper()
        # Clean matching e.g. 1.1 or ISOLASI
        for std in standard_layout:
            if std['bed'].upper() == b_key or std['bed'].upper() in b_key:
                bed_map[std['bed']] = p
                break

    final_patients = []
    for std in standard_layout:
        if std['bed'] in bed_map:
            final_patients.append(bed_map[std['bed']])
        else:
            final_patients.append(std)

    # Parse SENSUS section
    sensus = {
        "perawat": {"pagi": [], "sore": [], "malam": []},
        "pasienAwal": {"pagi": 0, "sore": 0, "malam": 0},
        "pasienBaru": {"pagi": 0, "sore": 0, "malam": 0},
        "pulang": {"pagi": 0, "sore": 0, "malam": 0},
        "pindah": {"pagi": 0, "sore": 0, "malam": 0},
        "meninggal": {"pagi": 0, "sore": 0, "malam": 0},
        "total": {"pagi": 0, "sore": 0, "malam": 0},
        "bedKosong": {"pagi": 0, "sore": 0, "malam": 0},
        "bedKosongText": {"pagi": "", "sore": "", "malam": ""},
        "bedKosongDetail": {
            "pagi": {"total": 0, "pria": 0, "wanita": 0, "isolasi": 0},
            "sore": {"total": 0, "pria": 0, "wanita": 0, "isolasi": 0},
            "malam": {"total": 0, "pria": 0, "wanita": 0, "isolasi": 0}
        },
        "bedRusak": {"pagi": 4, "sore": 4, "malam": 4},
        "bedRusakText": {"pagi": "4 (KAKAP 9)", "sore": "4 (KAKAP 9)", "malam": "4 (KAKAP 9)"},
        "isolasi": {"pagi": "KOSONG", "sore": "KOSONG", "malam": "KOSONG"}
    }

    def safe_int(v):
        try:
            m = re.search(r'\d+', str(v or ''))
            return int(m.group(0)) if m else 0
        except:
            return 0

    for r_idx in range(sensus_start_row, sensus_start_row + 22):
        if r_idx not in rows_data: continue
        c = rows_data[r_idx]
        label = str(c.get('G') or '').strip()
        h_val, i_val, j_val = c.get('H'), c.get('I'), c.get('J')

        if "Perawat" in label:
            if h_val: sensus["perawat"]["pagi"].append(str(h_val).strip())
            if i_val: sensus["perawat"]["sore"].append(str(i_val).strip())
            if j_val: sensus["perawat"]["malam"].append(str(j_val).strip())
        elif "Pasien awal" in label:
            sensus["pasienAwal"]["pagi"] = safe_int(h_val)
            sensus["pasienAwal"]["sore"] = safe_int(i_val)
            sensus["pasienAwal"]["malam"] = safe_int(j_val)
        elif "Pasien baru" in label:
            sensus["pasienBaru"]["pagi"] = safe_int(h_val)
            sensus["pasienBaru"]["sore"] = safe_int(i_val)
            sensus["pasienBaru"]["malam"] = safe_int(j_val)
        elif "Pulang" in label:
            sensus["pulang"]["pagi"] += safe_int(h_val)
            sensus["pulang"]["sore"] += safe_int(i_val)
            sensus["pulang"]["malam"] += safe_int(j_val)
        elif "Pindah" in label:
            sensus["pindah"]["pagi"] = safe_int(h_val)
            sensus["pindah"]["sore"] = safe_int(i_val)
            sensus["pindah"]["malam"] = safe_int(j_val)
        elif "Meninggal" in label:
            sensus["meninggal"]["pagi"] = safe_int(h_val)
            sensus["meninggal"]["sore"] = safe_int(i_val)
            sensus["meninggal"]["malam"] = safe_int(j_val)
        elif label == "Total":
            sensus["total"]["pagi"] = safe_int(h_val)
            sensus["total"]["sore"] = safe_int(i_val)
            sensus["total"]["malam"] = safe_int(j_val)
        elif "Bed tidak dapat dipakai" in label:
            sensus["bedRusak"]["pagi"] = safe_int(h_val) or 4
            sensus["bedRusak"]["sore"] = safe_int(i_val) or 4
            sensus["bedRusak"]["malam"] = safe_int(j_val) or 4
            sensus["bedRusakText"]["pagi"] = str(h_val or '4 (KAKAP 9)').strip()
            sensus["bedRusakText"]["sore"] = str(i_val or '4 (KAKAP 9)').strip()
            sensus["bedRusakText"]["malam"] = str(j_val or '4 (KAKAP 9)').strip()
        elif "Bed kosong" in label:
            sensus["bedKosongText"]["pagi"] = str(h_val or '').strip()
            sensus["bedKosongText"]["sore"] = str(i_val or '').strip()
            sensus["bedKosongText"]["malam"] = str(j_val or '').strip()
            for sh_k, sh_v in [('pagi', h_val), ('sore', i_val), ('malam', j_val)]:
                raw_txt = str(sh_v or '').strip()
                m_tot = re.search(r'^\s*(\d+)', raw_txt)
                tot_c = int(m_tot.group(1)) if m_tot else safe_int(raw_txt)
                sensus["bedKosong"][sh_k] = tot_c
                m_l = re.search(r'(\d+)\s*(?:L|Laki)', raw_txt, re.I)
                m_p = re.search(r'(\d+)\s*(?:P|Perempuan)', raw_txt, re.I)
                sensus["bedKosongDetail"][sh_k]["total"] = tot_c
                if m_l: sensus["bedKosongDetail"][sh_k]["pria"] = int(m_l.group(1))
                if m_p: sensus["bedKosongDetail"][sh_k]["wanita"] = int(m_p.group(1))
        elif "ISOLASI" in label:
            sensus["isolasi"]["pagi"] = str(h_val or 'KOSONG').strip()
            sensus["isolasi"]["sore"] = str(i_val or 'KOSONG').strip()
            sensus["isolasi"]["malam"] = str(j_val or 'KOSONG').strip()

    # Split patients by Team
    tim1_patients = [p for p in final_patients if p['team'] == 'Tim I']
    tim2_patients = [p for p in final_patients if p['team'] == 'Tim II']

    # Occupied count
    occ_total = sum(1 for p in final_patients if not p['isEmpty'])
    occ_t1 = sum(1 for p in tim1_patients if not p['isEmpty'])
    occ_t2 = sum(1 for p in tim2_patients if not p['isEmpty'])

    # Fill fallback sensus totals if missing
    if sensus["total"]["pagi"] == 0: sensus["total"]["pagi"] = occ_total
    if sensus["total"]["sore"] == 0: sensus["total"]["sore"] = sensus["total"]["pagi"]
    if sensus["total"]["malam"] == 0: sensus["total"]["malam"] = sensus["total"]["sore"]

    # Fallback pasienAwal for morning shift if empty: total - baru + pulang + pindah + meninggal
    if sensus["pasienAwal"]["pagi"] == 0:
        sensus["pasienAwal"]["pagi"] = max(0, sensus["total"]["pagi"] - sensus["pasienBaru"]["pagi"] + sensus["pulang"]["pagi"] + sensus["pindah"]["pagi"] + sensus["meninggal"]["pagi"])
    if sensus["pasienAwal"]["sore"] == 0:
        sensus["pasienAwal"]["sore"] = sensus["total"]["pagi"]
    if sensus["pasienAwal"]["malam"] == 0:
        sensus["pasienAwal"]["malam"] = sensus["total"]["sore"]

    # Dynamic free bed calculation from actual beds
    male_empty = sum(1 for p in final_patients if p.get('isEmpty') and ('♂' in p.get('room', '') or re.search(r'\bKAKAP\s+(1|5|6|7|9)\b', p.get('room', ''), re.I)))
    female_empty = sum(1 for p in final_patients if p.get('isEmpty') and ('♀' in p.get('room', '') or re.search(r'\bKAKAP\s+(2|3|4|8|10)\b', p.get('room', ''), re.I)))
    iso_patient = next((p for p in final_patients if 'ISOLASI' in p.get('room', '').upper() or p.get('bed') == 'ISOLASI'), None)
    iso_empty = 1 if (iso_patient and iso_patient.get('isEmpty')) else 0

    for sh in ["pagi", "sore", "malam"]:
        raw_sh_txt = sensus["bedKosongText"][sh]
        if raw_sh_txt == "0" or (sensus["bedKosong"][sh] == 0 and "0" in raw_sh_txt):
            sensus["bedKosongDetail"][sh]["total"] = 0
            sensus["bedKosongDetail"][sh]["pria"] = 0
            sensus["bedKosongDetail"][sh]["wanita"] = 0
            sensus["bedKosongDetail"][sh]["isolasi"] = 0
        else:
            # Gunakan status aktual isolasi dari bed map
            sensus["bedKosongDetail"][sh]["isolasi"] = iso_empty
            if sensus["bedKosongDetail"][sh]["pria"] == 0 and sensus["bedKosongDetail"][sh]["wanita"] == 0:
                sensus["bedKosongDetail"][sh]["pria"] = male_empty
                sensus["bedKosongDetail"][sh]["wanita"] = female_empty
                sensus["bedKosongDetail"][sh]["isolasi"] = iso_empty
                sensus["bedKosong"][sh] = male_empty + female_empty + iso_empty
                sensus["bedKosongDetail"][sh]["total"] = sensus["bedKosong"][sh]

    # Calculate summary
    empty_total = TOTAL_BEDS - occ_total
    bor_total = round((occ_total / TOTAL_BEDS) * 100, 1)
    bor_t1 = round((occ_t1 / TIM1_BEDS) * 100, 1)
    bor_t2 = round((occ_t2 / TIM2_BEDS) * 100, 1)

    # Tag counts
    tag_counts = defaultdict(int)
    for p in final_patients:
        for t in p.get('tags', []):
            tag_counts[t['label']] += 1

    summary = {
        "totalBeds": TOTAL_BEDS,
        "capacityTim1": TIM1_BEDS,
        "capacityTim2": TIM2_BEDS,
        "capacityA": TIM1_BEDS,
        "capacityB": TIM2_BEDS,
        "occupied": occ_total,
        "empty": empty_total,
        "bor": bor_total,
        "borTim1": bor_t1,
        "borTim2": bor_t2,
        "borA": bor_t1,
        "borB": bor_t2,
        "occTim1": occ_t1,
        "occTim2": occ_t2,
        "occA": occ_t1,
        "occB": occ_t2,
        "emptyTim1": TIM1_BEDS - occ_t1,
        "emptyTim2": TIM2_BEDS - occ_t2,
        "emptyA": TIM1_BEDS - occ_t1,
        "emptyB": TIM2_BEDS - occ_t2,
        "dischargedToday": sum(1 for p in final_patients if p.get('isDischargedToday')),
        "tagCounts": dict(tag_counts),
        "criticalEWS": sum(1 for p in final_patients if p.get('ews', {}).get('level') == 'critical'),
        "mediumEWS": sum(1 for p in final_patients if p.get('ews', {}).get('level') == 'medium')
    }

    room_notes = {
        "kakap-8": {"type": "warning", "text": "AC Panas (kamar 8 klg pasien setuju kondisi)"},
        "kakap-9": {"type": "warning", "text": "AC Panas · Kamar BAU/Rusak — Tidak aktif digunakan"}
    }
    fasilitas_notes = [
        "Lift luar mati, lift dalam sering error (pintu terbuka sendiri)"
    ]
    antrean_dict = {
        "pagi": [],
        "sore": [],
        "malam": []
    }

    return {
        "date": iso_date,
        "patients": final_patients,
        "tim1": tim1_patients,
        "tim2": tim2_patients,
        "eg2a": tim1_patients,
        "eg2b": tim2_patients,
        "summary": summary,
        "sensus": sensus,
        "roomNotes": room_notes,
        "fasilitasNotes": fasilitas_notes,
        "antrean": antrean_dict
    }

def build_data(download=False):
    if download:
        print(f"[INFO] Downloading latest spreadsheet from Google Sheets...")
        urllib.request.urlretrieve(SPREADSHEET_URL, XLSX_PATH)
        print(f"[INFO] Downloaded successfully: {os.path.getsize(XLSX_PATH)} bytes")

    if not os.path.exists(XLSX_PATH):
        raise FileNotFoundError(f"File {XLSX_PATH} not found.")

    print(f"[INFO] Processing {XLSX_PATH}...")
    with zipfile.ZipFile(XLSX_PATH, 'r') as z:
        shared_strings = parse_shared_strings(z)
        xf_to_color = load_style_fills(z)

        # Get sheet relationships
        rels_xml = z.read('xl/_rels/workbook.xml.rels')
        r_root = ET.fromstring(rels_xml)
        rel_map = {rel.attrib['Id']: rel.attrib['Target'] for rel in r_root}

        wb_root = ET.fromstring(z.read('xl/workbook.xml'))
        day_sheets = []
        for s in wb_root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet'):
            name = s.attrib.get('name')
            rid = s.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            target = 'xl/' + rel_map[rid].lstrip('/')

            # Skip Petunjuk and Daftar Perawat
            if any(k in name.upper() for k in ['PETUNJUK', 'DAFTAR PERAWAT', 'DROPDOWN', 'MASTER']):
                continue

            # Read row 2 for date
            xml_data = z.read(target)
            s_root = ET.fromstring(xml_data)
            texts = []
            for row in s_root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
                if int(row.attrib.get('r', 0)) > 3: break
                for c in row.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                    t = c.attrib.get('t')
                    v_el = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                    if v_el is not None and v_el.text:
                        val = v_el.text
                        if t == 's': val = shared_strings[int(val)]
                        texts.append(str(val))
            combined_txt = ' '.join(texts)
            # Prioritaskan nama tab sheet karena cell A2 seringkali copy-paste dari hari sebelumnya
            m_tab = re.search(r'(\d{1,2})(\d{2})(202\d)', name)
            iso_d = None
            if m_tab:
                d, mth, y = int(m_tab.group(1)), int(m_tab.group(2)), int(m_tab.group(3))
                iso_d = f"{y:04d}-{mth:02d}-{d:02d}"
            else:
                m = re.search(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})', combined_txt)
                if m:
                    d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    iso_d = f"{y:04d}-{mth:02d}-{d:02d}"

            if iso_d:
                day_sheets.append((iso_d, name, target))

    day_sheets.sort(key=lambda x: x[0])
    print(f"[INFO] Found {len(day_sheets)} day sheet(s): {[s[0] for s in day_sheets]}")

    recent_days = {}
    history = []
    all_dates = []

    # Parse each sheet
    with zipfile.ZipFile(XLSX_PATH, 'r') as z:
        for iso_d, name, target in day_sheets:
            print(f"  -> Parsing {iso_d} (Sheet: {name})...")
            day_data = parse_day_sheet(z, target, shared_strings, xf_to_color, iso_d)
            recent_days[iso_d] = day_data
            all_dates.append(iso_d)
            history.append({
                "date": iso_d,
                "occTim1": day_data["summary"]["occTim1"],
                "occTim2": day_data["summary"]["occTim2"],
                "totalOcc": day_data["summary"]["occupied"],
                "totalBeds": TOTAL_BEDS,
                "bor": day_data["summary"]["bor"]
            })

    # =========================================================================
    # PERHITUNGAN SENSUS OTOMATIS DARI DATA PASIEN SATU PER SATU (TANPA HARDCODE)
    # 4 jenis pasien keluar dihitung terpisah: BLPL, APS, Pindah, Meninggal
    # =========================================================================
    def patient_identity_key(p):
        mr = re.sub(r'\D', '', str(p.get('mrNo') or ''))
        if len(mr) >= 5:
            return f"MR:{mr}"
        nm = re.sub(r'^(tn\.|ny\.|an\.|by\.|sdr\.|sdri\.|nn\.)\s*', '', str(p.get('name') or '').strip().lower())
        nm = re.sub(r'\s+', ' ', nm).strip()
        return f"NM:{nm}" if nm and nm != 'bed kosong' else ""

    prev_active_map = {}
    discharged_records = []  # list of {date, key, type, los}
    total_blpl = 0
    total_aps = 0
    total_pindah = 0
    total_meninggal = 0
    total_meninggal_gt48 = 0

    for idx_d, iso_d in enumerate(all_dates):
        day_data = recent_days[iso_d]
        patients = day_data["patients"]

        # Deduplikasi pasien aktif pada hari yang sama berdasarkan No. RM
        cur_active_map = {}
        for p in patients:
            if not p.get("isEmpty"):
                pk = patient_identity_key(p)
                if pk:
                    cur_active_map[pk] = p

        occ_total = sum(1 for p in patients if not p.get("isEmpty"))
        occ_t1 = sum(1 for p in patients if not p.get("isEmpty") and p.get("team") == "Tim I")
        occ_t2 = sum(1 for p in patients if not p.get("isEmpty") and p.get("team") == "Tim II")

        # Hitung pasien masuk (baru) & keluar (4 jenis terpisah) dari perbandingan pasien hari ini vs hari sebelumnya
        day_blpl = 0
        day_aps = 0
        day_pindah = 0
        day_meninggal = 0
        day_baru = 0
        already_counted_out = set()

        if idx_d > 0:
            # Pasien baru = ada hari ini, tidak ada kemarin
            for pk in cur_active_map:
                if pk not in prev_active_map:
                    day_baru += 1

            # Pasien keluar = ada kemarin, sudah tidak ada hari ini
            for pk, prev_p in prev_active_map.items():
                if pk not in cur_active_map:
                    dtype = prev_p.get("dischargeType") or "blpl"
                    los_val = max(1, int(prev_p.get("los") or 1))
                    if dtype == "meninggal":
                        day_meninggal += 1
                        if los_val >= 3:
                            total_meninggal_gt48 += 1
                    elif dtype == "aps":
                        day_aps += 1
                    elif dtype == "pindah":
                        day_pindah += 1
                    else:
                        day_blpl += 1
                    discharged_records.append({"date": iso_d, "key": pk, "type": dtype, "los": los_val})
                    already_counted_out.add(pk)

        # Pada hari terakhir, pasien yang sudah bertanda keluar hari ini juga dicatat pada ringkasan harian
        if idx_d == len(all_dates) - 1:
            for pk, cur_p in cur_active_map.items():
                if cur_p.get("dischargeType") and pk not in already_counted_out:
                    dtype = cur_p["dischargeType"]
                    los_val = max(1, int(cur_p.get("los") or 1))
                    if dtype == "meninggal":
                        day_meninggal += 1
                        if los_val >= 3:
                            total_meninggal_gt48 += 1
                    elif dtype == "aps":
                        day_aps += 1
                    elif dtype == "pindah":
                        day_pindah += 1
                    else:
                        day_blpl += 1
                    discharged_records.append({"date": iso_d, "key": pk, "type": dtype, "los": los_val})

        total_blpl += day_blpl
        total_aps += day_aps
        total_pindah += day_pindah
        total_meninggal += day_meninggal

        prev_occ = len(prev_active_map) if idx_d > 0 else occ_total
        day_keluar_total = day_blpl + day_aps + day_pindah + day_meninggal

        # Hitung bed kosong langsung dari denah 41 bed
        male_empty = sum(1 for p in patients if p.get("isEmpty") and ("♂" in p.get("room", "") or re.search(r"\bKAKAP\s+(1|5|6|7|9)\b", p.get("room", ""), re.I)))
        female_empty = sum(1 for p in patients if p.get("isEmpty") and ("♀" in p.get("room", "") or re.search(r"\bKAKAP\s+(2|3|4|8|10)\b", p.get("room", ""), re.I)))
        iso_patient = next((p for p in patients if "ISOLASI" in p.get("room", "").upper() or p.get("bed") == "ISOLASI"), None)
        iso_empty = 1 if (iso_patient and iso_patient.get("isEmpty")) else 0
        free_total = TOTAL_BEDS - occ_total

        s = day_data["sensus"]
        s["pulangBlpl"] = {"pagi": day_blpl, "sore": 0, "malam": 0, "total": day_blpl}
        s["pulangAps"] = {"pagi": day_aps, "sore": 0, "malam": 0, "total": day_aps}
        for sh in ["pagi", "sore", "malam"]:
            s["pasienAwal"][sh] = prev_occ if sh == "pagi" else occ_total
            s["pasienBaru"][sh] = day_baru if sh == "pagi" else 0
            s["pulang"][sh] = (day_blpl + day_aps) if sh == "pagi" else 0
            s["pindah"][sh] = day_pindah if sh == "pagi" else 0
            s["meninggal"][sh] = day_meninggal if sh == "pagi" else 0
            s["total"][sh] = occ_total
            s["bedKosong"][sh] = free_total
            s["bedKosongDetail"][sh] = {
                "total": free_total,
                "pria": male_empty,
                "wanita": female_empty,
                "isolasi": iso_empty
            }

        day_data["summary"]["occupied"] = occ_total
        day_data["summary"]["empty"] = free_total
        day_data["summary"]["bor"] = round((occ_total / TOTAL_BEDS) * 100, 1)
        day_data["summary"]["occTim1"] = occ_t1
        day_data["summary"]["occTim2"] = occ_t2
        day_data["summary"]["occA"] = occ_t1
        day_data["summary"]["occB"] = occ_t2
        day_data["summary"]["emptyTim1"] = TIM1_BEDS - occ_t1
        day_data["summary"]["emptyTim2"] = TIM2_BEDS - occ_t2
        day_data["summary"]["emptyA"] = TIM1_BEDS - occ_t1
        day_data["summary"]["emptyB"] = TIM2_BEDS - occ_t2
        day_data["summary"]["borTim1"] = round((occ_t1 / TIM1_BEDS) * 100, 1)
        day_data["summary"]["borTim2"] = round((occ_t2 / TIM2_BEDS) * 100, 1)
        day_data["summary"]["borA"] = day_data["summary"]["borTim1"]
        day_data["summary"]["borB"] = day_data["summary"]["borTim2"]
        day_data["summary"]["discharges"] = {
            "blpl": day_blpl,
            "aps": day_aps,
            "pindah": day_pindah,
            "meninggal": day_meninggal,
            "total": day_keluar_total
        }

        prev_active_map = cur_active_map

    # Refresh history dari hasil hitungan pasien satu per satu
    history = []
    for iso_d in all_dates:
        day_data = recent_days[iso_d]
        history.append({
            "date": iso_d,
            "occTim1": day_data["summary"]["occTim1"],
            "occTim2": day_data["summary"]["occTim2"],
            "totalOcc": day_data["summary"]["occupied"],
            "totalBeds": TOTAL_BEDS,
            "bor": day_data["summary"]["bor"]
        })
    print(f"[INFO] Sensus otomatis selesai untuk {len(all_dates)} tanggal ({all_dates[0]} s/d {all_dates[-1]}).")

    latest_date = all_dates[-1] if all_dates else datetime.now(WIB_TZ).strftime("%Y-%m-%d")
    today_data = recent_days.get(latest_date)

    # Doctor, Diagnosis, and Insurance Analytics aggregation from ALL TABS in spreadsheet
    unique_patients_map = {}
    all_observations_count = 0

    for iso_d in all_dates:
        day_info = recent_days.get(iso_d, {})
        for p in day_info.get('patients', []):
            if not p.get('isEmpty'):
                all_observations_count += 1
                mr = re.sub(r'\D', '', str(p.get('mrNo') or '')).strip()
                name = p.get('name', '').strip()
                key = f"MR:{mr}" if len(mr) >= 5 else f"NM:{name.lower()}"

                if key not in unique_patients_map:
                    unique_patients_map[key] = {
                        "mrNo": mr,
                        "name": name,
                        "bedLatest": p.get("bed", "-"),
                        "doctorPrimary": p.get("doctorPrimary", "-"),
                        "diagnosis": p.get("diagnosis", "-"),
                        "category": p.get("category", "-"),
                        "insurance": p.get("insurance", "-"),
                        "datesSeen": [iso_d]
                    }
                else:
                    if iso_d not in unique_patients_map[key]["datesSeen"]:
                        unique_patients_map[key]["datesSeen"].append(iso_d)
                    unique_patients_map[key]["bedLatest"] = p.get("bed", unique_patients_map[key]["bedLatest"])
                    if p.get("doctorPrimary") and p.get("doctorPrimary") != "-":
                        unique_patients_map[key]["doctorPrimary"] = p.get("doctorPrimary")
                    if p.get("insurance") and p.get("insurance") != "-":
                        unique_patients_map[key]["insurance"] = p.get("insurance")
                    if p.get("diagnosis") and p.get("diagnosis") != "-":
                        old_d = unique_patients_map[key]["diagnosis"]
                        new_d = p.get("diagnosis")
                        if new_d != old_d and new_d not in old_d:
                            unique_patients_map[key]["diagnosis"] = f"{old_d} | {new_d}"

    total_unique_pts = len(unique_patients_map)

    doctor_counts = defaultdict(int)
    ins_counts = defaultdict(int)
    cat_counts = defaultdict(int)
    diag_group_counts = defaultdict(int)

    # Standard Clinical Disease Entities for Top 10 Diagnosa Medis
    disease_patterns = [
        ("Gagal Ginjal Kronik (CKD on HD / Stage V)", ["CKD", "GAGAL GINJAL", "STAGE V", "ST V", "STG 5", "ST.V", "PRO HD", "ON HD", "NEFROPATI"]),
        ("Anemia Renal / Anemia Gravis in CKD", ["ANEMIA", "ANEMI", "GRAVIS", "LEUKOSITOSIS", "TROMBOSITOPENIA"]),
        ("Gangguan Elektrolit (Hiponatremia / Hiperkalemia)", ["ELEKTROLIT", "HIPONATREMIA", "HIPERKALEMIA", "HIPOKALEMIA", "HIPOCA", "HIPOOSMOLER"]),
        ("Keganasan / Onkologi (Ca Nasofaring, Ovarium, CML)", ["CA ", "CANCER", "TUMOR", "CML", "MALIGNANCY", "APLASTIK", "LIEN", "SERVIKS"]),
        ("Gastrointestinal / PSCBA / Melena / Dyspepsia", ["MELENA", "PSCBA", "HEMATEMESIS", "DYSPEPSIA", "DISPEPSIA", "GASTROPATI", "HEMATOCHEZIA", "GASTRO"]),
        ("Diabetes Melitus Tipe II (DKD / HHS / KAD)", ["DM ", "DM T", "DIABETES", "DKD", "HHS", "KAD", "HIPOGLIKEMIA"]),
        ("Edema Paru / Efusi Pleura / CHF", ["EDEMA PULMO", "EFUSI", "PLEURA", "CHF", "ANASARKA", "SESAK"]),
        ("Dermatologi & Imunologi (Pempigus, Psoriasis)", ["PEMFIGUS", "PEMPENIGUS", "VUGARIS", "VULGARIS", "PSORIASIS", "HERPES", "SLE", "RTA"]),
        ("Hipertensi (Urgensi / Emergensi / HHD)", ["HT ", "HIPERTENSI", "HHD", "URGENSI", "EMERGENSI", "HT STG"]),
        ("Urologi / Hidronefrosis / Nefrolitiasis", ["HIDRONEFROSIS", "NEFROLIT", "BATU", "URETER", "STENT"])
    ]

    for p in unique_patients_map.values():
        doc = p.get('doctorPrimary', '-')
        if doc and doc != '-':
            doctor_counts[doc] += 1

        ins = p.get('insurance', '-')
        if ins and ins != '-':
            ins_counts[ins] += 1

        cat = p.get('category', '-')
        if cat and cat != '-':
            cat_counts[cat] += 1

        diag_full = (p.get('diagnosis', '')).upper()
        matched_any = False
        for label, keywords in disease_patterns:
            if any(k in diag_full for k in keywords):
                diag_group_counts[label] += 1
                matched_any = True
        if not matched_any and diag_full.strip() and not diag_full.startswith('ATAS NAMA'):
            diag_group_counts["Penyakit Dalam / Diagnosa Lainnya"] += 1

    denom_pts = max(1, total_unique_pts)
    top_doctors = [{"name": k, "count": v, "pct": round(v / denom_pts * 100, 1)} for k, v in sorted(doctor_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
    top_diagnoses = [{"name": k, "count": v, "pct": round(v / denom_pts * 100, 1)} for k, v in sorted(diag_group_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
    category_list = [{"name": k, "count": v, "pct": round(v / denom_pts * 100, 1)} for k, v in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)]
    insurance_list = [{"name": k, "count": v, "pct": round(v / denom_pts * 100, 1)} for k, v in sorted(ins_counts.items(), key=lambda x: x[1], reverse=True)]

    # =========================================================================
    # INDIKATOR MUTU RUMAH SAKIT (RUMUS STANDAR KEMENKES RI)
    # =========================================================================
    total_hp = sum(h["totalOcc"] for h in history)
    total_days = max(1, len(history))
    total_discharges = total_blpl + total_aps + total_pindah + total_meninggal
    sufficient_data = (total_days >= 30 and total_discharges >= 30)

    bor_overall = round((total_hp / (TOTAL_BEDS * total_days)) * 100, 1) if total_days > 0 else 0.0
    total_los_discharged = sum(r["los"] for r in discharged_records)
    if total_discharges > 0 and total_los_discharged > 0:
        avlos = round(total_los_discharged / total_discharges, 1)
    elif total_discharges > 0:
        avlos = round(total_hp / total_discharges, 1)
    else:
        avlos = 0.0

    toi = round(max(0.0, ((TOTAL_BEDS * total_days) - total_hp) / total_discharges), 1) if total_discharges > 0 else 0.0
    bto_period = round(total_discharges / TOTAL_BEDS, 2)
    bto_annual = round((total_discharges / TOTAL_BEDS) * (365 / total_days), 1) if sufficient_data else None
    bto_display = bto_annual if sufficient_data else bto_period
    bto_unit = "kali/tahun" if sufficient_data else f"kali/{total_days} hari"

    deaths_gt48 = total_meninggal_gt48
    gdr = round((total_meninggal / total_discharges) * 1000, 1) if total_discharges > 0 else 0.0
    ndr = round((deaths_gt48 / total_discharges) * 1000, 1) if total_discharges > 0 else 0.0

    month_key = all_dates[0][:7] if all_dates else "2026-11"
    monthly_entry = {
        "month": month_key,
        "days": total_days,
        "hp": total_hp,
        "hpTim1": sum(h.get("occTim1", 0) for h in history),
        "hpTim2": sum(h.get("occTim2", 0) for h in history),
        "discharges": total_discharges,
        "blpl": total_blpl,
        "aps": total_aps,
        "pindah": total_pindah,
        "deaths": total_meninggal,
        "deathsGt48": deaths_gt48,
        "sufficientData": sufficient_data,
        "bor": bor_overall,
        "avlos": avlos,
        "toi": toi,
        "bto": bto_display,
        "btoPeriod": bto_period,
        "btoAnnual": bto_annual,
        "btoUnit": bto_unit,
        "gdr": gdr,
        "ndr": ndr
    }

    hospital_indicators = {
        "capacity": {
            "tim1": TIM1_BEDS,
            "tim2": TIM2_BEDS,
            "total": TOTAL_BEDS
        },
        "availableBeds": TOTAL_BEDS,
        "totalDays": total_days,
        "totalHP": total_hp,
        "totalDischarges": total_discharges,
        "sufficientData": sufficient_data,
        "dischargeBreakdown": {
            "blpl": total_blpl,
            "aps": total_aps,
            "pindah": total_pindah,
            "meninggal": total_meninggal,
            "meninggalGt48": deaths_gt48
        },
        "overall": {
            "bor": bor_overall,
            "avlos": avlos,
            "toi": toi,
            "bto": bto_display,
            "btoPeriod": bto_period,
            "btoAnnual": bto_annual,
            "btoUnit": bto_unit,
            "gdr": gdr,
            "ndr": ndr
        },
        "monthly": [monthly_entry]
    }

    now_wib = datetime.now(WIB_TZ)
    months_id = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    last_updated_wib = f"{now_wib.day} {months_id[now_wib.month - 1]} {now_wib.year} pukul {now_wib.strftime('%H:%M')} WIB"

    full_output = {
        "metadata": {
            "title": "Dashboard Ruang Kakap",
            "subtitle": "Sistem Informasi Sensus Pasien, Denah Bed & Operan Jaga Rawat Inap Ruang Kakap",
            "hospital": "RSUD Dr. Soedarso Pontianak",
            "roomName": "Ruang Rawat Inap Kakap",
            "openedDate": "2026-11-02",
            "capacity": {"tim1": TIM1_BEDS, "tim2": TIM2_BEDS, "total": TOTAL_BEDS},
            "wings": ["Tim I (Kakap 1-5 & Isolasi - 21 Bed)", "Tim II (Kakap 6-10 - 20 Bed)"],
            "lastUpdated": now_wib.strftime("%d-%m-%Y %H:%M:%S"),
            "lastUpdatedWib": last_updated_wib,
            "lastUpdatedIso": now_wib.isoformat(),
            "latestDate": latest_date,
            "totalDatesRecorded": len(all_dates),
            "dateRange": f"{all_dates[0]} s/d {all_dates[-1]}" if all_dates else "-",
            "spreadsheetUrl": SPREADSHEET_URL,
            "privacyEncrypted": True
        },
        "allDates": all_dates,
        "history": history,
        "analytics": {
            "topDoctors": top_doctors,
            "topDiagnoses": top_diagnoses,
            "categories": category_list,
            "insurances": insurance_list,
            "totalPatients": total_unique_pts,
            "totalObservations": all_observations_count,
            "measurementSchedule": "Diukur per hari di pagi hari (Pukul 07:00 WIB)",
            "measurementScope": f"Data dari seluruh tab spreadsheet ({all_dates[0]} s/d {all_dates[-1]})",
            "totalTabsCount": len(all_dates),
            "spreadsheetRange": f"{all_dates[0]} s/d {all_dates[-1]}"
        },
        "monthly": [{
            "month": month_key,
            "daysCounted": total_days,
            "avgOcc": round(total_hp / total_days, 1),
            "avgOccA": round(sum(h.get("occTim1", 0) for h in history) / total_days, 1),
            "avgOccB": round(sum(h.get("occTim2", 0) for h in history) / total_days, 1),
            "avgBor": bor_overall
        }],
        "hospitalIndicators": hospital_indicators,
        "recentDays": recent_days,
        "today": today_data
    }

    # Integrasi Clinical Pathway MVP RSUD dr. Soedarso (sebelum data disamarkan agar analisis CP tetap akurat)
    try:
        import cp_mvp_engine
        cp_analytics = cp_mvp_engine.run_engine(recent_days=recent_days, today_data=today_data)
        full_output["clinicalPathways"] = cp_analytics
        print("[INFO] cp_mvp_engine berhasil memproses analitik kepatuhan CP.")
    except Exception as e:
        print(f"[WARN] cp_mvp_engine error: {e}")

    # =========================================================================
    # KEAMANAN DATA PASIEN (UU PDP No. 27/2022):
    # Enkripsi identitas penuh & catatan SBAR ke clinicalVault (hanya terbuka dg PIN),
    # lalu samarkan seluruh nama lengkap, No. RM, dan catatan klinis di JSON publik.
    # =========================================================================
    vault_days = {}
    for iso_d in all_dates:
        day_obj = recent_days[iso_d]
        day_vault = {}
        for p in day_obj.get("patients", []):
            if not p.get("isEmpty"):
                bed_key = str(p.get("bed", ""))
                day_vault[bed_key] = {
                    "name": p.get("name", ""),
                    "mrNo": p.get("mrNo", ""),
                    "notes": p.get("notes", {"pagi": "", "sore": "", "malam": ""})
                }
                # Samarkan data publik
                p["name"] = mask_patient_name_py(p.get("name", ""))
                p["mrNo"] = mask_mr_py(p.get("mrNo", ""))
                p["notes"] = {"pagi": "", "sore": "", "malam": ""}
        vault_days[iso_d] = day_vault

    # Samarkan pula data pasien riil di clinicalPathways (sementara kasus benchmark tetap ditandai DATA CONTOH)
    vault_cp = {}
    def mask_cp_obj(obj):
        if isinstance(obj, list):
            for item in obj:
                mask_cp_obj(item)
        elif isinstance(obj, dict):
            is_bench = bool(obj.get("is_benchmark") or str(obj.get("episode_id", "")).startswith("EP-BENCH"))
            if not is_bench:
                ep_id = obj.get("episode_id") or obj.get("mr_no") or obj.get("mrNo")
                raw_name = obj.get("patient_name") or obj.get("name")
                raw_mr = obj.get("mr_no") or obj.get("mrNo")
                if ep_id and (raw_name or raw_mr):
                    if isinstance(raw_name, str) and "***" not in raw_name and any(x in obj for x in ("patient_name", "mr_no", "mrNo")):
                        vault_cp[str(ep_id)] = {
                            "name": raw_name,
                            "mrNo": str(raw_mr or "")
                        }
                if "patient_name" in obj and isinstance(obj["patient_name"], str):
                    obj["patient_name"] = mask_patient_name_py(obj["patient_name"])
                if "name" in obj and isinstance(obj["name"], str) and ("mr_no" in obj or "mrNo" in obj or "bed" in obj):
                    obj["name"] = mask_patient_name_py(obj["name"])
                if "mr_no" in obj and isinstance(obj["mr_no"], str):
                    obj["mr_no"] = mask_mr_py(obj["mr_no"])
                if "mrNo" in obj and isinstance(obj["mrNo"], str):
                    obj["mrNo"] = mask_mr_py(obj["mrNo"])
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    mask_cp_obj(v)

    if "clinicalPathways" in full_output:
        mask_cp_obj(full_output["clinicalPathways"])
        try:
            with open(CLINICAL_PATHWAYS_JSON, "w", encoding="utf-8") as cf:
                json.dump(full_output["clinicalPathways"], cf, indent=2, ensure_ascii=False)
            print(f"[SUCCESS] Wrote masked {CLINICAL_PATHWAYS_JSON}")
        except Exception as e:
            print(f"[WARN] Could not write masked clinical_pathways.json: {e}")

    clinical_pin = os.getenv("KAKAP_CLINICAL_PIN", "").strip() or "2026"
    full_output["clinicalVault"] = crypto_vault.encrypt_clinical_vault(
        {"days": vault_days, "cp": vault_cp},
        clinical_pin
    )

    with open(DASHBOARD_DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2, ensure_ascii=False)
    print(f"[SUCCESS] Wrote encrypted & masked {DASHBOARD_DATA_JSON} ({os.path.getsize(DASHBOARD_DATA_JSON)} bytes)")

    with open(HOSPITAL_INDICATORS_JSON, "w", encoding="utf-8") as f:
        json.dump(hospital_indicators, f, indent=2, ensure_ascii=False)
    print(f"[SUCCESS] Wrote {HOSPITAL_INDICATORS_JSON}")

if __name__ == "__main__":
    import sys
    do_dl = "--download" in sys.argv
    build_data(download=do_dl)