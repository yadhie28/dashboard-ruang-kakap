# Dashboard Ruang Kakap
**RSUD Dr. Soedarso Pontianak — Instalasi Rawat Inap (Tim I & Tim II • 41 Bed)**

Sistem Informasi Manajemen Sensus Pasien Rawat Inap, Denah Keterisian Bed Dinamis (41 Bed), Surveilans Triase Fisiologis **EWS / NEWS2**, Format Operan Jaga Shift **SBAR**, Interoperabilitas Standar **HL7 FHIR Release 4 (SatuSehat Ready)**, Indikator Efisiensi Mutu RS (BOR, AVLOS, TOI, BTO, NDR, GDR), serta Grafik Barber-Johnson Interaktif.

---

## 🚀 3 Cara Membuka Dashboard Sewaktu-Waktu

### 🖱️ 1. Klik Ganda (Double-Click) dari Desktop Mac
1. Temukan berkas **`Buka_Dashboard_Ruang_Kakap.command`** di **Desktop** Mac Anda.
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

## 🔄 Sumber Data & Jadwal Penarikan Otomatis

- **Google Spreadsheet Sumber**:  
  [https://docs.google.com/spreadsheets/d/1-5y9GuHIFbHE0OwS5_tfvdC9j9DMLO55i7uQyKpAKhY/edit?usp=sharing](https://docs.google.com/spreadsheets/d/1-5y9GuHIFbHE0OwS5_tfvdC9j9DMLO55i7uQyKpAKhY/edit?usp=sharing)
- **Jadwal Auto-Sync Setiap Pergantian Shift**:
  - **Shift Pagi**: Pukul **07.00 WIB** (Operan Jaga Malam ➔ Pagi)
  - **Shift Sore**: Pukul **14.00 WIB** (Operan Jaga Pagi ➔ Sore)
  - **Shift Malam**: Pukul **20.00 WIB** (Operan Jaga Sore ➔ Malam)
- **Tarik Data Manual**:
  Klik tombol **Sinkronisasi Data** di bilah atas aplikasi, atau jalankan:
  ```bash
  python3 run_build_data.py --download
  ```

---

*Dikembangkan untuk efisiensi operasional keperawatan, kendali mutu, dan keselamatan pasien (Patient Safety) Ruang Kakap RSUD Dr. Soedarso Pontianak.*

