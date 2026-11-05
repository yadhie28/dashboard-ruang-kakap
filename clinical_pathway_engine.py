#!/usr/bin/env python3
"""
clinical_pathway_engine.py
=============================================================================
Engine Audit Mutu & Pelaporan Kepatuhan Clinical Pathway (CP) Resmi
RSUD Dr. Soedarso Pontianak - Ruang Rawat Inap Kakap (Penyakit Dalam)
=============================================================================
Menghitung 5 Dimensi Kunci Sesuai Arahan:
1. Kepatuhan Penegakan Diagnosis (Baku Emas Lab & Radiologi)
2. Kepatuhan Terapi / Obat (Antibiotik Profilaksis, Insulin, Terapi Utama)
3. Kepatuhan Lama Rawat (Length of Stay / LOS Control vs Target CP)
4. Analisis Variasi (Variance Categorization ke 4 Kategori Baku)
5. Integrasi Biaya (Financial Auditing & Cost Containment INA-CBGs vs Real Cost)
=============================================================================
"""

import os
import json
import re
from datetime import datetime

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CP_MASTER_PATH = os.path.join(CURRENT_DIR, "clinical_pathways.json")
DASHBOARD_DATA_PATH = os.path.join(CURRENT_DIR, "dashboard_data.json")

def load_cp_master():
    """Memuat database master Clinical Pathway RSUD Dr. Soedarso."""
    if os.path.exists(CP_MASTER_PATH):
        try:
            with open(CP_MASTER_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load {CP_MASTER_PATH}: {e}")
    return {"pathways": [], "varianceCategories": []}

def match_patient_to_pathway(patient, pathways):
    """
    Mencocokkan pasien Ruang Kakap dengan Clinical Pathway yang relevan.
    Berdasarkan teks diagnosa, kategori, dan catatan klinis menggunakan word-boundary regex.
    """
    diag_str = (patient.get("diagnosis") or "").lower()
    cat_str = (patient.get("category") or "").lower()
    tags = [t.get("label", "").lower() for t in patient.get("tags", [])]
    notes_str = ""
    p_notes = patient.get("notes") or {}
    if isinstance(p_notes, dict):
        notes_str = " ".join(str(v) for v in p_notes.values()).lower()
    elif isinstance(p_notes, str):
        notes_str = p_notes.lower()

    full_text = f"{diag_str} {cat_str} {' '.join(tags)} {notes_str}"

    def has_kw(pattern, text):
        return bool(re.search(r'\b' + re.escape(pattern) + r'\b', text, re.I))

    # Helper mapping pathway by ID
    cp_map = {cp["id"]: cp for cp in pathways}

    # 1. Cek Stroke Non Perdarahan / Iskemik
    if any(has_kw(k, diag_str) for k in ["stroke iskemik", "stroke infark", "stroke sequele", "non perdarahan", "infark serebri"]) or \
       (has_kw("stroke", diag_str) and not any(has_kw(k, diag_str) for k in ["perdarahan", "ich", "ivh", "sah"])):
        if "CP-SR-01" in cp_map: return cp_map["CP-SR-01"]

    # 2. Cek Stroke Perdarahan
    if any(has_kw(k, diag_str) for k in ["stroke perdarahan", "ich", "ivh", "sah", "perdarahan otak", "hemorrhagic stroke"]):
        if "CP-SR-02" in cp_map: return cp_map["CP-SR-02"]

    # 3. Cek Kanker Payudara / Ca Mammae
    if any(has_kw(k, full_text) for k in ["mammae", "payudara", "mastektomi", "bcs"]):
        if "CP-BD-01" in cp_map: return cp_map["CP-BD-01"]

    # 4. Cek HIV / AIDS
    if any(has_kw(k, full_text) for k in ["hiv", "aids", "vct", "cd4"]):
        if "CP-PD-02" in cp_map: return cp_map["CP-PD-02"]

    # 5. Cek DM Tipe II + CKD (Penyakit Dalam Kombinasi)
    is_dm = any(has_kw(k, full_text) for k in ["dm", "dm tipe 2", "dm t ii", "diabetes", "kad", "hhs", "gastropati dm"])
    is_ckd = any(has_kw(k, full_text) for k in ["ckd", "dkd", "nefropati", "ginjal", "renal", "uremic", "hd", "hemodialisa", "pro hd", "on hd"])

    if is_dm and is_ckd:
        if "CP-PD-01" in cp_map: return cp_map["CP-PD-01"]

    # 6. Cek CKD Stage V on HD / Hemodialisa Murni (Tanpa DM)
    if is_ckd:
        if "CP-PD-05" in cp_map: return cp_map["CP-PD-05"]

    # 7. Cek DM Murni Tanpa CKD
    if is_dm:
        if "CP-PD-01" in cp_map: return cp_map["CP-PD-01"]

    # 8. Cek Anemia Gravis, Thalasemia & Gangguan Hematologi Kronis
    if any(has_kw(k, full_text) for k in ["thalasemia", "anemia gravis", "anemia", "anemia aplastik", "cml", "itp", "transfusi", "feritin", "prc", "trombositopenia"]):
        if "CP-PD-04" in cp_map: return cp_map["CP-PD-04"]

    # 9. Cek Kanker / Onkologi Umum di Ruang Kakap
    if any(has_kw(k, full_text) for k in ["tumor", "kanker", "ca ", "karsinoma", "malignancy", "kemoterapi", "radioterapi"]):
        if "CP-BD-01" in cp_map: return cp_map["CP-BD-01"]

    # Fallback ke pathway penyakit dalam terdekat
    if "CP-PD-05" in cp_map:
        return cp_map["CP-PD-05"]
    return pathways[0] if pathways else None

def audit_patient_compliance(patient, pathway):
    """
    Melakukan audit kepatuhan klinis 5 dimensi terhadap satu pasien:
    1. Kepatuhan Diagnosis (Lab & Radiologi Baku Emas)
    2. Kepatuhan Terapi & Obat
    3. Kepatuhan Lama Rawat (LOS Control)
    4. Analisis Variasi (4 Kategori Baku)
    5. Integrasi Biaya INA-CBGs vs Estimasi Real Cost
    """
    p_notes = patient.get("notes") or {}
    notes_text = ""
    if isinstance(p_notes, dict):
        notes_text = " ".join(str(v) for v in p_notes.values()).lower()
    elif isinstance(p_notes, str):
        notes_text = p_notes.lower()

    diag_text = (patient.get("diagnosis") or "").lower()
    combined_clinical = f"{diag_text} {notes_text}"

    # -------------------------------------------------------------------------
    # 1. KEPATUHAN PENEGAKAN DIAGNOSIS (LABORATORIUM & RADIOLOGI BAKU EMAS)
    # -------------------------------------------------------------------------
    diag_standards = pathway.get("diagnosticStandards", [])
    diag_results = []
    diag_fulfilled = 0
    diag_mandatory_count = 0

    diagnostic_keywords = {
        "LAB_GDS": ["gds", "gula darah", "glukosa"],
        "LAB_GDP": ["gdp", "puasa", "gula puasa"],
        "LAB_CREAT": ["kreatinin", "creatinin", "ureum", "renal", "fungsi ginjal", "ckd", "dkd"],
        "LAB_LIPID": ["lipid", "kolesterol", "cholesterol", "trigliserida", "ldl", "hdl"],
        "LAB_HBA1C": ["hba1c", "a1c", "g2jpp"],
        "RAD_EKG": ["ekg", "rekam jantung", "ecg"],
        "RAD_THORAX": ["thorax", "toraks", "ronsen", "rontgen", "cxr", "foto dada", "edema pulmo"],
        "RAD_THORAX_PA": ["thorax", "rontgen dada", "ronsen", "cxr"],
        "LAB_HIV_AB": ["hiv", "rapid hiv", "tiga tes", "immunoassay"],
        "LAB_HIV_AG": ["p24", "antigen hiv", "viral load"],
        "LAB_CD4": ["cd4", "viral load", "limfosit"],
        "LAB_COINFECT": ["hbsag", "hepatitis", "tcm", "bta", "tb", "sputum"],
        "RAD_HCTS": ["hcts", "ct-scan", "ct scan", "head ct"],
        "LAB_DARAH_RUTIN": ["darah rutin", "dr", "hb", "leukosit", "trombosit"],
        "LAB_KOAGULASI": ["pt", "aptt", "inr", "koagulasi"],
        "LAB_METABOLIK": ["elektrolit", "na", "k", "natrium", "kalium", "cl"],
        "LAB_HEMOSTASIS": ["hemostasis", "pt", "aptt", "inr", "fibrinogen"],
        "RAD_USG_MAMMO": ["usg", "mamografi", "birads", "mammae"],
        "LAB_BIOPSI": ["biopsi", "fnac", "core biopsy"],
        "LAB_PRA_OP": ["pra-op", "hb", "sgot", "sgpt", "urinalisis"],
        "LAB_PA_IHK": ["pa", "histopatologi", "ihk", "er", "pr", "her2", "ki-67"],
        "LAB_DR_RETIC": ["dr", "darah rutin", "retikulosit", "hb"],
        "LAB_GDT": ["gdt", "gambaran darah tepi", "morfologi"],
        "LAB_FERRITIN": ["feritin", "ferritin", "tibc", "serum iron", "iron"],
        "LAB_HEPATIC_RENAL": ["bilirubin", "sgot", "sgpt", "fungsi hati", "ureum", "kreatinin"],
        "RAD_USG_ABDOMEN": ["usg abdomen", "usg", "abdomen"],
        "LAB_CREAT_UREUM": ["kreatinin", "creatinin", "ureum", "cr", "ur", "ckd", "gagal ginjal", "egfr"],
        "LAB_ELEKTROLIT": ["elektrolit", "kalium", "k ", "k:", "k 6", "natrium", "na", "hiperkalemia", "hiponatremia"],
        "LAB_DARAH_LENGKAP": ["darah lengkap", "darah rutin", "dr", "hb", "leukosit", "trombosit", "anemia renal"],
        "RAD_USG_RENAL": ["usg", "usg ginjal", "hidronefrosis", "nefrolit"]
    }

    for std in diag_standards:
        code = std["code"]
        is_mand = std.get("mandatory", True)
        if is_mand:
            diag_mandatory_count += 1

        kw_list = diagnostic_keywords.get(code, [std["name"].lower()])
        is_done = any(k in combined_clinical for k in kw_list)

        # Baseline: jika pasien sudah ditegakkan diagnosis CKD/DM/Stroke oleh DPJP,
        # parameter primer dianggap telah terbukti di IGD / lab sebelumnya
        if not is_done and is_mand:
            if "ckd" in diag_text and code in ["LAB_CREAT", "LAB_GDS"]:
                is_done = True
            elif "anemia" in diag_text and code in ["LAB_DR_RETIC", "LAB_GDT"]:
                is_done = True
            elif "stroke" in diag_text and code in ["RAD_HCTS", "RAD_EKG"]:
                is_done = True

        if is_done:
            diag_fulfilled += 1

        diag_results.append({
            "code": code,
            "name": std["name"],
            "category": std.get("category", "Laboratorium"),
            "mandatory": is_mand,
            "isDone": is_done,
            "status": "Terpenuhi" if is_done else ("Belum Dilakukan (Wajib)" if is_mand else "Opsional")
        })

    diag_compliance_pct = round((diag_fulfilled / len(diag_standards)) * 100, 1) if diag_standards else 100.0

    # -------------------------------------------------------------------------
    # 2. KEPATUHAN TERAPI & OBAT (MEDICATION COMPLIANCE)
    # -------------------------------------------------------------------------
    med_standards = pathway.get("medicationStandards", [])
    med_results = []
    med_fulfilled = 0
    med_mandatory_count = 0

    medication_keywords = {
        "MED_INSULIN": ["insulin", "novorapid", "lantus", "sansulin", "levemir", "apidra"],
        "MED_INFUS": ["ivfd", "infus", "asering", "rl", "nacl", "bfluid", "ns"],
        "MED_ORAL": ["metformin", "acarbose", "glimepiride", "pioglitazon"],
        "MED_HYPO_GUARD": ["d40", "dextrose", "gds", "hipo"],
        "MED_ARV": ["arv", "tdf", "3tc", "efv", "dtg", "azt", "nvp"],
        "MED_COTRIMOX": ["kotrimoksazol", "cotrimoxazole", "bactrim"],
        "MED_OAT": ["oat", "rifampisin", "inh", "etambutol", "pirazinamid"],
        "MED_ANTIPLATELET": ["aspilet", "clopidogrel", "dapt", "aspirin", "trombo"],
        "MED_INFUS_ISOTONIK": ["nacl", "ns", "isotonik", "ivfd"],
        "MED_NEUROPROTECTOR": ["citicoline", "piracetam"],
        "MED_STATIN": ["atorvastatin", "simvastatin", "rosuvastatin", "statin"],
        "MED_ANTI_EDEMA": ["manitol", "mannitol", "hipertonik"],
        "MED_NIMODIPINE": ["nimodipine", "nimotop"],
        "MED_ANTIHT_IV": ["nicardipine", "diltiazem", "clonidine"],
        "MED_SURGERY_EVAL": ["bedah saraf", "evd", "kraniotomi", "dekompresi"],
        "MED_AB_PROFILAKSIS": ["cefazolin", "ceftriaxone", "profilaksis", "antibiotik"],
        "MED_ANALGETIK": ["paracetamol", "ketorolak", "tramadol", "nsaid", "analgetik", "lanso"],
        "MED_VTE_PREVENT": ["lmwh", "enoxaparin", "fondaparinux"],
        "MED_ANTIEMETIK": ["ondansetron", "metoklopramid", "antiemetik"],
        "MED_TRANSFUSI_PRC": ["tranfusi", "transfusi", "prc", "darah", "kolf"],
        "MED_PREMEDIKASI": ["ca glukonas", "diphenhydramine", "dexa", "premedikasi"],
        "MED_CHELATION": ["deferipron", "kelasi", "desferal", "ferriprox"],
        "MED_SUPPLEMENT": ["as. folat", "asam folat", "vit e", "vitamin e", "mecobalamin"],
        "MED_HD_HEPARIN": ["hd", "hemodialisa", "hemodialisis", "cdl", "akses", "pro hd", "on hd", "heparin"],
        "MED_ANTI_HIPERKALEMIA": ["ca glukonas", "kalitake", "d40", "insulin", "bicnat", "hiperkalemia", "koreksi"],
        "MED_EPO": ["epo", "renogen", "hemopo", "eprex", "zat besi"],
        "MED_BINDER_PHOS": ["kalsium karbonat", "caco3", "calos", "binder", "renagel"],
        "MED_RESTRIKSI_CAIRAN": ["restriksi", "balans", "intake", "edema", "pembatasan", "cairan", "ivfd"]
    }

    for std in med_standards:
        code = std["code"]
        is_mand = std.get("mandatory", True)
        if is_mand:
            med_mandatory_count += 1

        kw_list = medication_keywords.get(code, [std["name"].lower()])
        is_given = any(k in combined_clinical for k in kw_list)

        # Baseline clinical deduction
        if not is_done and is_mand:
            if "insulin" in combined_clinical and code == "MED_INSULIN":
                is_given = True
            elif "ivfd" in combined_clinical and code in ["MED_INFUS", "MED_INFUS_ISOTONIK"]:
                is_given = True

        if is_given:
            med_fulfilled += 1

        med_results.append({
            "code": code,
            "name": std["name"],
            "timing": std.get("timing", "Sesuai Hari Rawat"),
            "mandatory": is_mand,
            "isGiven": is_given,
            "status": "Diberikan Tepat Alur" if is_given else ("Belum Tercatat (Wajib)" if is_mand else "Sesuai Indikasi")
        })

    med_compliance_pct = round((med_fulfilled / len(med_standards)) * 100, 1) if med_standards else 100.0

    # -------------------------------------------------------------------------
    # 3. KEPATUHAN LAMA RAWAT (LENGTH OF STAY / LOS CONTROL)
    # -------------------------------------------------------------------------
    raw_los = patient.get("los")
    try:
        actual_los = int(raw_los) if raw_los is not None else 1
    except (ValueError, TypeError):
        actual_los = 1

    target_los = pathway.get("targetLos", 7)
    delta_los = actual_los - target_los

    if delta_los <= 0:
        los_status = "Compliant (On-Track)"
        los_badge = "badge-success"
        los_compliance_pct = 100.0
    elif delta_los == 1:
        los_status = "Warning (Borderline Over-LOS)"
        los_badge = "badge-warning"
        los_compliance_pct = 85.0
    elif delta_los <= 3:
        los_status = "Over-LOS (Penyimpangan Ringan-Sedang)"
        los_badge = "badge-danger"
        los_compliance_pct = max(30.0, round(100.0 - (delta_los * 18.0), 1))
    else:
        los_status = "Excessive LOS (Penyimpangan Berat / Komplikasi Kronis)"
        los_badge = "badge-danger"
        los_compliance_pct = max(10.0, round(100.0 - (delta_los * 12.0), 1))

    # -------------------------------------------------------------------------
    # 4. ANALISIS VARIASI PELAYANAN (VARIANCE CATEGORIZATION - 4 KATEGORI BAKU)
    # -------------------------------------------------------------------------
    has_variance = (delta_los > 0) or (diag_compliance_pct < 80.0) or (med_compliance_pct < 75.0)
    detected_variances = []

    # Deteksi Faktor Pasien (Kondisi Klinis / Komplikasi Berat)
    patient_variance_reasons = []
    if any(k in combined_clinical for k in ["edema pulmo", "hiperkalemia", "asidosis", "sepsis", "syok", "uremic syndrome", "melena"]):
        patient_variance_reasons.append("Komplikasi klinis berat (edema pulmo / hiperkalemia / perdarahan saluran cerna aktif)")
    if any(k in combined_clinical for k in ["anemia gravis", "hb 6", "hb: 6", "hb < 7"]):
        patient_variance_reasons.append("Kondisi anemia gravis berat membutuhkan transfusi berulang sebelum dapat dipulangkan")
    if any(k in combined_clinical for k in ["sirosis", "asites", "paraplegia", "chf"]):
        patient_variance_reasons.append("Komorbiditas multipel (Sirosis hati / CHF / Gagal Jantung) memperpanjang masa pemulihan")
    if "penolakan" in combined_clinical or "keluarga menolak" in combined_clinical:
        patient_variance_reasons.append("Keluarga meminta penundaan tindakan / rencana pulang")

    if patient_variance_reasons:
        detected_variances.append({
            "category": "Faktor Pasien (Kondisi Klinis)",
            "categoryId": "VAR_PATIENT",
            "code": "A",
            "reasons": patient_variance_reasons,
            "badgeColor": "#ef4444"
        })

    # Deteksi Faktor Sistem Rumah Sakit (Sarana, Fasilitas & Logistik)
    system_variance_reasons = []
    if "masih dicari" in combined_clinical or "stok darah" in combined_clinical or "stok habis" in combined_clinical:
        system_variance_reasons.append("Kendala logistik darah BDRS/PMI (Stok kantong PRC kosong/masih dalam pencarian)")
    if "tidak bisa dilakukan karena" in combined_clinical or "lab luar" in combined_clinical:
        system_variance_reasons.append("Pemeriksaan penunjang laboratorium khusus (Lab Luar) belum dapat dilakukan sesuai syarat klinis")
    if any(k in combined_clinical for k in ["ac panas", "kamar 8 & 9 ac panas", "lift luar mati", "lift dalam sering error"]):
        system_variance_reasons.append("Kendala sarana prasarana ruangan (AC ruang kamar perbaikan / lift operasional terganggu)")
    if "antrian poli" in combined_clinical or "antrian eg" in combined_clinical or "antrian transit" in combined_clinical:
        system_variance_reasons.append("Keterbatasan kapasitas bed isolasi / antrean kamar rawat inap transit")

    if system_variance_reasons:
        detected_variances.append({
            "category": "Faktor Sistem Rumah Sakit (Sarana & Logistik)",
            "categoryId": "VAR_SYSTEM",
            "code": "B",
            "reasons": system_variance_reasons,
            "badgeColor": "#f59e0b"
        })

    # Deteksi Faktor Tenaga Medis (DPJP & Klinisi)
    staff_variance_reasons = []
    if "tunda" in combined_clinical or "menunda" in combined_clinical or "jadwal ulang" in combined_clinical:
        staff_variance_reasons.append("DPJP menunda prosedur/tindakan medis untuk evaluasi hasil penunjang tambahan")
    if "konsul" in combined_clinical and ("belum dijawab" in combined_clinical or "menunggu jawaban" in combined_clinical):
        staff_variance_reasons.append("Menunggu jawaban konsultasi antar divisi / KSM multidisiplin")
    if not staff_variance_reasons and delta_los >= 3 and not system_variance_reasons:
        staff_variance_reasons.append("Instruksi lanjutan DPJP menunggu target perbaikan biomarker darah tercapai")

    if staff_variance_reasons:
        detected_variances.append({
            "category": "Faktor Tenaga Medis (DPJP & Klinisi)",
            "categoryId": "VAR_MEDICAL_STAFF",
            "code": "C",
            "reasons": staff_variance_reasons,
            "badgeColor": "#8b5cf6"
        })

    # Deteksi Faktor Eksternal (Administrasi & Sosial)
    external_variance_reasons = []
    if any(k in combined_clinical for k in ["bpjs", "klaim", "sep", "rujukan"]):
        if delta_los >= 2:
            external_variance_reasons.append("Kendala administratif rujukan berjenjang antar faskes luar kota Pontianak")
    if "penjemputan" in combined_clinical or "keluarga belum" in combined_clinical or "ongkos" in combined_clinical:
        external_variance_reasons.append("Keluarga pasien belum dapat menjemput karena kendala transportasi daerah asal")

    if external_variance_reasons:
        detected_variances.append({
            "category": "Faktor Eksternal (Administrasi & Sosial)",
            "categoryId": "VAR_EXTERNAL",
            "code": "D",
            "reasons": external_variance_reasons,
            "badgeColor": "#06b6d4"
        })

    # Jika ada over-LOS tetapi belum terklasifikasi, berikan klasifikasi klinis default
    if delta_los > 0 and not detected_variances:
        detected_variances.append({
            "category": "Faktor Pasien (Kondisi Klinis)",
            "categoryId": "VAR_PATIENT",
            "code": "A",
            "reasons": [f"Pasien masih memerlukan perawatan intensif melebihi target alur klinis ({actual_los} hari vs target {target_los} hari)"],
            "badgeColor": "#ef4444"
        })

    primary_variance = detected_variances[0] if detected_variances else None

    # -------------------------------------------------------------------------
    # 5. INTEGRASI BIAYA & AUDIT FINANSIAL (REAL COST VS INA-CBGS COST CONTAINMENT)
    # -------------------------------------------------------------------------
    insurance = patient.get("insurance", "BPJS Kelas 3")
    cbg_data = pathway.get("inaCbgBenchmark", {})
    tariffs = cbg_data.get("tariffs", {})

    # Tentukan tarif INA-CBG sesuai kelas
    matched_class = "BPJS Kelas 3"
    if "kelas 1" in insurance.lower():
        matched_class = "BPJS Kelas 1"
    elif "kelas 2" in insurance.lower():
        matched_class = "BPJS Kelas 2"
    elif "kelas 3" in insurance.lower():
        matched_class = "BPJS Kelas 3"
    else:
        matched_class = "Umum / Asuransi Lain"

    ina_cbg_cap = tariffs.get(matched_class, tariffs.get("BPJS Kelas 3", 5500000))

    # Estimasi Real Hospital Cost (Tarif RSUD Dr. Soedarso)
    # Akomodasi: Kelas 1: 350k/hari, Kelas 2: 250k/hari, Kelas 3: 150k/hari
    room_rate_per_day = 350000 if "kelas 1" in insurance.lower() else (250000 if "kelas 2" in insurance.lower() else 150000)
    visite_rate_per_day = 125000
    daily_care_rate = room_rate_per_day + visite_rate_per_day

    # Estimasi biaya lab & penunjang yang dilakukan
    lab_rad_cost = diag_fulfilled * 165000

    # Estimasi biaya farmasi & obat per hari
    daily_pharma_rate = 320000
    if "prc" in combined_clinical or "tranfusi" in combined_clinical:
        daily_pharma_rate += 180000 # Tambahan biaya darah dan transfusi set
    if "insulin" in combined_clinical:
        daily_pharma_rate += 90000

    estimated_real_cost = (actual_los * daily_care_rate) + lab_rad_cost + (actual_los * daily_pharma_rate)

    financial_margin = ina_cbg_cap - estimated_real_cost
    cost_utilization_pct = round((estimated_real_cost / ina_cbg_cap) * 100, 1)

    if cost_utilization_pct <= 80.0:
        cost_status = "Surplus Finansial (Aman)"
        cost_badge = "badge-success"
        cost_alert_level = "low"
    elif cost_utilization_pct <= 100.0:
        cost_status = "Waspada Plafon (Cost Limit Approaching)"
        cost_badge = "badge-warning"
        cost_alert_level = "medium"
    else:
        cost_status = "Defisit Operasional (Cost Overrun)"
        cost_badge = "badge-danger"
        cost_alert_level = "high"

    # -------------------------------------------------------------------------
    # SKOR KEPATUHAN KESELURUHAN (OVERALL CP COMPLIANCE SCORE)
    # Bobot: 35% Diagnosis + 35% Terapi + 30% LOS Control
    # -------------------------------------------------------------------------
    overall_compliance = round(
        (diag_compliance_pct * 0.35) +
        (med_compliance_pct * 0.35) +
        (los_compliance_pct * 0.30),
        1
    )

    if overall_compliance >= 85.0:
        compliance_tier = "Sangat Patuh (Gold Standard)"
        tier_color = "#10b981"
        tier_badge = "badge-success"
    elif overall_compliance >= 70.0:
        compliance_tier = "Cukup Patuh (Moderate Compliance)"
        tier_color = "#f59e0b"
        tier_badge = "badge-warning"
    else:
        compliance_tier = "Perlu Evaluasi (High Variance)"
        tier_color = "#ef4444"
        tier_badge = "badge-danger"

    return {
        "pathwayId": pathway["id"],
        "pathwayTitle": pathway["title"],
        "pathwayShortTitle": pathway.get("shortTitle", pathway["title"]),
        "department": pathway.get("department", "KSM Penyakit Dalam"),
        "targetLos": target_los,
        "actualLos": actual_los,
        "deltaLos": delta_los,
        "losStatus": los_status,
        "losBadge": los_badge,
        "losCompliancePct": los_compliance_pct,
        "diagnosticCompliancePct": diag_compliance_pct,
        "diagnosticDetails": diag_results,
        "medicationCompliancePct": med_compliance_pct,
        "medicationDetails": med_results,
        "overallCompliancePct": overall_compliance,
        "complianceTier": compliance_tier,
        "tierColor": tier_color,
        "tierBadge": tier_badge,
        "hasVariance": has_variance,
        "variances": detected_variances,
        "primaryVariance": primary_variance,
        "financialAudit": {
            "insuranceClass": matched_class,
            "cbgCode": cbg_data.get("cbgCode", "N-4-10-I"),
            "cbgDescription": cbg_data.get("description", "-"),
            "cbgTariff": ina_cbg_cap,
            "estimatedRealCost": estimated_real_cost,
            "costMargin": financial_margin,
            "costUtilizationPct": cost_utilization_pct,
            "costStatus": cost_status,
            "costBadge": cost_badge,
            "alertLevel": cost_alert_level
        }
    }

def process_clinical_pathway_analytics(patients_list):
    """
    Memproses seluruh pasien di Ruang Kakap dan menyusun laporan komprehensif.
    """
    cp_master = load_cp_master()
    pathways = cp_master.get("pathways", [])
    variance_cats = cp_master.get("varianceCategories", [])

    audited_patients = []
    total_active_patients = 0

    pathway_stats = {}
    variance_counts = {
        "VAR_PATIENT": {"name": "Faktor Pasien (Kondisi Klinis)", "count": 0, "color": "#ef4444", "patients": []},
        "VAR_SYSTEM": {"name": "Faktor Sistem Rumah Sakit (Sarana & Logistik)", "count": 0, "color": "#f59e0b", "patients": []},
        "VAR_MEDICAL_STAFF": {"name": "Faktor Tenaga Medis (DPJP & Klinisi)", "count": 0, "color": "#8b5cf6", "patients": []},
        "VAR_EXTERNAL": {"name": "Faktor Eksternal (Administrasi & Sosial)", "count": 0, "color": "#06b6d4", "patients": []}
    }

    sum_diag_comp = 0.0
    sum_med_comp = 0.0
    sum_los_comp = 0.0
    sum_overall_comp = 0.0

    total_cbg_potential = 0
    total_real_cost = 0
    surplus_patients = 0
    deficit_patients = 0

    for p in patients_list:
        if p.get("isEmpty"):
            continue

        total_active_patients += 1
        matched_cp = match_patient_to_pathway(p, pathways)

        if matched_cp:
            audit = audit_patient_compliance(p, matched_cp)

            audited_p = {
                "bed": p.get("bed"),
                "room": p.get("room"),
                "name": p.get("name"),
                "mrNo": p.get("mrNo", "-"),
                "age": p.get("age", "-"),
                "gender": p.get("gender", "-"),
                "doctor": p.get("doctorPrimary", p.get("doctor", "-")),
                "admissionDate": p.get("admissionDate", "-"),
                "diagnosis": p.get("diagnosis", "-"),
                "insurance": p.get("insurance", "-"),
                "audit": audit
            }
            audited_patients.append(audited_p)

            # Akumulasi Skor
            sum_diag_comp += audit["diagnosticCompliancePct"]
            sum_med_comp += audit["medicationCompliancePct"]
            sum_los_comp += audit["losCompliancePct"]
            sum_overall_comp += audit["overallCompliancePct"]

            # Akumulasi Finansial
            fin = audit["financialAudit"]
            total_cbg_potential += fin["cbgTariff"]
            total_real_cost += fin["estimatedRealCost"]
            if fin["costMargin"] >= 0:
                surplus_patients += 1
            else:
                deficit_patients += 1

            # Akumulasi Variasi
            for v in audit.get("variances", []):
                cat_id = v.get("categoryId")
                if cat_id in variance_counts:
                    variance_counts[cat_id]["count"] += 1
                    variance_counts[cat_id]["patients"].append({
                        "bed": p.get("bed"),
                        "name": p.get("name"),
                        "reasons": v.get("reasons", [])
                    })

            # Akumulasi Statistik per Jenis CP
            cp_id = matched_cp["id"]
            if cp_id not in pathway_stats:
                pathway_stats[cp_id] = {
                    "id": cp_id,
                    "title": matched_cp["title"],
                    "shortTitle": matched_cp.get("shortTitle", matched_cp["title"]),
                    "targetLos": matched_cp.get("targetLos", 7),
                    "patientCount": 0,
                    "avgOverallCompliance": 0.0,
                    "sumOverall": 0.0,
                    "overLosCount": 0
                }
            pathway_stats[cp_id]["patientCount"] += 1
            pathway_stats[cp_id]["sumOverall"] += audit["overallCompliancePct"]
            if audit["deltaLos"] > 0:
                pathway_stats[cp_id]["overLosCount"] += 1

    cp_count = len(audited_patients)
    avg_diag = round(sum_diag_comp / cp_count, 1) if cp_count > 0 else 0.0
    avg_med = round(sum_med_comp / cp_count, 1) if cp_count > 0 else 0.0
    avg_los = round(sum_los_comp / cp_count, 1) if cp_count > 0 else 0.0
    avg_overall = round(sum_overall_comp / cp_count, 1) if cp_count > 0 else 0.0

    for cp_id, st in pathway_stats.items():
        st["avgOverallCompliance"] = round(st["sumOverall"] / st["patientCount"], 1)

    total_margin = total_cbg_potential - total_real_cost
    cost_efficiency_pct = round((total_real_cost / total_cbg_potential) * 100, 1) if total_cbg_potential > 0 else 0.0

    return {
        "summary": {
            "totalInpatients": total_active_patients,
            "totalCpInpatients": cp_count,
            "cpCoveragePct": round((cp_count / total_active_patients) * 100, 1) if total_active_patients > 0 else 0.0,
            "avgDiagnosticCompliance": avg_diag,
            "avgMedicationCompliance": avg_med,
            "avgLosCompliance": avg_los,
            "overallCpCompliance": avg_overall,
            "compliantPatientsCount": sum(1 for p in audited_patients if p["audit"]["overallCompliancePct"] >= 80.0),
            "variancePatientsCount": sum(1 for p in audited_patients if p["audit"]["hasVariance"]),
            "overLosPatientsCount": sum(1 for p in audited_patients if p["audit"]["deltaLos"] > 0),
            "financialAuditSummary": {
                "totalInaCbgTariff": total_cbg_potential,
                "totalEstimatedRealCost": total_real_cost,
                "netFinancialMargin": total_margin,
                "costEfficiencyPct": cost_efficiency_pct,
                "surplusPatientsCount": surplus_patients,
                "deficitPatientsCount": deficit_patients,
                "costContainmentStatus": "Optimal (Surplus Finansial Terkendali)" if total_margin >= 0 else "Defisit Operasional Rawat Inap"
            }
        },
        "varianceAnalysis": {
            "categories": variance_counts,
            "totalVarianceEvents": sum(v["count"] for v in variance_counts.values())
        },
        "pathwayBreakdown": list(pathway_stats.values()),
        "patients": audited_patients,
        "masterPathways": pathways
    }

if __name__ == "__main__":
    if os.path.exists(DASHBOARD_DATA_PATH):
        with open(DASHBOARD_DATA_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        pts = d.get("today", {}).get("patients", [])
        res = process_clinical_pathway_analytics(pts)
        print("=" * 60)
        print(f"SISTEM PELAPORAN KEPATUHAN CLINICAL PATHWAY - RSUD DR. SOEDARSO")
        print("=" * 60)
        print(f"Total Pasien Rawat Inap Kakap : {res['summary']['totalInpatients']}")
        print(f"Pasien Masuk Clinical Pathway : {res['summary']['totalCpInpatients']} ({res['summary']['cpCoveragePct']}%)")
        print(f"Kepatuhan Penegakan Diagnosis : {res['summary']['avgDiagnosticCompliance']}%")
        print(f"Kepatuhan Terapi & Obat       : {res['summary']['avgMedicationCompliance']}%")
        print(f"Kepatuhan Lama Rawat (LOS)    : {res['summary']['avgLosCompliance']}%")
        print(f"Skor Kepatuhan Agregat CP     : {res['summary']['overallCpCompliance']}%")
        print("-" * 60)
        print(f"Financial Auditing (Cost Containment):")
        print(f"  Plafon INA-CBGs Total : Rp {res['summary']['financialAuditSummary']['totalInaCbgTariff']:,}")
        print(f"  Biaya Riil Estimasi   : Rp {res['summary']['financialAuditSummary']['totalEstimatedRealCost']:,}")
        print(f"  Net Margin RSUD       : Rp {res['summary']['financialAuditSummary']['netFinancialMargin']:,} ({res['summary']['financialAuditSummary']['costEfficiencyPct']}% utilization)")
        print("=" * 60)
