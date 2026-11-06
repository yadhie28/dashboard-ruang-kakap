"""
cp_mvp_engine.py
================
Engine Pengukur Kepatuhan Clinical Pathway (CP) MVP
RSUD dr. Soedarso Pontianak

Fitur Inti:
1. Master Template 5 Seed CP Resmi (CA Mammae, DM-CKD, HIV/AIDS, Stroke Non Perdarahan, Stroke Perdarahan)
2. CP Builder Template Validation (struktur matriks item x hari, PPA, tipe item, kriteria)
3. Generator 50 Data Episode Sintetis (10 episode x 5 CP) dengan variasi kasus patuh, patuh sebagian, varian sistem/pasien, dan drop-out
4. Mesin Kalkulasi Kepatuhan Mutu:
   - Kepatuhan Mentah (Raw Compliance)
   - Kepatuhan Adjusted (Varian Berjustifikasi Dikeluarkan dari Denominator)
   - Bundle Kritis All-or-None
   - Kepatuhan per PPA & per Domain
   - Taksonomi Varian 4 Kategori (Pasien, Klinisi, Sistem RS, Kebijakan)
"""

import os
import json
import re
from datetime import datetime, timedelta

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_JSON_PATH = os.path.join(CURRENT_DIR, "cp_master_templates.json")

# ==============================================================================
# 1. DEFINISI 12 DOMAIN STANDAR MUTU KLINIS
# ==============================================================================
DOMAINS = [
    {"id": 1, "code": "MED", "name": "Penilaian dan Pemantauan Medis", "order": 1},
    {"id": 2, "code": "KEP", "name": "Penilaian dan Asuhan Keperawatan", "order": 2},
    {"id": 3, "code": "GIZ", "name": "Penilaian dan Asuhan Gizi", "order": 3},
    {"id": 4, "code": "FAR", "name": "Penilaian dan Asuhan Farmasi", "order": 4},
    {"id": 5, "code": "PEN", "name": "Pemeriksaan Penunjang (Lab & Radiologi)", "order": 5},
    {"id": 6, "code": "TIN", "name": "Tindakan Medis / Reperfusi / Operasi", "order": 6},
    {"id": 7, "code": "TNK", "name": "Tindakan Keperawatan", "order": 7},
    {"id": 8, "code": "OBT", "name": "Medikasi / Terapi Farmakologi", "order": 8},
    {"id": 9, "code": "NUT", "name": "Tata Laksana Nutrisi / Diet", "order": 9},
    {"id": 10, "code": "EDU", "name": "Pendidikan dan Komunikasi Terintegrasi", "order": 10},
    {"id": 11, "code": "REH", "name": "Mobilisasi dan Rehabilitasi Medik", "order": 11},
    {"id": 12, "code": "OUT", "name": "Outcome / Kriteria Pemulangan (Discharge)", "order": 12}
]

# ==============================================================================
# 2. DEFINISI 5 SEED CLINICAL PATHWAY RESMI RSUD DR. SOEDARSO
# ==============================================================================

