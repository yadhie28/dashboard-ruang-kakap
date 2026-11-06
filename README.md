# Dashboard Ruang Kakap
**RSUD Dr. Soedarso Pontianak — Instalasi Rawat Inap (Tim I & Tim II • 41 Bed)**

Sistem Informasi Manajemen Sensus Pasien Rawat Inap, Denah Keterisian Bed Dinamis (41 Bed), Surveilans Triase Fisiologis **EWS / NEWS2**, Format Operan Jaga Shift **SBAR**, Interoperabilitas Standar **HL7 FHIR Release 4 (SatuSehat Ready)**, Indikator Efisiensi Mutu RS (BOR, AVLOS, TOI, BTO, NDR, GDR), Grafik Barber-Johnson Interaktif, serta **Modul Pengukur Kepatuhan Clinical Pathway Harian Pagi (PMKP / Kemenkes)**.

---

## 🌐 Akses Live Cloud (Kapan Saja & Di Mana Saja)
- **Live Dashboard (GitHub Pages):** [https://yadhie28.github.io/dashboard-ruang-kakap/](https://yadhie28.github.io/dashboard-ruang-kakap/)
- **Repositori Kode (GitHub):** [https://github.com/yadhie28/dashboard-ruang-kakap](https://github.com/yadhie28/dashboard-ruang-kakap)

---

## 🚀 3 Cara Membuka Dashboard Lokal Sewaktu-Waktu

### 🖱️ 1. Klik Ganda (Double-Click) dari Mac
1. Temukan berkas **`start_server.command`** di dalam folder ini (atau shortcut di Desktop Mac Anda).
2. Klik ganda berkas tersebut.
3. Server lokal Python akan otomatis aktif dan peramban (browser) langsung terbuka di `http://localhost:3000`.

---

### 💻 2. Jalankan Manual Lewat Terminal
```bash
cd /Users/rusmulyadiiskandar/.gemini/antigravity/scratch/dashboard-ruang-kakap
python3 server.py
```
Lalu buka di browser: `http://localhost:3000`

---

### 📁 3. Buka di Antigravity IDE / VS Code
Buka menu **File > Open Folder...** lalu arahkan ke:
```bash
/Users/rusmulyadiiskandar/.gemini/antigravity/scratch/dashboard-ruang-kakap
```
Atur folder ini sebagai **Active Workspace**.

---

## 📋 Fitur Utama & Modul Terpasang

1. **Sensus Dinamis & Keseimbangan Shift (Pagi, Sore, Malam):**
   - Formula keseimbangan bangsal: $\text{Free Bed} + \text{Px Sekarang} = \text{Px Awal} + \text{Px Baru} - \text{Px Meninggal} - \text{Px Pulang} - \text{Px Pindah}$.
   - Format WhatsApp terstandarisasi untuk kepala ruangan dan grup jaga.
2. **Denah Bed Interaktif (41 Bed) & SBAR Pasien:**
   - Visualisasi kamar Tim I (21 Bed) & Tim II (20 Bed) dengan status keterisian real-time, triase EWS/NEWS2, dan identitas pasien.
3. **Indikator Efisiensi Mutu Rawat Inap & Grafik Barber-Johnson:**
   - Perhitungan otomatis BOR, AVLOS, TOI, BTO, NDR, GDR secara bulanan & tahunan.
4. **Pengukur Kepatuhan Clinical Pathway Harian Pagi (PMKP / Akreditasi):**
   - Pengukuran sekali sehari pada pagi hari (07:00 WIB) menggunakan total data seluruh tab spreadsheet.
   - Rasio matematis: $\text{Kepatuhan CP} = \frac{\text{Nominator (Pasien Sesuai Seluruh Aspek)}}{\text{Denominator (Pasien Inklusi CP)}} \times 100\%$.
   - Evaluasi 6 aspek pelayanan: Kontrol LOS ($\le 7$ hari), Diagnostik/Penunjang, Terapi Farmakoterapi, Asuhan Medis & Keperawatan, Nutrisi/Diet Gizi, serta Edukasi & Discharge Planning.
   - Penapisan visual alur inklusi vs eksklusi terhadap 41 pasien unik bangsal.
5. **Analitik Agregat Bangsal (All Tabs):**
   - Top 10 DPJP / Dokter Spesialis (basis 41 pasien unik).
   - Top 10 Diagnosa Medis terstandarisasi klinis.
   - Distribusi Jaminan / Asuransi Pasien (BPJS Kelas 1/2/3).

---

## 🛏️ Struktur Kamar & Kapasitas Bed (41 Bed)

- **Tim I (21 Bed)**:
  - Kamar Kakap 1 (♂ Pria): Bed 1.1, 1.2, 1.3, 1.4
  - Kamar Kakap 2 (♀ Wanita): Bed 2.1, 2.2, 2.3, 2.4
  - Kamar Kakap 3 (♀ Wanita): Bed 3.1, 3.2, 3.3, 3.4
  - Kamar Kakap 4 (♀ Wanita): Bed 4.1, 4.2, 4.3, 4.4
  - Kamar Kakap 5 (♂ Pria): Bed 5.1, 5.2, 5.3, 5.4
  - Kamar Bed Isolasi (Khusus): Bed Isolasi (Bed 41)
- **Tim II (20 Bed)**:
  - Kamar Kakap 6 (♂ Pria): Bed 6.1, 6.2, 6.3, 6.4
  - Kamar Kakap 7 (♂ Pria): Bed 7.1, 7.2, 7.3, 7.4
  - Kamar Kakap 8 (♀ Wanita): Bed 8.1, 8.2, 8.3, 8.4
  - Kamar Kakap 9 (♂ Pria): Bed 9.1, 9.2, 9.3, 9.4
  - Kamar Kakap 10 (♀ Wanita): Bed 10.1, 10.2, 10.3, 10.4

---

## 🔄 Pembaruan Data dari Google Sheets

- **Tarik & Olah Data Manual:**
  ```bash
  python3 run_build_data.py --download
  ```
- **Kalkulasi Sensus Shift:**
  ```bash
  python3 shift_census_calculator.py
  ```
- **Audit Clinical Pathway:**
  ```bash
  python3 cp_mvp_engine.py
  ```

---

*Dikembangkan untuk efisiensi operasional keperawatan, kendali mutu, dan keselamatan pasien (Patient Safety) Ruang Kakap RSUD Dr. Soedarso Pontianak.*