SEED_TEMPLATES = [
    {
        "id": "CP-MAMMAE-001",
        "nomorCp": "CP/BEDAH-ONK/01/2026",
        "nama": "Kanker Payudara (CA Mammae) Stadium I–II (Bedah Elektif)",
        "versi": "1.0",
        "tanggalBerlaku": "2026-09-01",
        "ksm": "Bedah / Onkologi",
        "jumlahHariStandar": 5,
        "losTarget": 5,
        "kriteriaInklusi": "Ca Mammae stadium dini/operable (stadium I–II), rencana bedah elektif Mastektomi Radikal Modifikasi / BCS ± diseksi KGB aksila tanpa komplikasi pra-bedah.",
        "kriteriaEksklusi": "Stadium lanjut lokal (IIIb) / metastatik (IV), kemoterapi neoadjuvan pra-bedah, rekonstruksi payudara simultan.",
        "kodeIcd10": "C50.-",
        "kodeIcd9": "85.44, 85.21, 40.11, 40.3",
        "statusAktif": True,
        "items": [
            {
                "id": "CM-01", "domainCode": "MED", "uraian": "Anamnesis keluhan, evaluasi faktor risiko, pemeriksaan fisik payudara & KGB regional",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "CM-02", "domainCode": "MED", "uraian": "Penetapan status performa ECOG & evaluasi pre-anestesi pra-bedah",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "CM-03", "domainCode": "MED", "uraian": "Pemantauan pasca operasi (luka operasi, produksi drain WSD/vacuum, tanda perdarahan/infeksi)",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [2, 3, 4, 5]
            },
            {
                "id": "CM-04", "domainCode": "KEP", "uraian": "Asesmen awal keperawatan, tanda vital, skrining nyeri, riwayat alergi & risiko jatuh",
                "ppa": "PERAWAT", "tipe": "WAJIB", "isKritis": False, "bobot": 1.0, "jadwal": [1]
            },
            {
                "id": "CM-05", "domainCode": "KEP", "uraian": "Pemantauan tanda vital dan skala nyeri per shift (3 shift/hari)",
                "ppa": "PERAWAT", "tipe": "FREKUENSI", "isKritis": False, "bobot": 1.0, "jadwal": [1, 2, 3, 4, 5]
            },
            {
                "id": "CM-06", "domainCode": "TNK", "uraian": "Perawatan luka operasi, pencatatan volume & karakteristik cairan drain",
                "ppa": "PERAWAT", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [2, 3, 4, 5]
            },
            {
                "id": "CM-07", "domainCode": "PEN", "uraian": "Laboratorium pra-bedah: Darah lengkap (Hb, Leuko, Trombosit, Ht)",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "CM-08", "domainCode": "PEN", "uraian": "Faal Hemostasis pra-bedah: PT, APTT, INR",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "CM-09", "domainCode": "PEN", "uraian": "GDS, Elektrolit (Na, K), Fungsi Ginjal & Hati (Ureum, Kreatinin, SGOT, SGPT)",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": False, "bobot": 1.0, "jadwal": [1]
            },
            {
                "id": "CM-10", "domainCode": "PEN", "uraian": "Foto Thoraks PA (skrining metastasis paru) & EKG 12 Lead",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "CM-11", "domainCode": "TIN", "uraian": "Informed consent tindakan bedah onkologi dan anestesi terintegrasi",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 3.0, "jadwal": [1]
            },
            {
                "id": "CM-12", "domainCode": "TIN", "uraian": "Mastektomi Radikal Modifikasi / Breast Conserving Surgery ± Diseksi KGB Aksila",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 3.0, "jadwal": [2]
            },
            {
                "id": "CM-13", "domainCode": "OBT", "uraian": "Antibiotik Profilaksis (Cefazolin 2g IV atau sesuai formularium) 30-60 menit pra-insisi",
                "ppa": "DPJP", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 3.0, "jadwal": [2]
            },
            {
                "id": "CM-14", "domainCode": "OBT", "uraian": "Analgetik pasca-bedah bertahap (Paracetamol IV / NSAID)",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": False, "bobot": 1.0, "jadwal": [2, 3, 4]
            },
            {
                "id": "CM-15", "domainCode": "OBT", "uraian": "Analgetik Opioid (Tramadol/Ketorolak) bila nyeri berat VAS ≥ 7",
                "ppa": "DPJP", "tipe": "KONDISIONAL", "isKritis": False, "bobot": 1.0, "jadwal": [2, 3]
            },
            {
                "id": "CM-16", "domainCode": "GIZ", "uraian": "Skrining gizi awal & edukasi preskripsi diet pra/pasca-bedah bertahap",
                "ppa": "AHLI_GIZI", "tipe": "WAJIB", "isKritis": False, "bobot": 1.0, "jadwal": [1, 2]
            },
            {
                "id": "CM-17", "domainCode": "FAR", "uraian": "Rekonsiliasi obat saat admisi dan pengkajian interaksi obat",
                "ppa": "APOTEKER", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "CM-18", "domainCode": "FAR", "uraian": "Rekonsiliasi obat pulang & konseling informasi obat pulang (PIO)",
                "ppa": "APOTEKER", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 2.0, "jadwal": [5]
            },
            {
                "id": "CM-19", "domainCode": "REH", "uraian": "Edukasi latihan rehabilitasi gerak lengan bertahap & pencegahan limfedema",
                "ppa": "FISIOTERAPIS", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [3, 4, 5]
            },
            {
                "id": "CM-20", "domainCode": "EDU", "uraian": "Penjelasan tindak lanjut: hasil PA (ER, PR, HER2, Ki-67), rencana terapi adjuvan & SADARI",
                "ppa": "DPJP", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 2.0, "jadwal": [5]
            },
            {
                "id": "CM-21", "domainCode": "OUT", "uraian": "Luka operasi baik/kering, produksi drain minimal (<30cc/24j), drain dicabut",
                "ppa": "DPJP", "tipe": "OUTCOME", "isKritis": True, "bobot": 2.0, "jadwal": [5]
            },
            {
                "id": "CM-22", "domainCode": "OUT", "uraian": "Pasien keluar hidup & Length of Stay (LOS) ≤ 5 hari",
                "ppa": "DPJP", "tipe": "OUTCOME", "isKritis": True, "bobot": 3.0, "jadwal": [5]
            }
        ]
    },
    {
        "id": "CP-DMCKD-002",
        "nomorCp": "CP/PD-NEFRO/02/2026",
        "nama": "Diabetes Melitus Tipe II dengan Komplikasi CKD",
        "versi": "1.0",
        "tanggalBerlaku": "2026-09-01",
        "ksm": "Penyakit Dalam (Nefrologi & Endokrin)",
        "jumlahHariStandar": 7,
        "losTarget": 7,
        "kriteriaInklusi": "DM tipe II dengan komplikasi nefropati diabetik / penurunan fungsi ginjal kronik (eGFR < 60 mL/min atau proteinuria persisten).",
        "kriteriaEksklusi": "Ketoasidosis Diabetikum (KAD), Sindrom Hiperosmolar Hiperglikemik (HHS), AKI stadium III yang memerlukan dialisis emergensi langsung di ICU.",
        "kodeIcd10": "E11.22",
        "kodeIcd9": "99.18, 38.95",
        "statusAktif": True,
        "items": [
            {
                "id": "DM-01", "domainCode": "MED", "uraian": "Asesmen klinis komplikasi mikrovaskular & makrovaskular, evaluasi hidrasi dan edema",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "DM-02", "domainCode": "MED", "uraian": "Visite harian DPJP dan penyesuaian dosis terapi hipoglikemik harian",
                "ppa": "DPJP", "tipe": "FREKUENSI", "isKritis": False, "bobot": 1.0, "jadwal": [1, 2, 3, 4, 5, 6, 7]
            },
            {
                "id": "DM-03", "domainCode": "KEP", "uraian": "Asesmen keperawatan, pemantauan tanda vital, EWS & skrining risiko jatuh",
                "ppa": "PERAWAT", "tipe": "FREKUENSI", "isKritis": False, "bobot": 1.0, "jadwal": [1, 2, 3, 4, 5, 6, 7]
            },
            {
                "id": "DM-04", "domainCode": "KEP", "uraian": "Monitoring ketat tanda hipoglikemia & protokol penanganan hipoglikemia darurat",
                "ppa": "PERAWAT", "tipe": "FREKUENSI", "isKritis": True, "bobot": 3.0, "jadwal": [1, 2, 3, 4, 5, 6, 7]
            },
            {
                "id": "DM-05", "domainCode": "KEP", "uraian": "Pencatatan balans cairan ketat per 24 jam (intake cairan, diuresis, insensible water loss)",
                "ppa": "PERAWAT", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1, 2, 3, 4, 5, 6, 7]
            },
            {
                "id": "DM-06", "domainCode": "PEN", "uraian": "Pemeriksaan GDS serial harian (pre-prandial & post-prandial / per 6 jam)",
                "ppa": "PERAWAT", "tipe": "FREKUENSI", "isKritis": True, "bobot": 3.0, "jadwal": [1, 2, 3, 4, 5, 6, 7]
            },
            {
                "id": "DM-07", "domainCode": "PEN", "uraian": "Pemeriksaan fungsi ginjal serial: Ureum, Kreatinin Serum, eGFR",
                "ppa": "DPJP", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 2.0, "jadwal": [1, 4, 7]
            },
            {
                "id": "DM-08", "domainCode": "PEN", "uraian": "Pemeriksaan Elektrolit (Na, K, Cl) & Analisa Gas Darah bila ada asidosis",
                "ppa": "DPJP", "tipe": "KONDISIONAL", "isKritis": True, "bobot": 2.0, "jadwal": [1, 2, 3]
            },
            {
                "id": "DM-09", "domainCode": "PEN", "uraian": "HbA1c & Urinalisis lengkap (proteinuria, sedimen urin)",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": False, "bobot": 1.0, "jadwal": [1]
            },
            {
                "id": "DM-10", "domainCode": "PEN", "uraian": "EKG 12 Lead & Foto Rontgen Thoraks PA",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": False, "bobot": 1.0, "jadwal": [1]
            },
            {
                "id": "DM-11", "domainCode": "GIZ", "uraian": "Asesmen gizi & penetapan diet DM Ginjal Rendah Protein (0.6 - 0.8 g/kgBB)",
                "ppa": "AHLI_GIZI", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "DM-12", "domainCode": "EDU", "uraian": "Edukasi gizi terintegrasi untuk pasien & keluarga (diet restriksi kalium, fosfat, natrium)",
                "ppa": "AHLI_GIZI", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 2.0, "jadwal": [1, 2]
            },
            {
                "id": "DM-13", "domainCode": "GIZ", "uraian": "Monitoring dan evaluasi (Monev) asupan makan (target >80% kebutuhan energi)",
                "ppa": "AHLI_GIZI", "tipe": "JENDELA_WAKTU", "isKritis": False, "bobot": 1.0, "jadwal": [4, 5]
            },
            {
                "id": "DM-14", "domainCode": "FAR", "uraian": "Rekonsiliasi obat saat admisi & penyesuaian dosis obat terhadap klirens kreatinin",
                "ppa": "APOTEKER", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 3.0, "jadwal": [1]
            },
            {
                "id": "DM-15", "domainCode": "OBT", "uraian": "Antihiperglikemi: Injeksi Insulin (Regimen Basal-Bolus / Sliding Scale)",
                "ppa": "DPJP", "tipe": "EKSKLUSIF", "grupEksklusif": "DM_ANTIDIABETIK", "isKritis": True, "bobot": 3.0, "jadwal": [1, 2, 3, 4, 5, 6, 7]
            },
            {
                "id": "DM-16", "domainCode": "OBT", "uraian": "Antihiperglikemi: Obat Hipoglikemik Oral (OHO) aman ginjal (bila eGFR >30 mL/min)",
                "ppa": "DPJP", "tipe": "EKSKLUSIF", "grupEksklusif": "DM_ANTIDIABETIK", "isKritis": False, "bobot": 1.0, "jadwal": [1, 2, 3, 4, 5, 6, 7]
            },
            {
                "id": "DM-17", "domainCode": "TIN", "uraian": "Hemodialisis akut / insersi kateter ganda (CDL) bila ada sindrom uremik berat / anuria",
                "ppa": "DPJP", "tipe": "KONDISIONAL", "isKritis": True, "bobot": 3.0, "jadwal": [2, 3, 4]
            },
            {
                "id": "DM-18", "domainCode": "EDU", "uraian": "Edukasi perawatan kaki diabetik & teknik penyuntikan insulin mandiri di rumah",
                "ppa": "PERAWAT", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 2.0, "jadwal": [5, 6, 7]
            },
            {
                "id": "DM-19", "domainCode": "OUT", "uraian": "Kadar GDS terkontrol (140-180 mg/dL), bebas episode hipoglikemia, hemodinamik stabil",
                "ppa": "DPJP", "tipe": "OUTCOME", "isKritis": True, "bobot": 2.0, "jadwal": [7]
            },
            {
                "id": "DM-20", "domainCode": "OUT", "uraian": "Status keluar hidup & Length of Stay (LOS) ≤ 7 hari",
                "ppa": "DPJP", "tipe": "OUTCOME", "isKritis": True, "bobot": 3.0, "jadwal": [7]
            }
        ]
    },
    {
        "id": "CP-HIV-003",
        "nomorCp": "CP/PD-INF/03/2026",
        "nama": "Human Immunodeficiency Virus (HIV / AIDS)",
        "versi": "1.0",
        "tanggalBerlaku": "2026-09-01",
        "ksm": "Penyakit Dalam (Alergi Imunologi / Tropis)",
        "jumlahHariStandar": 6,
        "losTarget": 6,
        "kriteriaInklusi": "Pasien terkonfirmasi HIV stadium 3-4 atau pasien baru dengan manifestasi infeksi oportunistik (PCP, TB, Toxoplasmosis, Candidiasis).",
        "kriteriaEksklusi": "Pasien rawat jalan tanpa komplikasi infeksi oportunistik berat.",
        "kodeIcd10": "B20",
        "kodeIcd9": "99.29",
        "statusAktif": True,
        "items": [
            {
                "id": "HIV-01", "domainCode": "MED", "uraian": "Asesmen klinis infeksi oportunistik, penetapan stadium klinis WHO & evaluasi komorbid",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "HIV-02", "domainCode": "MED", "uraian": "Konsultasi lintas spesialis (Paru, Neurologi, Kulit) sesuai keterlibatan organ",
                "ppa": "KONSULTAN", "tipe": "KONDISIONAL", "isKritis": False, "bobot": 1.0, "jadwal": [1, 2, 3]
            },
            {
                "id": "HIV-03", "domainCode": "KEP", "uraian": "Asesmen keperawatan, tanda vital & penerapan kewaspadaan transmisi / isolasi",
                "ppa": "PERAWAT", "tipe": "FREKUENSI", "isKritis": True, "bobot": 2.0, "jadwal": [1, 2, 3, 4, 5, 6]
            },
            {
                "id": "HIV-04", "domainCode": "PEN", "uraian": "Tes diagnosis bertingkat HIV sesuai alur nasional (Rapid Test 3 metode / Immunoassay)",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 3.0, "jadwal": [1]
            },
            {
                "id": "HIV-05", "domainCode": "PEN", "uraian": "Pemeriksaan hitung CD4 serum",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1, 2]
            },
            {
                "id": "HIV-06", "domainCode": "PEN", "uraian": "Foto Thoraks PA & Tes Cepat Molekuler (TCM) Sputum bila ada batuk/curiga TB",
                "ppa": "DPJP", "tipe": "KONDISIONAL", "isKritis": True, "bobot": 2.0, "jadwal": [1, 2]
            },
            {
                "id": "HIV-07", "domainCode": "GIZ", "uraian": "Skrining gizi awal, penanganan wasting syndrome & diet Tinggi Kalori Tinggi Protein",
                "ppa": "AHLI_GIZI", "tipe": "WAJIB", "isKritis": False, "bobot": 1.0, "jadwal": [1]
            },
            {
                "id": "HIV-08", "domainCode": "EDU", "uraian": "Edukasi gizi & sanitasi makanan higienis (food safety)",
                "ppa": "AHLI_GIZI", "tipe": "JENDELA_WAKTU", "isKritis": False, "bobot": 1.0, "jadwal": [1, 2]
            },
            {
                "id": "HIV-09", "domainCode": "GIZ", "uraian": "Monev asupan nutrisi dan toleransi makan",
                "ppa": "AHLI_GIZI", "tipe": "JENDELA_WAKTU", "isKritis": False, "bobot": 1.0, "jadwal": [4, 5]
            },
            {
                "id": "HIV-10", "domainCode": "FAR", "uraian": "Rekonsiliasi obat & konseling kepatuhan minum obat (Adherence Counseling ≥ 95%)",
                "ppa": "APOTEKER", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 3.0, "jadwal": [1, 6]
            },
            {
                "id": "HIV-11", "domainCode": "FAR", "uraian": "Skrining interaksi obat (DDI) antara ARV dan obat IO (Rifampisin, Flukonazol)",
                "ppa": "APOTEKER", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [2, 3, 4, 5, 6]
            },
            {
                "id": "HIV-12", "domainCode": "OBT", "uraian": "Profilaksis Kotrimoksazol (CPT) bila CD4 < 200 sel/uL atau stadium klinis 3-4",
                "ppa": "DPJP", "tipe": "KONDISIONAL", "isKritis": True, "bobot": 2.0, "jadwal": [1, 2, 3, 4, 5, 6]
            },
            {
                "id": "HIV-13", "domainCode": "OBT", "uraian": "Regimen ARV Lini 1: TDF + 3TC + DTG (Pilihan Utama)",
                "ppa": "DPJP", "tipe": "EKSKLUSIF", "grupEksklusif": "HIV_ARV_REGIMEN", "isKritis": True, "bobot": 3.0, "jadwal": [3, 4, 5, 6]
            },
            {
                "id": "HIV-14", "domainCode": "OBT", "uraian": "Regimen ARV Lini 1: TDF + 3TC + EFV (Alternatif bila ada kontraindikasi DTG)",
                "ppa": "DPJP", "tipe": "EKSKLUSIF", "grupEksklusif": "HIV_ARV_REGIMEN", "isKritis": True, "bobot": 3.0, "jadwal": [3, 4, 5, 6]
            },
            {
                "id": "HIV-15", "domainCode": "EDU", "uraian": "Konseling VCT, penerimaan diri & rujukan ke Poli Perawatan, Dukungan & Pengobatan (PDP)",
                "ppa": "PERAWAT", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 2.0, "jadwal": [2, 3, 4, 5]
            },
            {
                "id": "HIV-16", "domainCode": "OUT", "uraian": "Gejala infeksi oportunistik akut teratasi, toleransi ARV/IO baik, terdaftar di SIHA",
                "ppa": "DPJP", "tipe": "OUTCOME", "isKritis": True, "bobot": 2.0, "jadwal": [6]
            },
            {
                "id": "HIV-17", "domainCode": "OUT", "uraian": "Status keluar hidup & Length of Stay (LOS) ≤ 6 hari",
                "ppa": "DPJP", "tipe": "OUTCOME", "isKritis": True, "bobot": 3.0, "jadwal": [6]
            }
        ]
    },
    {
        "id": "CP-STROKE-NON-004",
        "nomorCp": "CP/SARAF/04/2026",
        "nama": "Stroke Non Perdarahan (Stroke Iskemik / Infark)",
        "versi": "1.0",
        "tanggalBerlaku": "2026-09-01",
        "ksm": "Neurologi",
        "jumlahHariStandar": 6,
        "losTarget": 6,
        "kriteriaInklusi": "Defisit neurologis fokal akut onset < 72 jam, terbukti non-perdarahan pada neuroimaging.",
        "kriteriaEksklusi": "Perdarahan intrakranial (ICH/SAH), TIA (sembuh sempurna <24 jam), kelainan struktural non-vaskular (tumor otak, abses).",
        "kodeIcd10": "I63.9",
        "kodeIcd9": "87.03, 99.10",
        "statusAktif": True,
        "items": [
            {
                "id": "SNP-01", "domainCode": "MED", "uraian": "Asesmen neurologis awal: Skala NIHSS, Skor GCS, onset waktu serangan",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 3.0, "jadwal": [1]
            },
            {
                "id": "SNP-02", "domainCode": "MED", "uraian": "Diagnosis Stroke Iskemik: Trombosis Serebri",
                "ppa": "DPJP", "tipe": "EKSKLUSIF", "grupEksklusif": "STROKE_DX_SUBTYPE", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "SNP-03", "domainCode": "MED", "uraian": "Diagnosis Stroke Iskemik: Emboli Serebri",
                "ppa": "DPJP", "tipe": "EKSKLUSIF", "grupEksklusif": "STROKE_DX_SUBTYPE", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "SNP-04", "domainCode": "MED", "uraian": "Diagnosis Stroke Iskemik: Infark Rekuren",
                "ppa": "DPJP", "tipe": "EKSKLUSIF", "grupEksklusif": "STROKE_DX_SUBTYPE", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "SNP-05", "domainCode": "PEN", "uraian": "CT Scan Kepala Non-Kontras Cito (Golden hour menyingkirkan perdarahan)",
                "ppa": "DPJP", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 3.0, "jadwal": [1]
            },
            {
                "id": "SNP-06", "domainCode": "PEN", "uraian": "Laboratorium Cito: PT, APTT, INR, GDS, Trombosit, Elektrolit",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "SNP-07", "domainCode": "PEN", "uraian": "Profil Lipid (Kolesterol, LDL, HDL, Trigliserida) & Asam Urat",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": False, "bobot": 1.0, "jadwal": [2]
            },
            {
                "id": "SNP-08", "domainCode": "KEP", "uraian": "Asesmen skrining fungsi menelan awal (GUSS / Dysphagia Screen) sebelum asupan oral",
                "ppa": "PERAWAT", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 3.0, "jadwal": [1]
            },
            {
                "id": "SNP-09", "domainCode": "KEP", "uraian": "Posisi elevasi kepala 30 derajat, pemantauan TTV, SaO2, dan GCS per 4 jam",
                "ppa": "PERAWAT", "tipe": "FREKUENSI", "isKritis": True, "bobot": 2.0, "jadwal": [1, 2, 3, 4, 5, 6]
            },
            {
                "id": "SNP-10", "domainCode": "GIZ", "uraian": "Asesmen gizi & pemilihan rute nutrisi (Oral vs Sonde NGT bila disfagia)",
                "ppa": "AHLI_GIZI", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1, 2]
            },
            {
                "id": "SNP-11", "domainCode": "FAR", "uraian": "Rekonsiliasi obat saat admisi & verifikasi riwayat obat rutin pasien",
                "ppa": "APOTEKER", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "SNP-12", "domainCode": "OBT", "uraian": "Terapi Antiplatelet: Aspilet (Aspirin) 80 - 160 mg",
                "ppa": "DPJP", "tipe": "EKSKLUSIF", "grupEksklusif": "STROKE_ANTIPLATELET", "isKritis": True, "bobot": 3.0, "jadwal": [1, 2, 3, 4, 5, 6]
            },
            {
                "id": "SNP-13", "domainCode": "OBT", "uraian": "Terapi Antiplatelet: Clopidogrel 75 mg (Alternatif alergi/intoleransi aspirin)",
                "ppa": "DPJP", "tipe": "EKSKLUSIF", "grupEksklusif": "STROKE_ANTIPLATELET", "isKritis": True, "bobot": 3.0, "jadwal": [1, 2, 3, 4, 5, 6]
            },
            {
                "id": "SNP-14", "domainCode": "OBT", "uraian": "Terapi Antiplatelet: DAPT (Aspirin + Clopidogrel) pada stroke minor / TIA risiko tinggi",
                "ppa": "DPJP", "tipe": "EKSKLUSIF", "grupEksklusif": "STROKE_ANTIPLATELET", "isKritis": True, "bobot": 3.0, "jadwal": [1, 2, 3, 4, 5, 6]
            },
            {
                "id": "SNP-15", "domainCode": "OBT", "uraian": "Statin Intensitas Tinggi: Atorvastatin 20-40 mg / Simvastatin",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1, 2, 3, 4, 5, 6]
            },
            {
                "id": "SNP-16", "domainCode": "OBT", "uraian": "Neuroprotektor (Citicoline / Piracetam)",
                "ppa": "DPJP", "tipe": "OPSIONAL", "isKritis": False, "bobot": 1.0, "jadwal": [1, 2, 3, 4, 5, 6]
            },
            {
                "id": "SNP-17", "domainCode": "REH", "uraian": "Fisioterapi motorik, alih baring per 2 jam & terapi wicara bila afasia",
                "ppa": "FISIOTERAPIS", "tipe": "KONDISIONAL", "isKritis": True, "bobot": 2.0, "jadwal": [2, 3, 4, 5, 6]
            },
            {
                "id": "SNP-18", "domainCode": "FAR", "uraian": "Edukasi obat saat pemberian pertama & rekonsiliasi obat saat pemulangan",
                "ppa": "APOTEKER", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 2.0, "jadwal": [1, 6]
            },
            {
                "id": "SNP-19", "domainCode": "OUT", "uraian": "Skor NIHSS membaik / stabil, bebas komplikasi pneumonia aspirasi & dekubitus",
                "ppa": "DPJP", "tipe": "OUTCOME", "isKritis": True, "bobot": 2.0, "jadwal": [6]
            },
            {
                "id": "SNP-20", "domainCode": "OUT", "uraian": "Status keluar hidup & Length of Stay (LOS) ≤ 6 hari",
                "ppa": "DPJP", "tipe": "OUTCOME", "isKritis": True, "bobot": 3.0, "jadwal": [6]
            }
        ]
    },
    {
        "id": "CP-STROKE-PERD-005",
        "nomorCp": "CP/SARAF/05/2026",
        "nama": "Stroke Perdarahan (Intraserebral / Subaraknoid)",
        "versi": "1.0",
        "tanggalBerlaku": "2026-09-01",
        "ksm": "Neurologi & Bedah Saraf",
        "jumlahHariStandar": 14,
        "losTarget": 14,
        "kriteriaInklusi": "Defisit neurologis fokal akut disertai bukti hiperdensitas perdarahan intrakranial pada neuroimaging.",
        "kriteriaEksklusi": "Perdarahan intrakranial sekunder akibat trauma kapitis berat, ruptur AVM kompleks rujukan bedah khusus.",
        "kodeIcd10": "I61.9, I60.9",
        "kodeIcd9": "87.03, 01.24",
        "statusAktif": True,
        "items": [
            {
                "id": "SP-01", "domainCode": "MED", "uraian": "Asesmen neurologis darurat: Skor GCS, refleks batang otak, diameter & refleks pupil",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 3.0, "jadwal": [1]
            },
            {
                "id": "SP-02", "domainCode": "MED", "uraian": "Diagnosis Stroke Perdarahan: Perdarahan Intraserebral (PIS / ICH)",
                "ppa": "DPJP", "tipe": "EKSKLUSIF", "grupEksklusif": "STROKE_BLEED_DX", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "SP-03", "domainCode": "MED", "uraian": "Diagnosis Stroke Perdarahan: Perdarahan Subaraknoid (PSA / SAH)",
                "ppa": "DPJP", "tipe": "EKSKLUSIF", "grupEksklusif": "STROKE_BLEED_DX", "isKritis": True, "bobot": 2.0, "jadwal": [1]
            },
            {
                "id": "SP-04", "domainCode": "MED", "uraian": "Konsultasi Bedah Saraf (evaluasi operatif evakuasi hematom / pasang EVD)",
                "ppa": "KONSULTAN", "tipe": "KONDISIONAL", "isKritis": True, "bobot": 3.0, "jadwal": [1, 2]
            },
            {
                "id": "SP-05", "domainCode": "PEN", "uraian": "CT Scan Kepala Non-Kontras Cito (Hitung volume perdarahan & pergeseran garis tengah)",
                "ppa": "DPJP", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 3.0, "jadwal": [1]
            },
            {
                "id": "SP-06", "domainCode": "PEN", "uraian": "Skrining koagulopati cito: PT, APTT, INR, Trombosit",
                "ppa": "DPJP", "tipe": "WAJIB", "isKritis": True, "bobot": 3.0, "jadwal": [1]
            },
            {
                "id": "SP-07", "domainCode": "KEP", "uraian": "Monitoring ketat tanda kenaikan TIK, pupil, GCS & EWS per 1-2 jam di Unit Stroke / HCU",
                "ppa": "PERAWAT", "tipe": "FREKUENSI", "isKritis": True, "bobot": 3.0, "jadwal": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
            },
            {
                "id": "SP-08", "domainCode": "KEP", "uraian": "Protokol pencegahan kenaikan TIK (elevasi kepala 30°, hindari fleksi leher & batuk/mengejan)",
                "ppa": "PERAWAT", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
            },
            {
                "id": "SP-09", "domainCode": "KEP", "uraian": "Skrining fungsi menelan dan pemasangan sonde NGT bila disfagia / GCS <13",
                "ppa": "PERAWAT", "tipe": "JENDELA_WAKTU", "isKritis": True, "bobot": 3.0, "jadwal": [1, 2]
            },
            {
                "id": "SP-10", "domainCode": "GIZ", "uraian": "Preskripsi nutrisi enteral bertahap via NGT (Energi 25-30 kkal/kgBB, Rendah Garam)",
                "ppa": "AHLI_GIZI", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
            },
            {
                "id": "SP-11", "domainCode": "FAR", "uraian": "Rekonsiliasi obat & pemantauan target penurunan tekanan darah aman (TDS 140-160 mmHg)",
                "ppa": "APOTEKER", "tipe": "WAJIB", "isKritis": True, "bobot": 2.0, "jadwal": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
            },
            {
                "id": "SP-12", "domainCode": "OBT", "uraian": "Antihipertensi IV kontinu (Nicardipine / Diltiazem drip) bila TDS > 180 mmHg",
                "ppa": "DPJP", "tipe": "KONDISIONAL", "isKritis": True, "bobot": 3.0, "jadwal": [1, 2, 3]
            },
            {
                "id": "SP-13", "domainCode": "OBT", "uraian": "Manitol 20% infus (Anti-edema serebral) bila ada tanda peningkatan TIK",
                "ppa": "DPJP", "tipe": "KONDISIONAL", "isKritis": True, "bobot": 2.0, "jadwal": [1, 2, 3, 4, 5]
            },
            {
                "id": "SP-14", "domainCode": "OBT", "uraian": "Nimodipine 60 mg per 4 jam (Khusus pencegahan vasospasme pada SAH)",
                "ppa": "DPJP", "tipe": "KONDISIONAL", "isKritis": True, "bobot": 3.0, "jadwal": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
            },
            {
                "id": "SP-15", "domainCode": "OBT", "uraian": "Antikonvulsan profilaksis (Fenitoin / Levetiracetam) bila ada kejang / perdarahan kortikal",
                "ppa": "DPJP", "tipe": "KONDISIONAL", "isKritis": False, "bobot": 1.0, "jadwal": [1, 2, 3, 4, 5, 6, 7]
            },
            {
                "id": "SP-16", "domainCode": "TIN", "uraian": "Tindakan Kraniotomi dekompresi / Evakuasi hematom / Pemasangan drain EVD",
                "ppa": "DPJP", "tipe": "KONDISIONAL", "isKritis": True, "bobot": 3.0, "jadwal": [1, 2, 3]
            },
            {
                "id": "SP-17", "domainCode": "REH", "uraian": "Alih baring pasif, positioning mencegah kontraktur & fisioterapi dada pasif",
                "ppa": "FISIOTERAPIS", "tipe": "KONDISIONAL", "isKritis": False, "bobot": 1.0, "jadwal": [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
            },
            {
                "id": "SP-18", "domainCode": "OUT", "uraian": "Kesadaran stabil/membaik, TIK terkontrol, bebas komplikasi ulkus dekubitus",
                "ppa": "DPJP", "tipe": "OUTCOME", "isKritis": True, "bobot": 2.0, "jadwal": [14]
            },
            {
                "id": "SP-19", "domainCode": "OUT", "uraian": "Status keluar hidup & Length of Stay (LOS) ≤ 14 hari",
                "ppa": "DPJP", "tipe": "OUTCOME", "isKritis": True, "bobot": 3.0, "jadwal": [14]
            }
        ]
    }
]

# ==============================================================================
# 3. CP BUILDER & TEMPLATE VALIDATOR
# ==============================================================================

def validate_cp_template(template):
    """
    Validasi aturan CP Builder:
    - Tidak boleh ada item tanpa PPA
    - Grup eksklusif minimal memiliki 2 opsi
    - Harus memiliki nama, nomor CP, jumlah hari standar, dan kode ICD
    """
    errors = []
    if not template.get("nama"):
        errors.append("Nama template Clinical Pathway wajib diisi.")
    if not template.get("nomorCp"):
        errors.append("Nomor dokumen CP wajib diisi.")
    if not template.get("jumlahHariStandar") or int(template["jumlahHariStandar"]) < 1:
        errors.append("Jumlah hari standar rawat minimal 1 hari.")
    
    items = template.get("items", [])
    if not items:
        errors.append("Template CP harus memiliki minimal satu item kegiatan.")
    
    exclusive_groups = {}
    for idx, itm in enumerate(items):
        if not itm.get("ppa"):
            errors.append(f"Item #{idx+1} ('{itm.get('uraian', '')[:30]}') tidak memiliki PPA penanggung jawab.")
        if not itm.get("jadwal") or not isinstance(itm.get("jadwal"), list) or len(itm.get("jadwal")) == 0:
            errors.append(f"Item #{idx+1} tidak memiliki jadwal hari rawat yang valid.")
        
        if itm.get("tipe") == "EKSKLUSIF":
            grp = itm.get("grupEksklusif")
            if not grp:
                errors.append(f"Item eksklusif #{idx+1} wajib mencantumkan nama grupEksklusif.")
            else:
                exclusive_groups[grp] = exclusive_groups.get(grp, 0) + 1

    for grp_name, count in exclusive_groups.items():
        if count < 2:
            errors.append(f"Grup eksklusif '{grp_name}' hanya memiliki {count} pilihan (minimal 2 pilihan).")

    return {
        "isValid": len(errors) == 0,
        "errors": errors
    }

def save_master_templates(templates):
    with open(TEMPLATES_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)
    return TEMPLATES_JSON_PATH

def load_master_templates():
    if os.path.exists(TEMPLATES_JSON_PATH):
        try:
            with open(TEMPLATES_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # fallback to seed
    save_master_templates(SEED_TEMPLATES)
    return SEED_TEMPLATES

# ==============================================================================
# 4. FORMULA LOGIKA AUDIT KEPATUHAN MUTU (BERBOBOT, MENTAH, ADJUSTED, BUNDLE)
# ==============================================================================

def calculate_patient_compliance(enrollment, template):
    """
    Menghitung kepatuhan CP untuk satu episode pasien:
    - Kepatuhan Mentah: Terlaksana / Wajib * 100
    - Kepatuhan Adjusted: Terlaksana / (Wajib - N/A Terjustifikasi) * 100
    - Bundle Kritis: All-or-none untuk item berstatus isKritis == True
    - Kepatuhan per PPA & per Domain
    - Penanganan Pasien Drop-out (hanya dihitung sampai hari terakhir di CP)
    """
    executions = enrollment.get("executions", {})
    variances = enrollment.get("variances", [])
    max_day = enrollment.get("hariTerakhirCp", template.get("jumlahHariStandar", 5))

    total_wajib_scheduled = 0
    total_terlaksana = 0
    total_na_justified = 0
    total_tidak_terlaksana = 0

    critical_bundle_passed = True
    critical_items_count = 0
    critical_items_failed = []

    ppa_stats = {}
    domain_stats = {}

    for item in template.get("items", []):
        item_id = item["id"]
        ppa = item.get("ppa", "LAINNYA")
        dom = item.get("domainCode", "UMUM")
        is_kritis = item.get("isKritis", False)
        bobot = float(item.get("bobot", 1.0))
        tipe = item.get("tipe", "WAJIB")

        if ppa not in ppa_stats:
            ppa_stats[ppa] = {"wajib": 0, "terlaksana": 0, "na": 0}
        if dom not in domain_stats:
            domain_stats[dom] = {"wajib": 0, "terlaksana": 0, "na": 0}

        for day in item.get("jadwal", []):
            if day > max_day:
                continue  # Lewati jika pasien sudah keluar dari CP sebelum hari ini

            key = f"{item_id}_d{day}"
            status = executions.get(key, "TERLAKSANA")  # default terlaksana jika simulasi patuh

            # Jika ini grup eksklusif, evaluasi per grup
            # Cek apakah ada varian
            var_match = next((v for v in variances if v.get("itemId") == item_id and v.get("hariKe") == day), None)

            if status == "N/A":
                # N/A dinilai terjustifikasi jika memiliki varian berjustifikasi / indikasi khusus
                is_justified = var_match.get("isJustified", True) if var_match else True
                if is_justified:
                    total_na_justified += 1
                    ppa_stats[ppa]["na"] += 1
                    domain_stats[dom]["na"] += 1
                    total_wajib_scheduled += 1
                else:
                    # N/A tanpa justifikasi dihitung sebagai TIDAK TERLAKSANA
                    total_wajib_scheduled += 1
                    total_tidak_terlaksana += 1
                    ppa_stats[ppa]["wajib"] += 1
                    domain_stats[dom]["wajib"] += 1
                    if is_kritis:
                        critical_bundle_passed = False
                        critical_items_failed.append(f"{item['uraian'][:35]} (Hari {day})")
            elif status == "TERLAKSANA":
                total_wajib_scheduled += 1
                total_terlaksana += 1
                ppa_stats[ppa]["wajib"] += 1
                ppa_stats[ppa]["terlaksana"] += 1
                domain_stats[dom]["wajib"] += 1
                domain_stats[dom]["terlaksana"] += 1
            elif status == "TIDAK_TERLAKSANA":
                total_wajib_scheduled += 1
                total_tidak_terlaksana += 1
                ppa_stats[ppa]["wajib"] += 1
                domain_stats[dom]["wajib"] += 1
                if is_kritis:
                    critical_bundle_passed = False
                    critical_items_failed.append(f"{item['uraian'][:35]} (Hari {day})")

            if is_kritis:
                critical_items_count += 1

    # Rumus Kepatuhan Mentah: Terlaksana / Wajib
    raw_denom = total_wajib_scheduled
    raw_score = round((total_terlaksana / raw_denom * 100), 1) if raw_denom > 0 else 100.0

    # Rumus Kepatuhan Adjusted: Terlaksana / (Wajib - N/A Terjustifikasi)
    adj_denom = total_wajib_scheduled - total_na_justified
    adj_score = round((total_terlaksana / adj_denom * 100), 1) if adj_denom > 0 else 100.0

    # Kategori Ambang Mutu
    if adj_score >= 80.0 and critical_bundle_passed:
        mutu_category = "HIJAU"  # Memenuhi standar mutu
    elif adj_score >= 70.0:
        mutu_category = "KUNING"  # Peringatan / Perlu Evaluasi
    else:
        mutu_category = "MERAH"  # Substandar / Wajib Audit

    # Hitung persentase per PPA
    ppa_summary = {}
    for p, val in ppa_stats.items():
        v_adj_den = val["wajib"]
        pct = round((val["terlaksana"] / v_adj_den * 100), 1) if v_adj_den > 0 else 100.0
        ppa_summary[p] = {
            "terlaksana": val["terlaksana"],
            "wajib": val["wajib"],
            "na": val["na"],
            "compliancePct": pct
        }

    # Hitung persentase per Domain
    domain_summary = {}
    for d, val in domain_stats.items():
        d_adj_den = val["wajib"]
        pct = round((val["terlaksana"] / d_adj_den * 100), 1) if d_adj_den > 0 else 100.0
        domain_summary[d] = {
            "terlaksana": val["terlaksana"],
            "wajib": val["wajib"],
            "na": val["na"],
            "compliancePct": pct
        }

    return {
        "totalWajibScheduled": total_wajib_scheduled,
        "totalTerlaksana": total_terlaksana,
        "totalNaJustified": total_na_justified,
        "totalTidakTerlaksana": total_tidak_terlaksana,
        "rawScore": raw_score,
        "adjScore": adj_score,
        "criticalBundlePassed": critical_bundle_passed,
        "criticalItemsFailed": critical_items_failed,
        "mutuCategory": mutu_category,
        "ppaSummary": ppa_summary,
        "domainSummary": domain_summary
    }

# ==============================================================================
# ==============================================================================
# 4.1 ENGINE PENAPISAN DIAGNOSIS & DENOMINATOR KLINIS RESMI
# ==============================================================================

def match_clinical_pathway_diagnosis(diag):
    """
    Penapisan diagnosis klinis pasien berdasarkan 5 Clinical Pathway resmi RSUD dr. Soedarso.
    Hanya pasien dengan diagnosa medis yang cocok yang dimasukkan ke dalam DENOMINATOR CP.
    Pasien lain dieksklusi dengan alasan ilmiah terdokumentasi.
    
    Returns: (matched_template_id or None, cp_nama or None, reason_string)
    """
    if not diag:
        return None, None, "Eksklusi: Tidak ada data diagnosa medis di lembar sensus"
        
    text = str(diag).lower().strip()
    
    # 1. CA MAMMAE / KANKER PAYUDARA (ICD-10 C50.-)
    if re.search(r'(?:ca\s*mammae|kanker\s*payudara|carcinoma\s*mammae|neoplasma\s*mammae|tumor\s*mammae)', text):
        return 'CP-MAMMAE-001', 'Kanker Payudara (CA Mammae) Stadium I–II (Bedah Elektif)', 'Inklusi: Diagnosa sesuai Clinical Pathway Kanker Payudara (ICD-10 C50)'
        
    # 2. HIV / AIDS (ICD-10 B20)
    if re.search(r'\b(?:hiv|aids|b20)\b', text):
        return 'CP-HIV-003', 'Human Immunodeficiency Virus (HIV / AIDS)', 'Inklusi: Diagnosa sesuai Clinical Pathway HIV/AIDS (ICD-10 B20)'
        
    # 3. STROKE PERDARAHAN (ICD-10 I61.9, I60.9)
    if re.search(r'\b(?:ich|ivh|sah|stroke\s*p(?:erdarahan|is|ha)|stroke\s*hemor(?:a|o)gik|perdarahan\s*intra\s*serebral|perdarahan\s*subaraknoid)\b', text):
        if 'sequele' in text or 'sekuele' in text or 'lama' in text:
            return None, None, 'Eksklusi: Riwayat / sekuele stroke lama (Bukan episode stroke akut CP)'
        return 'CP-STROKE-PERD-005', 'Stroke Perdarahan (Intraserebral / Subaraknoid)', 'Inklusi: Diagnosa sesuai Clinical Pathway Stroke Perdarahan (ICD-10 I61/I60)'
        
    # 4. STROKE NON PERDARAHAN (ICD-10 I63.9)
    if re.search(r'\b(?:stroke\s*non\s*perdarahan|stroke\s*iskemik|stroke\s*infark|cva\s*infark|infark\s*serebri)\b', text):
        if 'sequele' in text or 'sekuele' in text or 'lama' in text:
            return None, None, 'Eksklusi: Riwayat / sekuele stroke lama (Bukan episode stroke akut CP)'
        return 'CP-STROKE-NON-004', 'Stroke Non Perdarahan (Iskemik / Infark)', 'Inklusi: Diagnosa sesuai Clinical Pathway Stroke Non Perdarahan (ICD-10 I63.9)'
        
    if re.search(r'\b(?:stroke|cva)\b', text) and ('sequele' in text or 'sekuele' in text):
        return None, None, 'Eksklusi: Riwayat / sekuele stroke lama (Bukan episode akut CP)'
        
    # 5. DM TIPE II DENGAN KOMPLIKASI CKD (ICD-10 E11.22)
    has_dm = bool(re.search(r'\b(?:dm|diabetes|hhs|kad|ketoasidosis|hiperglikemi|t2dm|gds\s*tinggi)\b', text))
    has_ckd = bool(re.search(r'(?:ckd|gagal\s*ginjal|dkd|diabetic\s*kidney|nefro|hemodialisis|\bhd\b)', text))
    
    if has_dm and has_ckd:
        return 'CP-DMCKD-002', 'Diabetes Melitus Tipe II dengan Komplikasi CKD', 'Inklusi: Diagnosa sesuai Clinical Pathway DM Tipe II + CKD (ICD-10 E11.22)'
        
    if has_dm and not has_ckd:
        return None, None, 'Eksklusi: DM Tipe II tanpa komplikasi CKD/DKD (Dokumen CP khusus DM Tipe II dengan komplikasi CKD)'
        
    if has_ckd and not has_dm:
        return None, None, 'Eksklusi: CKD tanpa Diabetes Mellitus (Dokumen CP khusus DM Tipe II dengan komplikasi CKD)'
        
    return None, None, 'Eksklusi: Diagnosa medis tidak tercakup dalam 5 Clinical Pathway resmi RSUD dr. Soedarso'


def screen_spreadsheet_patients(recent_days=None, today_data=None, templates=None):
    """
    Melakukan audit penapisan seluruh data pasien dari spreadsheet Ruang Kakap
    terhadap kriteria inklusi & eksklusi 5 Clinical Pathway resmi RSUD dr. Soedarso.
    """
    if not recent_days and not today_data:
        dash_path = os.path.join(CURRENT_DIR, "dashboard_data.json")
        if os.path.exists(dash_path):
            try:
                with open(dash_path, "r", encoding="utf-8") as f:
                    dash = json.load(f)
                    recent_days = dash.get("recentDays", {})
                    today_data = dash.get("today", {})
            except Exception as e:
                print(f"[WARN] Failed to load dashboard_data.json in screen_spreadsheet_patients: {e}")

    if not templates:
        templates = load_master_templates()

    tmpl_map = {t["id"]: t["nama"] for t in templates}

    # 1. Penapisan Pasien Hari Ini (Active Inpatients)
    today_pts = [p for p in (today_data.get("patients", []) if today_data else []) if not p.get("isEmpty")]
    today_included = []
    today_excluded = []
    today_per_cp = {t["id"]: 0 for t in templates}

    for p in today_pts:
        diag = p.get("diagnosis", "")
        cpid, cpname, reason = match_clinical_pathway_diagnosis(diag)
        los_val = 1
        try:
            los_val = int(p.get("los", 1))
        except (ValueError, TypeError):
            los_val = 1

        record = {
            "bed": p.get("bed"),
            "name": p.get("name"),
            "mrNo": p.get("mrNo") or f"RM-K-{p.get('bed')}",
            "diagnosis": diag,
            "doctor": p.get("doctor", "-"),
            "los": los_val,
            "gender": p.get("gender", "L"),
            "age": p.get("age", 50),
            "admissionDate": p.get("admissionDate") or (today_data.get("date", "2026-11-05") if today_data else "2026-11-05"),
            "date": today_data.get("date", "2026-11-05") if today_data else "2026-11-05"
        }
        if cpid:
            record["cpId"] = cpid
            record["cpNama"] = cpname or tmpl_map.get(cpid, cpid)
            record["status"] = "INCLUDED"
            record["inclusionReason"] = reason
            today_included.append(record)
            today_per_cp[cpid] += 1
        else:
            record["status"] = "EXCLUDED"
            record["exclusionReason"] = reason
            today_excluded.append(record)

    # 2. Penapisan Riwayat (Historical Recent Days)
    all_hist_pts = []
    if isinstance(recent_days, dict):
        for dt, day_obj in recent_days.items():
            for p in day_obj.get("patients", []):
                if not p.get("isEmpty"):
                    all_hist_pts.append((dt, p))
    elif isinstance(recent_days, list):
        for day_obj in recent_days:
            dt = day_obj.get("date", "")
            for p in day_obj.get("patients", []):
                if not p.get("isEmpty"):
                    all_hist_pts.append((dt, p))

    hist_included = []
    hist_excluded = []
    hist_per_cp = {t["id"]: 0 for t in templates}
    seen_unique_inc = set()

    for dt, p in all_hist_pts:
        diag = p.get("diagnosis", "")
        cpid, cpname, reason = match_clinical_pathway_diagnosis(diag)
        los_val = 1
        try:
            los_val = int(p.get("los", 1))
        except (ValueError, TypeError):
            los_val = 1

        record = {
            "bed": p.get("bed"),
            "name": p.get("name"),
            "mrNo": p.get("mrNo") or f"RM-K-{p.get('bed')}",
            "diagnosis": diag,
            "doctor": p.get("doctor", "-"),
            "los": los_val,
            "gender": p.get("gender", "L"),
            "age": p.get("age", 50),
            "admissionDate": p.get("admissionDate") or dt,
            "date": dt
        }
        uniq_key = f"{record['name']}_{record['bed']}_{cpid}"
        if cpid:
            record["cpId"] = cpid
            record["cpNama"] = cpname or tmpl_map.get(cpid, cpid)
            record["status"] = "INCLUDED"
            record["inclusionReason"] = reason
            if uniq_key not in seen_unique_inc:
                seen_unique_inc.add(uniq_key)
                hist_included.append(record)
                hist_per_cp[cpid] += 1
        else:
            record["status"] = "EXCLUDED"
            record["exclusionReason"] = reason
            hist_excluded.append(record)

    total_today = len(today_pts)
    inc_today = len(today_included)
    exc_today = len(today_excluded)
    cov_pct_today = round(inc_today / total_today * 100, 1) if total_today > 0 else 0.0

    return {
        "today": {
            "totalInpatients": total_today,
            "denominatorIncluded": inc_today,
            "totalExcluded": exc_today,
            "wardCoveragePct": cov_pct_today,
            "perCpDenominator": today_per_cp,
            "includedPatients": today_included,
            "excludedPatients": today_excluded
        },
        "historical": {
            "totalRecords": len(all_hist_pts),
            "uniqueIncludedCount": len(hist_included),
            "totalExcludedRecords": len(hist_excluded),
            "perCpDenominator": hist_per_cp,
            "includedPatients": hist_included,
            "sampleExcluded": hist_excluded[:50]
        }
    }


def build_real_patient_episodes(included_patients, templates):
    """
    Mengonversi data pasien spreadsheet yang lolos kriteria inklusi CP
    menjadi episode audit mutu yang dapat dinilai langsung dalam checklist.
    """
    real_episodes = []
    tmpl_dict = {t["id"]: t for t in templates}

    for p in included_patients:
        tmpl = tmpl_dict.get(p["cpId"])
        if not tmpl:
            continue

        ep_id = f"EP-REAL-{p['bed']}-{p['date'].replace('-', '')}"
        current_los = p["los"]
        std_days = tmpl["jumlahHariStandar"]
        hari_terakhir = min(current_los, std_days)

        executions = {}
        for itm in tmpl["items"]:
            for d in itm["jadwal"]:
                if d <= hari_terakhir:
                    executions[f"{itm['id']}_d{d}"] = "TERLAKSANA"

        ep = {
            "episodeId": ep_id,
            "mrNo": p["mrNo"],
            "namaPasien": p["name"],
            "gender": p["gender"],
            "usia": p["age"],
            "ruangRawat": f"Ruang Kakap ({p['bed']})",
            "dpjp": p["doctor"],
            "templateId": p["cpId"],
            "cpNama": p["cpNama"],
            "caseProfile": "PASIEN_RIIL_BANGSAL",
            "statusEnrollment": "AKTIF" if p["date"] == "2026-11-05" else "SELESAI",
            "alasanKeluar": None,
            "hariTerakhirCp": hari_terakhir,
            "targetLos": tmpl["losTarget"],
            "realLos": current_los,
            "tglMasuk": p["admissionDate"],
            "tglKeluar": None if p["date"] == "2026-11-05" else p["date"],
            "executions": executions,
            "variances": [],
            "isRealPatient": True,
            "denominatorStatus": "INCLUDED",
            "inclusionReason": p["inclusionReason"],
            "diagnosisSpreadsheet": p["diagnosis"]
        }
        ep["compliance"] = calculate_patient_compliance(ep, tmpl)
        real_episodes.append(ep)

    return real_episodes

# 5. GENERATOR 50 DATA UJI SINTETIS (10 EPISODE PER CP DENGAN VARIASI KLINIS)
# ==============================================================================

def generate_synthetic_dataset():
    """
    Membuat 50 episode pasien sintetis (tanpa data riil pasien)
    10 episode per CP dengan kombinasi kasus:
    - 5 Kasus Patuh Penuh (Raw > 85%, Adj > 90%, Bundle Passed)
    - 3 Kasus Patuh Sebagian (Adj 70-85%, dengan varian berjustifikasi / N/A medis)
    - 1 Kasus Penuh Varian Sistem / Stok Obat / Alat Rusak (Adj < 70%, Bundle Failed)
    - 1 Kasus Drop-out / Keluar dari CP (komplikasi nekrosis flap, rujukan, atau APS)
    """
    templates = load_master_templates()
    dataset = []

    DOCTORS = {
        "CP-MAMMAE-001": ["dr. Antonius, Sp.B(K)Onk", "dr. Budi Setiawan, Sp.B"],
        "CP-DMCKD-002": ["dr. Hendra, Sp.PD, K-EMD", "dr. Dewi Sartika, Sp.PD, K-GH"],
        "CP-HIV-003": ["dr. Faisal, Sp.PD, K-PTI", "dr. Rina Marli, Sp.PD"],
        "CP-STROKE-NON-004": ["dr. Suryadi, Sp.N", "dr. Maya Indah, Sp.N(K)"],
        "CP-STROKE-PERD-005": ["dr. Suryadi, Sp.N", "dr. Agung Prasetyo, Sp.BS"]
    }

    ROOMS = ["Kakap 1", "Kakap 2", "Kakap 3", "Kakap 4", "Kakap 5", "Kakap 6", "Kakap 7", "Kakap 8", "Kakap 9", "Kakap Isolasi"]

    MALE_NAMES = ["Bambang Sutrisno", "Ahmad Zaelani", "Deddy Kurniawan", "Agus Hermawan", "Rudi Hartono", "Eko Prasetyo", "Suparman", "Hendra Wijaya", "Budi Santoso", "Yanto Sukardi"]
    FEMALE_NAMES = ["Siti Aminah", "Sri Wahyuni", "Nurul Hidayah", "Endang Lestari", "Dewi Anggraini", "Ratna Sari", "Fitri Handayani", "Titik Mulyani", "Kartini Sastro", "Lina Marlina"]

    global_ep_counter = 1

    for tmpl in templates:
        cp_id = tmpl["id"]
        cp_name = tmpl["nama"]
        std_days = tmpl["jumlahHariStandar"]
        doc_list = DOCTORS.get(cp_id, ["dr. Spesialis DPJP"])

        for case_idx in range(1, 11):
            ep_id = f"EP-{cp_id[:6]}-{case_idx:02d}"
            mr_no = f"RM-2026-{global_ep_counter:04d}"
            global_ep_counter += 1

            is_female = (cp_id == "CP-MAMMAE-001") or (case_idx % 2 == 0)
            patient_name = FEMALE_NAMES[case_idx - 1] if is_female else MALE_NAMES[case_idx - 1]
            gender = "P" if is_female else "L"
            age = 40 + (case_idx * 3) % 35
            room = ROOMS[(case_idx - 1) % len(ROOMS)]
            dpjp = doc_list[(case_idx - 1) % len(doc_list)]

            # Skenario Kasus
            executions = {}
            variances = []
            status_enrollment = "SELESAI"
            alasan_keluar = None
            hari_terakhir = std_days
            real_los = std_days

            if case_idx <= 5:
                # Kasus 1-5: Patuh Penuh (Semua item terjadwal terlaksana)
                case_profile = "PATUH_PENUH"
                for itm in tmpl["items"]:
                    for d in itm["jadwal"]:
                        executions[f"{itm['id']}_d{d}"] = "TERLAKSANA"

                # Khusus kriteria uji: antiplatelet stroke non perdarahan pilih tepat satu
                if cp_id == "CP-STROKE-NON-004":
                    for d in range(1, std_days + 1):
                        executions[f"SNP-12_d{d}"] = "TERLAKSANA"  # Aspilet terpilih
                        executions[f"SNP-13_d{d}"] = "N/A"
                        executions[f"SNP-14_d{d}"] = "N/A"

                # Khusus kriteria uji: nimodipine SAH vs ICH
                if cp_id == "CP-STROKE-PERD-005":
                    # Pasien ICH, nimodipine otomatis N/A
                    for d in range(1, std_days + 1):
                        executions[f"SP-02_d1"] = "TERLAKSANA"  # ICH
                        executions[f"SP-03_d1"] = "N/A"  # SAH
                        executions[f"SP-14_d{d}"] = "N/A"  # Nimodipine N/A terjustifikasi
                    variances.append({
                        "itemId": "SP-14", "hariKe": 1, "kategori": "PASIEN_PENYAKIT",
                        "alasan": "Diagnosis pasien adalah ICH (bukan SAH), nimodipine N/A sesuai pedoman CP.",
                        "isJustified": True, "petugas": dpjp, "tgl": "2026-11-01"
                    })

            elif case_idx <= 8:
                # Kasus 6-8: Patuh Sebagian dengan Varian Medis Berjustifikasi
                case_profile = "PATUH_SEBAGIAN"
                for itm in tmpl["items"]:
                    for d in itm["jadwal"]:
                        executions[f"{itm['id']}_d{d}"] = "TERLAKSANA"

                # Contoh Varian Medis Berjustifikasi: Alergi Cefazolin pada Mammae -> ganti Ciprofloxacin
                if cp_id == "CP-MAMMAE-001":
                    executions["CM-13_d2"] = "N/A"
                    variances.append({
                        "itemId": "CM-13", "hariKe": 2, "kategori": "PASIEN_PENYAKIT",
                        "alasan": "Pasien memiliki riwayat alergi berat sefalosporin (urtikaria & bronkospasme). Diberikan Ciprofloxacin 400mg IV atas instruksi DPJP.",
                        "isJustified": True, "petugas": dpjp, "tgl": "2026-11-02"
                    })
                elif cp_id == "CP-DMCKD-002":
                    executions["DM-17_d2"] = "N/A"
                    variances.append({
                        "itemId": "DM-17", "hariKe": 2, "kategori": "PASIEN_PENYAKIT",
                        "alasan": "Diuresis pasien membaik >1.5 cc/kgBB/jam, uremia terkompensasi, hemodialisis akut tidak diperlukan.",
                        "isJustified": True, "petugas": dpjp, "tgl": "2026-11-02"
                    })
                elif cp_id == "CP-STROKE-NON-004":
                    # Pasien kontraindikasi aspirin (ulkus peptikum aktif) -> pakai Clopidogrel
                    for d in range(1, std_days + 1):
                        executions[f"SNP-12_d{d}"] = "N/A"
                        executions[f"SNP-13_d{d}"] = "TERLAKSANA"
                    variances.append({
                        "itemId": "SNP-12", "hariKe": 1, "kategori": "PASIEN_PENYAKIT",
                        "alasan": "Riwayat perdarahan saluran cerna atas (melena) 1 minggu lalu, aspirin kontraindikasi; dialihkan ke Clopidogrel 75mg.",
                        "isJustified": True, "petugas": dpjp, "tgl": "2026-11-01"
                    })

            elif case_idx == 9:
                # Kasus 9: Varian Sistem / Rumah Sakit (Alat Rusak / Stok Obat Kosong) -> Menurunkan Mutu
                case_profile = "VARIAN_SISTEM_RS"
                for itm in tmpl["items"]:
                    for d in itm["jadwal"]:
                        executions[f"{itm['id']}_d{d}"] = "TERLAKSANA"

                if cp_id == "CP-STROKE-NON-004":
                    executions["SNP-05_d1"] = "TIDAK_TERLAKSANA"
                    variances.append({
                        "itemId": "SNP-05", "hariKe": 1, "kategori": "SISTEM_RS",
                        "alasan": "Pesawat CT-Scan RSUD Dr. Soedarso mengalami gangguan tabung pendingin, pemeriksaan tertunda hingga hari ke-2.",
                        "isJustified": False, "petugas": "Ns. Hendri, S.Kep", "tgl": "2026-11-01"
                    })
                elif cp_id == "CP-DMCKD-002":
                    executions["DM-06_d3"] = "TIDAK_TERLAKSANA"
                    variances.append({
                        "itemId": "DM-06", "hariKe": 3, "kategori": "SISTEM_RS",
                        "alasan": "Stok strip glukometer ruangan habis per jam 12.00, pengiriman logistik farmasi terlambat.",
                        "isJustified": False, "petugas": "Ns. Wahyu, S.Kep", "tgl": "2026-11-03"
                    })
                else:
                    first_crit = next(it for it in tmpl["items"] if it.get("isKritis"))
                    executions[f"{first_crit['id']}_d1"] = "TIDAK_TERLAKSANA"
                    variances.append({
                        "itemId": first_crit["id"], "hariKe": 1, "kategori": "SISTEM_RS",
                        "alasan": "Kendala teknis sistem operasional rumah sakit.",
                        "isJustified": False, "petugas": "Staf Bangsal", "tgl": "2026-11-01"
                    })

            else:
                # Kasus 10: Pasien Keluar dari Jalur CP (Drop-Out / Komplikasi / Rujukan)
                case_profile = "KELUAR_CP_DROP_OUT"
                status_enrollment = "KELUAR_CP"
                hari_terakhir = 3  # Keluar di hari ke-3
                real_los = 8  # Pemanjangan rawat karena komplikasi

                if cp_id == "CP-MAMMAE-001":
                    alasan_keluar = "Pasien mengalami komplikasi nekrosis flap mastektomi luas pada hari ke-3 pasca-bedah; memerlukan debridement ulang di OK dan antibiotik lini kedua."
                elif cp_id == "CP-DMCKD-002":
                    alasan_keluar = "Terjadi perburukan asidosis metabolik refrakter dan edema paru akut pada hari ke-3; pasien ditransfer ke ICU untuk intubasi dan HD cito."
                else:
                    alasan_keluar = "Terjadi komplikasi sekunder berat yang memerlukan alih rawat ke Intensive Care Unit (ICU)."

                for itm in tmpl["items"]:
                    for d in itm["jadwal"]:
                        if d <= hari_terakhir:
                            executions[f"{itm['id']}_d{d}"] = "TERLAKSANA"

                variances.append({
                    "itemId": None, "hariKe": 3, "kategori": "PASIEN_PENYAKIT",
                    "alasan": alasan_keluar,
                    "isJustified": True, "petugas": dpjp, "tgl": "2026-11-03"
                })

            enrollment_record = {
                "episodeId": ep_id,
                "mrNo": mr_no,
                "namaPasien": patient_name,
                "gender": gender,
                "usia": age,
                "ruangRawat": room,
                "dpjp": dpjp,
                "templateId": cp_id,
                "cpNama": cp_name,
                "caseProfile": case_profile,
                "statusEnrollment": status_enrollment,
                "alasanKeluar": alasan_keluar,
                "hariTerakhirCp": hari_terakhir,
                "targetLos": tmpl["losTarget"],
                "realLos": real_los,
                "tglMasuk": "2026-10-28",
                "tglKeluar": "2026-11-04" if status_enrollment == "SELESAI" else None,
                "executions": executions,
                "variances": variances
            }

            # Hitung skor mutu
            compliance_result = calculate_patient_compliance(enrollment_record, tmpl)
            enrollment_record["compliance"] = compliance_result

            dataset.append(enrollment_record)

    return dataset

# ==============================================================================
# 6. ANALITIK AGREGAT & MUTU CLINICAL PATHWAY RSUD DR. SOEDARSO
# ==============================================================================

def compute_cp_analytics(episodes, templates, screening=None):
    """
    Menghitung metrik agregat per CP dan keseluruhan:
    - Rata-rata kepatuhan mentah vs adjusted
    - Persentase kelolosan bundle kritis all-or-none
    - Pareto penyebab varian (4 kategori)
    - Rata-rata LOS riil vs Target LOS
    - Distribusi kepatuhan per profesi (DPJP, Perawat, Gizi, Farmasi, Fisioterapi)
    """
    total_episodes = len(episodes)
    if total_episodes == 0:
        return {}

    overall_raw_sum = sum(e["compliance"]["rawScore"] for e in episodes)
    overall_adj_sum = sum(e["compliance"]["adjScore"] for e in episodes)
    overall_bundle_passed = sum(1 for e in episodes if e["compliance"]["criticalBundlePassed"])
    
    # Pareto Varian
    variance_counts = {
        "PASIEN_PENYAKIT": 0,
        "PROFESIONAL_KLINISI": 0,
        "SISTEM_RS": 0,
        "KEBIJAKAN_ADMINISTRATIF": 0
    }
    all_variances_list = []

    for ep in episodes:
        for v in ep.get("variances", []):
            cat = v.get("kategori", "PASIEN_PENYAKIT")
            if cat in variance_counts:
                variance_counts[cat] += 1
            all_variances_list.append({
                "episodeId": ep["episodeId"],
                "mrNo": ep["mrNo"],
                "namaPasien": ep["namaPasien"],
                "cpNama": ep["cpNama"],
                "hariKe": v.get("hariKe"),
                "kategori": cat,
                "alasan": v.get("alasan"),
                "isJustified": v.get("isJustified", False),
                "petugas": v.get("petugas")
            })

    # Analitik per CP
    cp_summaries = []
    for tmpl in templates:
        cp_id = tmpl["id"]
        cp_eps = [e for e in episodes if e["templateId"] == cp_id]
        if not cp_eps:
            continue

        raw_avg = round(sum(e["compliance"]["rawScore"] for e in cp_eps) / len(cp_eps), 1)
        adj_avg = round(sum(e["compliance"]["adjScore"] for e in cp_eps) / len(cp_eps), 1)
        bundle_pct = round(sum(1 for e in cp_eps if e["compliance"]["criticalBundlePassed"]) / len(cp_eps) * 100, 1)
        avg_real_los = round(sum(e["realLos"] for e in cp_eps) / len(cp_eps), 1)

        mutu_cat = "HIJAU" if adj_avg >= 80.0 and bundle_pct >= 80.0 else ("KUNING" if adj_avg >= 70.0 else "MERAH")

        real_today_denom = 0
        real_hist_denom = 0
        if screening:
            real_today_denom = screening.get("today", {}).get("perCpDenominator", {}).get(cp_id, 0)
            real_hist_denom = screening.get("historical", {}).get("perCpDenominator", {}).get(cp_id, 0)

        cp_summaries.append({
            "templateId": cp_id,
            "nomorCp": tmpl["nomorCp"],
            "nama": tmpl["nama"],
            "ksm": tmpl["ksm"],
            "losTarget": tmpl["losTarget"],
            "avgRealLos": avg_real_los,
            "totalEpisodes": len(cp_eps),
            "realInpatientActive": real_today_denom,
            "realInpatientHistorical": real_hist_denom,
            "rawAvg": raw_avg,
            "adjAvg": adj_avg,
            "bundlePassedPct": bundle_pct,
            "mutuCategory": mutu_cat,
            "episodes": cp_eps
        })

    # PPA Aggregate
    ppa_totals = {}
    for ep in episodes:
        for ppa, stats in ep["compliance"]["ppaSummary"].items():
            if ppa not in ppa_totals:
                ppa_totals[ppa] = {"wajib": 0, "terlaksana": 0}
            ppa_totals[ppa]["wajib"] += stats["wajib"]
            ppa_totals[ppa]["terlaksana"] += stats["terlaksana"]

    ppa_radar = []
    for ppa, vals in ppa_totals.items():
        pct = round(vals["terlaksana"] / vals["wajib"] * 100, 1) if vals["wajib"] > 0 else 100.0
        ppa_radar.append({
            "ppa": ppa,
            "compliancePct": pct,
            "terlaksana": vals["terlaksana"],
            "wajib": vals["wajib"]
        })

    return {
        "summary": {
            "totalEpisodes": total_episodes,
            "overallRawScore": round(overall_raw_sum / total_episodes, 1),
            "overallAdjScore": round(overall_adj_sum / total_episodes, 1),
            "overallBundlePct": round(overall_bundle_passed / total_episodes * 100, 1),
            "totalVariances": len(all_variances_list)
        },
        "screening": screening or {},
        "variancePareto": variance_counts,
        "variances": all_variances_list,
        "cpSummaries": cp_summaries,
        "ppaRadar": ppa_radar,
        "domains": DOMAINS,
        "templates": templates
    }

def run_engine(recent_days=None, today_data=None):
    templates = load_master_templates()
    screening = screen_spreadsheet_patients(recent_days=recent_days, today_data=today_data, templates=templates)
    
    # Konversi pasien riil spreadsheet yang lolos inklusi denominator menjadi episode audit
    real_included_pts = screening.get("historical", {}).get("includedPatients", [])
    real_episodes = build_real_patient_episodes(real_included_pts, templates)
    
    # Dataset benchmark audit standar 5 CP
    synthetic_episodes = generate_synthetic_dataset()
    
    # Gabungkan: pasien riil di urutan teratas diikuti kasus benchmark
    all_episodes = real_episodes + synthetic_episodes
    
    analytics = compute_cp_analytics(all_episodes, templates, screening=screening)
    
    output_path = os.path.join(CURRENT_DIR, "clinical_pathways.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analytics, f, indent=2, ensure_ascii=False)
    
    print(f"[SUCCESS] Screening Denominator: {screening['today']['denominatorIncluded']}/{screening['today']['totalInpatients']} pasien aktif lolos kriteria CP (Cakupan Bangsal: {screening['today']['wardCoveragePct']}%).")
    print(f"[SUCCESS] {len(real_episodes)} episode riil terintegrasi ke denominator + {len(synthetic_episodes)} kasus benchmark -> {output_path}")
    return analytics

if __name__ == "__main__":
    run_engine()

