/**
 * CPPT Generator & Jembatan Pengisi Form SIMRS (Bookmarklet)
 * Dashboard Ruang Kakap — RSUD dr. Soedarso Pontianak
 *
 * PRIVASI & KEAMANAN:
 * - Seluruh draf CPPT, daftar pemeriksa, dan template pribadi hanya disimpan di browser lokal (localStorage).
 * - Tidak mengirim data pasien ke GitHub, server eksternal, atau layanan AI online.
 * - Tidak mengarang data klinis: data yang belum tersedia ditandai [ISI].
 * - Bookmarklet TIDAK PERNAH mengklik tombol Simpan SIMRS secara otomatis.
 */
(function (window) {
  'use strict';

  const STORAGE_EXAMINERS = 'kakap_cppt_examiners_v1';
  const STORAGE_TEMPLATES = 'kakap_cppt_templates_v1';
  const STORAGE_HISTORY = 'kakap_cppt_history_v1';
  const STORAGE_LAST_EXAMINER = 'kakap_cppt_last_examiner_v1';
  const PACKAGE_PREFIX = 'KAKAP_CPPT_V1::';

  // Template bawaan SOAPIER untuk Rawat Inap Penyakit Dalam (Ruang Kakap)
  // Semua template adalah kerangka draf yang WAJIB diperiksa perawat sebelum disimpan di SIMRS.
  const DEFAULT_TEMPLATES = [
    {
      id: 'tpl_d0003',
      sdkiCode: 'D.0003',
      title: 'Gangguan Pertukaran Gas (D.0003)',
      subjek: 'Pasien mengeluh sesak napas [ISI: memberat saat aktivitas / berkurang dengan posisi semi-Fowler], cepat lelah.',
      asesmen: 'Gangguan pertukaran gas (D.0003) b.d perubahan membran alveolus-kapiler / ketidakseimbangan ventilasi-perfusi.',
      planning: 'Setelah dilakukan asuhan keperawatan selama 1x24 jam diharapkan Pertukaran Gas (L.01003) meningkat dengan kriteria: dispnea menurun, bunyi napas tambahan menurun, SpO2 >= 95%, frekuensi napas 16-20 x/mnt.',
      implementation: '1. Memonitor frekuensi, irama, kedalaman, dan upaya napas.\n2. Memonitor saturasi oksigen (SpO2) dan tanda hipoksia.\n3. Mengatur posisi semi-Fowler / Fowler untuk memaksimalkan ventilasi.\n4. Memberikan terapi oksigen sesuai program medis: [ISI: nasal kanul / NRM ... L/mnt].\n5. Kolaborasi pemeriksaan AGD / foto toraks sesuai indikasi.',
      evaluation: 'S: Pasien mengatakan sesak [ISI: berkurang / masih terasa].\nO: [ISI: SpO2 ...%, RR ... x/mnt, terpasang O2 ... L/mnt].\nA: Masalah gangguan pertukaran gas [ISI: teratasi sebagian / belum teratasi].\nP: Lanjutkan pemantauan respirasi dan oksigenasi.',
      revised: 'Lanjutkan intervensi pemantauan respirasi; lapor DPJP segera bila SpO2 < 92% atau sesak memberat.'
    },
    {
      id: 'tpl_d0005',
      sdkiCode: 'D.0005',
      title: 'Pola Napas Tidak Efektif (D.0005)',
      subjek: 'Pasien mengeluh napas terasa pendek/sesak [ISI: sejak ... / saat berbaring telentang].',
      asesmen: 'Pola napas tidak efektif (D.0005) b.d hambatan upaya napas / posisi tubuh yang menghambat ekspansi paru.',
      planning: 'Setelah dilakukan asuhan keperawatan selama 1x24 jam diharapkan Pola Napas (L.01004) membaik: dispnea menurun, penggunaan otot bantu napas menurun, frekuensi napas membaik (16-20 x/mnt).',
      implementation: '1. Memonitor pola napas (frekuensi, kedalaman, usaha napas) dan bunyi napas tambahan.\n2. Memposisikan pasien semi-Fowler / Fowler.\n3. Mengajarkan teknik napas dalam dan batuk efektif bila mampu.\n4. Memberikan oksigenasi sesuai instruksi DPJP: [ISI].',
      evaluation: 'S: Keluhan sesak [ISI: berkurang / menetap].\nO: RR [ISI] x/mnt, SpO2 [ISI]%, penggunaan otot bantu napas [ISI: minimal / tidak ada].\nA: Masalah pola napas tidak efektif [ISI: teratasi sebagian / belum teratasi].\nP: Pertahankan posisi nyaman dan monitor pola napas berkala.',
      revised: 'Evaluasi ulang kebutuhan oksigen tiap shift; edukasi pasien membatasi aktivitas berat.'
    },
    {
      id: 'tpl_d0077',
      sdkiCode: 'D.0077',
      title: 'Nyeri Akut (D.0077)',
      subjek: 'Pasien mengeluh nyeri di area [ISI: lokasi nyeri], skala nyeri [ISI: 0-10], sifat [ISI: tertusuk/tumpul/hilang timbul], memberat saat [ISI].',
      asesmen: 'Nyeri akut (D.0077) b.d agen pencedera fisiologis / inflamasi / prosedur tindakan.',
      planning: 'Setelah dilakukan asuhan keperawatan selama 1x24 jam diharapkan Tingkat Nyeri (L.08066) menurun: keluhan nyeri menurun, meringis menurun, skala nyeri <= 3, TTV dalam batas stabil.',
      implementation: '1. Mengidentifikasi lokasi, karakteristik, durasi, frekuensi, kualitas, dan skala nyeri (PQRST).\n2. Mengajarkan teknik relaksasi napas dalam dan distraksi.\n3. Menciptakan lingkungan yang tenang dan posisi nyaman.\n4. Kolaborasi pemberian analgetik sesuai program DPJP: [ISI: nama obat & dosis].',
      evaluation: 'S: Pasien mengatakan nyeri [ISI: berkurang menjadi skala ... / masih nyeri].\nO: Ekspresi wajah [ISI: lebih rileks / tampak meringis], TTV stabil.\nA: Masalah nyeri akut [ISI: teratasi sebagian / belum teratasi].\nP: Lanjutkan manajemen nyeri farmakologis dan non-farmakologis.',
      revised: 'Pantau respons terhadap analgetik 30-60 menit pasca pemberian; lapor DPJP bila skala nyeri >= 7 menetap.'
    },
    {
      id: 'tpl_d0022',
      sdkiCode: 'D.0022',
      title: 'Hipervolemia / CKD / HD / Ascites (D.0022)',
      subjek: 'Pasien mengeluh [ISI: perut terasa penuh/bengkak pada kaki/sesak saat berbaring], BAK [ISI: sedikit/anuria/lancar].',
      asesmen: 'Hipervolemia (D.0022) b.d gangguan mekanisme regulasi / kelebihan asupan cairan / penurunan fungsi ginjal atau hati.',
      planning: 'Setelah dilakukan asuhan keperawatan selama 1x24 jam diharapkan Keseimbangan Cairan (L.03020) meningkat: edema/ascites berkurang, tidak ada sesak, balance cairan terkendali.',
      implementation: '1. Memonitor tanda hipervolemia (edema perifer, ascites, dispnea, JVP, ronki).\n2. Mencatat intake dan output cairan serta menghitung balance cairan/24 jam: [ISI: Intake ... mL / Output ... mL].\n3. Mengedukasi pembatasan asupan cairan dan garam sesuai diet.\n4. Kolaborasi pemberian diuretik / jadwal Hemodialisa (HD): [ISI].',
      evaluation: 'S: Keluhan sesak/bengkak [ISI: berkurang / menetap].\nO: Edema [ISI], balance cairan [ISI], TD [ISI] mmHg.\nA: Masalah hipervolemia [ISI: teratasi sebagian / belum teratasi].\nP: Lanjutkan pemantauan balance cairan ketat dan kepatuhan pembatasan minum.',
      revised: 'Pantau tanda edema paru akut dan hasil elektrolit/ureum-kreatinin terbaru.'
    },
    {
      id: 'tpl_d0027',
      sdkiCode: 'D.0027',
      title: 'Ketidakstabilan Kadar Glukosa Darah / DM (D.0027)',
      subjek: 'Pasien mengeluh [ISI: lemas/sering haus/sering BAK/pusing/keringat dingin], asupan makan [ISI: habis ... porsi].',
      asesmen: 'Ketidakstabilan kadar glukosa darah (D.0027) b.d resistensi insulin / gangguan toleransi glukosa darah.',
      planning: 'Setelah dilakukan asuhan keperawatan selama 1x24 jam diharapkan Kestabilan Kadar Glukosa Darah (L.03022) membaik: GDS dalam rentang target (100-180 mg/dL), keluhan lemas/pusing menurun.',
      implementation: '1. Memonitor kadar glukosa darah sewaktu (GDS): [ISI: ... mg/dL pukul ...].\n2. Memonitor tanda gejala hiperglikemia (poliuria, polidipsi, napas cepat) atau hipoglikemia (gemetar, keringat dingin, penurunan kesadaran).\n3. Memberikan terapi insulin / OAD sesuai program DPJP: [ISI].\n4. Mengedukasi kepatuhan diet DM dan jadwal makan.',
      evaluation: 'S: Keluhan lemas/pusing [ISI: berkurang / tidak ada].\nO: GDS terakhir [ISI] mg/dL, kesadaran [ISI].\nA: Masalah ketidakstabilan kadar glukosa darah [ISI: teratasi sebagian / belum teratasi].\nP: Lanjutkan pemantauan GDS berkala sesuai jadwal.',
      revised: 'Waspada hipoglikemia (GDS < 70 mg/dL) bila asupan makan menurun; lapor DPJP untuk penyesuaian dosis insulin.'
    },
    {
      id: 'tpl_d0009',
      sdkiCode: 'D.0009',
      title: 'Perfusi Perifer Tidak Efektif / Anemia (D.0009)',
      subjek: 'Pasien mengeluh badan terasa lemas, cepat lelah, dan pusing terutama saat berubah posisi.',
      asesmen: 'Perfusi perifer tidak efektif (D.0009) b.d penurunan konsentrasi hemoglobin / anemia.',
      planning: 'Setelah dilakukan asuhan keperawatan selama 1x24 jam diharapkan Perfusi Perifer (L.02011) meningkat: warna kulit/konjungtiva membaik, CRT < 3 detik, akral hangat, Hb meningkat menuju target.',
      implementation: '1. Memeriksa perfusi perifer (konjungtiva, akral, CRT, nadi perifer).\n2. Memonitor hasil laboratorium Hb/Ht terbaru: [ISI: Hb ... g/dL].\n3. Menganjurkan istirahat cukup dan mobilisasi bertahap.\n4. Kolaborasi pemberian transfusi darah PRC / terapi zat besi sesuai instruksi DPJP (pantau reaksi transfusi): [ISI].',
      evaluation: 'S: Pasien mengatakan lemas/pusing [ISI: mulai berkurang / masih terasa].\nO: Akral [ISI: hangat], CRT [ISI] detik, reaksi transfusi [ISI: tidak ada / belum transfusi].\nA: Masalah perfusi perifer tidak efektif [ISI: teratasi sebagian / belum teratasi].\nP: Lanjutkan pemantauan TTV, tanda perdarahan, dan cek Hb post-transfusi sesuai jadwal.',
      revised: 'Observasi ketat tanda reaksi transfusi (demam, menggigil, gatal, sesak) selama pemberian darah.'
    },
    {
      id: 'tpl_d0130',
      sdkiCode: 'D.0130',
      title: 'Hipertermia / Febris (D.0130)',
      subjek: 'Pasien mengeluh badan terasa panas/demam [ISI: sejak ...], disertai [ISI: menggigil / pusing / nyeri sendi].',
      asesmen: 'Hipertermia (D.0130) b.d proses penyakit (infeksi / inflamasi).',
      planning: 'Setelah dilakukan asuhan keperawatan selama 1x24 jam diharapkan Termoregulasi (L.14134) membaik: suhu tubuh menurun dalam rentang normal (36,5-37,5 C), menggigil menurun.',
      implementation: '1. Memonitor suhu tubuh dan TTV tiap 4 jam atau sesuai kondisi.\n2. Memberikan kompres hangat pada lipatan ketiak/lipat paha dan menganjurkan pakaian tipis menyerap keringat.\n3. Menganjurkan asupan cairan oral yang adekuat bila tidak ada kontraindikasi.\n4. Kolaborasi pemberian antipiretik / antibiotik sesuai instruksi DPJP: [ISI].',
      evaluation: 'S: Pasien mengatakan demam [ISI: mulai turun / masih terasa panas].\nO: Suhu terakhir [ISI] C, kulit [ISI: hangat / tidak menggigil].\nA: Masalah hipertermia [ISI: teratasi sebagian / belum teratasi].\nP: Lanjutkan pemantauan suhu berkala dan terapi antipiretik sesuai program.',
      revised: 'Pantau tanda syok sepsis/dehidrasi bila demam tinggi menetap > 38,5 C.'
    },
    {
      id: 'tpl_d0019',
      sdkiCode: 'D.0019',
      title: 'Defisit Nutrisi (D.0019)',
      subjek: 'Pasien mengeluh nafsu makan menurun, [ISI: mual / muntah / cepat kenyang], makan hanya habis [ISI: ... porsi].',
      asesmen: 'Defisit nutrisi (D.0019) b.d ketidakmampuan menelan/mencerna makanan / faktor psikologis / peningkatan kebutuhan metabolisme.',
      planning: 'Setelah dilakukan asuhan keperawatan selama 3x24 jam diharapkan Status Nutrisi (L.03030) membaik: porsi makan yang dihabiskan meningkat (>= 3/4 porsi), keluhan mual menurun.',
      implementation: '1. Memonitor asupan makanan harian dan keluhan mual/muntah.\n2. Menyajikan makanan dalam keadaan hangat, porsi kecil tetapi sering.\n3. Mengedukasi pasien dan keluarga tentang jenis diet RS yang sesuai: [ISI: diet lunak / tinggi protein / rendah garam].\n4. Kolaborasi dengan Ahli Gizi dan pemberian antiemetik sesuai instruksi DPJP: [ISI].',
      evaluation: 'S: Nafsu makan [ISI: mulai membaik / masih kurang], mual [ISI].\nO: Porsi makan habis [ISI], muntah [ISI: tidak ada / ... kali].\nA: Masalah defisit nutrisi [ISI: teratasi sebagian / belum teratasi].\nP: Lanjutkan pemantauan asupan nutrisi dan kolaborasi gizi.',
      revised: 'Evaluasi kebutuhan nutrisi enteral/parenteral bersama DPJP bila asupan oral < 50% selama 3 hari.'
    },
    {
      id: 'tpl_d0143',
      sdkiCode: 'D.0143',
      title: 'Risiko Jatuh (D.0143)',
      subjek: 'Pasien mengatakan [ISI: merasa pusing saat berdiri / tubuh terasa lemah / berjalan harus dibantu keluarga].',
      asesmen: 'Risiko jatuh (D.0143) d.d kelemahan fisik / anemia / usia lanjut / riwayat pusing atau penurunan kesadaran.',
      planning: 'Setelah dilakukan asuhan keperawatan selama masa rawat diharapkan Tingkat Jatuh (L.14138) menurun: tidak terjadi insiden jatuh, pengaman tempat tidur terpasang, pasien/keluarga memahami pencegahan jatuh.',
      implementation: '1. Mengidentifikasi faktor risiko jatuh (skor Morse/risiko jatuh) dan memasang penanda risiko jatuh bila indikasi.\n2. Memastikan pagar pengaman tempat tidur (side rail) terpasang dan roda tempat tidur terkunci.\n3. Menempatkan bel/kebutuhan pasien dalam jangkauan serta pencahayaan kamar cukup.\n4. Mengedukasi keluarga agar selalu mendampingi pasien saat ke kamar mandi atau berpindah posisi.',
      evaluation: 'S: Pasien dan keluarga memahami cara mencegah jatuh.\nO: Tidak ada kejadian jatuh, side rail terpasang, roda bed terkunci, lingkungan aman.\nA: Masalah risiko jatuh terkendali (tidak terjadi cedera).\nP: Pertahankan intervensi keselamatan pasien setiap shift.',
      revised: 'Kaji ulang risiko jatuh setiap pergantian shift atau bila ada perubahan kondisi/obat sedatif.'
    },
    {
      id: 'tpl_d0142',
      sdkiCode: 'D.0142',
      title: 'Risiko Infeksi (D.0142)',
      subjek: 'Pasien mengeluh [ISI: nyeri/panas di area luka atau infus / tidak ada keluhan tambahan].',
      asesmen: 'Risiko infeksi (D.0142) d.d efek prosedur invasif (infus/kateter/CDL/luka pasca tindakan) / penurunan imunitas.',
      planning: 'Setelah dilakukan asuhan keperawatan selama 3x24 jam diharapkan Tingkat Infeksi (L.14137) menurun: tidak ada tanda kemerahan, bengkak, pus, nyeri tekan, suhu dalam batas normal.',
      implementation: '1. Memonitor tanda infeksi lokal (rubor, kalor, dolor, tumor, eksudat) pada area luka/akses infus/CDL.\n2. Menerapkan cuci tangan 5 momen dan teknik aseptik pada setiap tindakan keperawatan.\n3. Merawat luka / mengganti balutan sesuai prosedur steril: [ISI].\n4. Kolaborasi pemberian antibiotik dan pemantauan leukosit/CRP sesuai program DPJP: [ISI].',
      evaluation: 'S: Pasien tidak mengeluh nyeri bertambah atau panas pada area luka/infus.\nO: Balutan [ISI: bersih dan kering], tanda plebitis/infeksi lokal [ISI: tidak ditemukan].\nA: Risiko infeksi terkendali.\nP: Lanjutkan pencegahan infeksi dan observasi area invasif tiap shift.',
      revised: 'Segera ganti akses IV bila tampak kemerahan/bengkak atau sudah > 72 jam.'
    }
  ];

  const cpptState = {
    selectedPatientKey: '',
    selectedShift: 'Pagi',
    selectedTemplateId: ''
  };

  function esc(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function toast(msg, type = 'info') {
    if (typeof window.showToast === 'function') {
      window.showToast(msg, type);
    } else {
      console.log(`[CPPT ${type}] ${msg}`);
    }
  }

  function getWibNow() {
    if (typeof window.getWIBTime === 'function') return window.getWIBTime();
    const now = new Date();
    return new Date(now.getTime() + (now.getTimezoneOffset() + 420) * 60000);
  }

  function pad2(n) { return String(n).padStart(2, '0'); }

  function detectShiftWib() {
    const h = getWibNow().getHours();
    if (h >= 7 && h < 14) return 'Pagi';
    if (h >= 14 && h < 20) return 'Sore';
    return 'Malam';
  }

  function formatSimrsDateTime(shiftName) {
    const w = getWibNow();
    const dd = pad2(w.getDate());
    const mm = pad2(w.getMonth() + 1);
    const yyyy = w.getFullYear();
    const hh = pad2(w.getHours());
    const mi = pad2(w.getMinutes());
    // Default jam aktual WIB agar akurat, atau bisa diubah manual
    return `${dd}/${mm}/${yyyy} ${hh}:${mi}`;
  }

  function getActivePatients() {
    const d = window.state && window.state.data;
    if (!d) return [];
    const curDate = window.state.currentDate || (d.metadata && d.metadata.latestDate);
    const day = (d.recentDays && d.recentDays[curDate]) || d.today;
    if (!day) return [];
    const raw = (Array.isArray(day.patients) && day.patients.length > 0)
      ? day.patients
      : [...(day.tim1 || day.eg2a || []), ...(day.tim2 || day.eg2b || [])];
    return raw.filter(p => p && !p.isEmpty);
  }

  function getPatientKey(pt) {
    return `${pt.bed || ''}__${pt.mrNo || ''}`;
  }

  function findSelectedPatient() {
    const pts = getActivePatients();
    return pts.find(p => getPatientKey(p) === cpptState.selectedPatientKey) || null;
  }

  // =========================================================================
  // PENYIMPANAN LOKAL BROWSER (PEMERIKSA, TEMPLATE, RIWAYAT DRAF CPPT)
  // =========================================================================
  function getKakapDefaultExaminers() {
    const set = new Set();
    const d = window.state && window.state.data;
    if (d && d.recentDays) {
      Object.values(d.recentDays).forEach(day => {
        const p = day && day.sensus && day.sensus.perawat;
        if (p) {
          ['pagi', 'sore', 'malam'].forEach(sh => {
            (p[sh] || []).forEach(n => {
              const clean = String(n || '').trim();
              if (clean.length > 2) set.add(clean);
            });
          });
        }
      });
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b, 'id'));
  }

  function loadExaminers() {
    let saved = null;
    try {
      const raw = localStorage.getItem(STORAGE_EXAMINERS);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) saved = parsed;
      }
    } catch (_) {}
    if (saved && saved.length > 0) return saved;
    const defaults = getKakapDefaultExaminers();
    return defaults.length > 0 ? defaults : ['Ns. Rusmulyadi, S.Kep., M.A.R.S'];
  }

  function saveExaminers(list) {
    try { localStorage.setItem(STORAGE_EXAMINERS, JSON.stringify(list)); } catch (_) {}
  }

  function loadTemplates() {
    try {
      const raw = localStorage.getItem(STORAGE_TEMPLATES);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (_) {}
    return DEFAULT_TEMPLATES.map(t => ({ ...t }));
  }

  function saveTemplates(list) {
    try { localStorage.setItem(STORAGE_TEMPLATES, JSON.stringify(list)); } catch (_) {}
  }

  function loadHistoryMap() {
    try {
      const raw = localStorage.getItem(STORAGE_HISTORY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object') return parsed;
      }
    } catch (_) {}
    return {};
  }

  function saveHistoryForPatient(ptKey, payload) {
    if (!ptKey) return;
    const map = loadHistoryMap();
    map[ptKey] = {
      ...payload,
      savedAt: new Date().toISOString()
    };
    try { localStorage.setItem(STORAGE_HISTORY, JSON.stringify(map)); } catch (_) {}
  }

  // =========================================================================
  // RENDER DAFTAR PASIEN, PEMERIKSA, DAN TEMPLATE
  // =========================================================================
  function renderPatientDropdown() {
    const sel = document.getElementById('cpptPatientSelect');
    const searchEl = document.getElementById('cpptPatientSearch');
    if (!sel) return;
    const q = (searchEl ? searchEl.value : '').toLowerCase().trim();
    const pts = getActivePatients();

    const filtered = pts.filter(p => {
      if (!q) return true;
      const bedStr = String(p.bed || '').toLowerCase();
      const nameStr = String(p.name || '').toLowerCase();
      const mrStr = String(p.mrNo || '').toLowerCase();
      const dxStr = String(p.diagnosis || '').toLowerCase();
      return bedStr.includes(q) || nameStr.includes(q) || mrStr.includes(q) || dxStr.includes(q);
    });

    const prevVal = cpptState.selectedPatientKey || sel.value;
    sel.innerHTML = `<option value="">-- Pilih Pasien Ruang Kakap (${filtered.length} tersedia) --</option>` +
      filtered.map(p => {
        const key = getPatientKey(p);
        const dispName = typeof window.maskPatientName === 'function' ? window.maskPatientName(p.name) : p.name;
        const dispMr = typeof window.maskMrNo === 'function' ? window.maskMrNo(p.mrNo) : p.mrNo;
        return `<option value="${esc(key)}" ${key === prevVal ? 'selected' : ''}>Bed ${esc(p.bed)} — ${esc(dispName)} (RM: ${esc(dispMr)})</option>`;
      }).join('');
  }

  function renderExaminerDropdown() {
    const sel = document.getElementById('cpptExaminerSelect');
    const listBox = document.getElementById('cpptExaminerManagerList');
    const examiners = loadExaminers();
    const lastUsed = localStorage.getItem(STORAGE_LAST_EXAMINER) || '';

    if (sel) {
      const cur = sel.value || lastUsed;
      sel.innerHTML = '<option value="">-- Pilih Nama Pemeriksa (Perawat) --</option>' +
        examiners.map(name => `<option value="${esc(name)}" ${name === cur ? 'selected' : ''}>${esc(name)}</option>`).join('');
    }
    if (listBox) {
      listBox.innerHTML = examiners.map((name, idx) => `
        <div class="cppt-mgr-row">
          <span>${esc(name)}</span>
          <button type="button" class="lb-btn-mini lb-btn-del" onclick="KakapCPPT.removeExaminer(${idx})">Hapus</button>
        </div>
      `).join('');
    }
  }

  function addExaminer() {
    const inp = document.getElementById('cpptNewExaminerInput');
    const name = (inp ? inp.value : '').trim();
    if (!name) {
      toast('Ketik nama pemeriksa terlebih dahulu.', 'warning');
      return;
    }
    const list = loadExaminers();
    if (list.some(x => x.toLowerCase() === name.toLowerCase())) {
      toast('Nama pemeriksa sudah ada di daftar.', 'info');
      return;
    }
    list.push(name);
    list.sort((a, b) => a.localeCompare(b, 'id'));
    saveExaminers(list);
    localStorage.setItem(STORAGE_LAST_EXAMINER, name);
    if (inp) inp.value = '';
    renderExaminerDropdown();
    const sel = document.getElementById('cpptExaminerSelect');
    if (sel) sel.value = name;
    toast(`Nama pemeriksa "${name}" ditambahkan.`, 'success');
  }

  function removeExaminer(idx) {
    const list = loadExaminers();
    if (idx < 0 || idx >= list.length) return;
    const removed = list.splice(idx, 1)[0];
    saveExaminers(list);
    renderExaminerDropdown();
    toast(`"${removed}" dihapus dari daftar pemeriksa.`, 'info');
  }

  function onExaminerChange() {
    const sel = document.getElementById('cpptExaminerSelect');
    if (sel && sel.value) {
      localStorage.setItem(STORAGE_LAST_EXAMINER, sel.value);
    }
  }

  function renderTemplateDropdown() {
    const sel = document.getElementById('cpptTemplateSelect');
    const listBox = document.getElementById('cpptTemplateManagerList');
    const templates = loadTemplates();

    if (sel) {
      const cur = cpptState.selectedTemplateId || sel.value;
      sel.innerHTML = '<option value="">-- Pilih Template Diagnosa Keperawatan (SOAPIER) --</option>' +
        templates.map(t => `<option value="${esc(t.id)}" ${t.id === cur ? 'selected' : ''}>${esc(t.title)}</option>`).join('');
    }
    if (listBox) {
      listBox.innerHTML = templates.map(t => `
        <div class="cppt-mgr-row">
          <div>
            <strong>${esc(t.title)}</strong>
            <div style="font-size:0.75rem;color:var(--text-muted);">${esc((t.asesmen || '').slice(0, 90))}...</div>
          </div>
          <div style="display:flex;gap:6px;flex-shrink:0;">
            <button type="button" class="lb-btn-mini" onclick="KakapCPPT.editTemplate('${esc(t.id)}')">Edit</button>
            <button type="button" class="lb-btn-mini lb-btn-del" onclick="KakapCPPT.deleteTemplate('${esc(t.id)}')">Hapus</button>
          </div>
        </div>
      `).join('');
    }
  }

  // =========================================================================
  // PERANGKAI KALIMAT OBJEK DARI TANDA VITAL + GENERATOR SOAPIER
  // =========================================================================
  function buildObjekText(pt) {
    const td = (document.getElementById('cpptVitalTd')?.value || '').trim();
    const nadi = (document.getElementById('cpptVitalHr')?.value || '').trim();
    const rr = (document.getElementById('cpptVitalRr')?.value || '').trim();
    const suhu = (document.getElementById('cpptVitalTemp')?.value || '').trim();
    const spo2 = (document.getElementById('cpptVitalSpo2')?.value || '').trim();
    const gcs = (document.getElementById('cpptVitalGcs')?.value || '').trim();

    const vitals = [];
    vitals.push(`TD: ${td ? td + ' mmHg' : '[ISI] mmHg'}`);
    vitals.push(`Nadi: ${nadi ? nadi + ' x/mnt' : '[ISI] x/mnt'}`);
    vitals.push(`Napas (RR): ${rr ? rr + ' x/mnt' : '[ISI] x/mnt'}`);
    vitals.push(`Suhu: ${suhu ? suhu + ' °C' : '[ISI] °C'}`);
    vitals.push(`SpO2: ${spo2 ? spo2 + '%' : '[ISI]%'}`);
    vitals.push(`Kesadaran/GCS: ${gcs || '[ISI: Compos Mentis / E4V5M6]'}`);

    const lines = [];
    lines.push(`Keadaan umum: [ISI: tampak sakit sedang / lemah / tenang].`);
    lines.push(`Tanda vital: ${vitals.join(', ')}.`);
    if (pt) {
      if (pt.diagnosis && pt.diagnosis !== '-') {
        lines.push(`Diagnosa medis tercatat: ${pt.diagnosis}.`);
      }
      if (Array.isArray(pt.tags) && pt.tags.length > 0) {
        lines.push(`Program klinis aktif: ${pt.tags.map(t => t.label).join(', ')}.`);
      }
      const notes = pt.notes || {};
      const activeShiftKey = (cpptState.selectedShift || 'Pagi').toLowerCase();
      const shiftNote = (notes[activeShiftKey] || notes.pagi || notes.sore || notes.malam || '').trim();
      if (shiftNote) {
        lines.push(`Catatan operan ruangan: ${shiftNote}`);
      }
    }
    return lines.join('\n');
  }

  function updateObjekFromVitals() {
    const pt = findSelectedPatient();
    const objEl = document.getElementById('cpptFieldObjek');
    if (objEl) {
      objEl.value = buildObjekText(pt);
    }
  }

  function onPatientChange() {
    const sel = document.getElementById('cpptPatientSelect');
    cpptState.selectedPatientKey = sel ? sel.value : '';
    const pt = findSelectedPatient();
    const infoBox = document.getElementById('cpptSelectedPatientInfo');
    const dupBtn = document.getElementById('btnCpptDuplicatePrev');

    if (!pt) {
      if (infoBox) infoBox.style.display = 'none';
      if (dupBtn) dupBtn.disabled = true;
      return;
    }

    const dispName = typeof window.maskPatientName === 'function' ? window.maskPatientName(pt.name) : pt.name;
    const dispMr = typeof window.maskMrNo === 'function' ? window.maskMrNo(pt.mrNo) : pt.mrNo;
    const sdkiList = (window.KakapELogbook && typeof window.KakapELogbook.suggestSdkiForPatient === 'function')
      ? window.KakapELogbook.suggestSdkiForPatient(pt, 3)
      : [];

    if (infoBox) {
      infoBox.style.display = 'block';
      infoBox.innerHTML = `
        <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:6px;">
          <div>
            <strong>Bed ${esc(pt.bed)}</strong> &bull; ${esc(dispName)} <span class="lb-muted">(RM: ${esc(dispMr)})</span>
          </div>
          <div><span class="lb-badge lb-badge-info">DPJP: ${esc(pt.doctorPrimary || '-')}</span></div>
        </div>
        <div style="font-size:0.84rem;margin-bottom:6px;"><strong>Diagnosa Medis (Spreadsheet):</strong> ${esc(pt.diagnosis || '-')}</div>
        ${sdkiList.length > 0 ? `<div style="font-size:0.8rem;"><strong>Saran SDKI Terdeteksi:</strong> ${sdkiList.map(s => `<span class="bed-sdki-code">${esc(s.code)}</span> ${esc(s.name)}`).join(' &bull; ')}</div>` : ''}
      `;
    }

    // Cek apakah ada CPPT sebelumnya untuk pasien ini di localStorage
    const hist = loadHistoryMap();
    if (dupBtn) {
      dupBtn.disabled = !hist[cpptState.selectedPatientKey];
    }

    // Pilih template otomatis yang paling cocok dengan saran SDKI pasien
    const templates = loadTemplates();
    let matchedTpl = null;
    if (sdkiList.length > 0) {
      for (const s of sdkiList) {
        matchedTpl = templates.find(t => t.sdkiCode === s.code);
        if (matchedTpl) break;
      }
    }
    if (matchedTpl) {
      cpptState.selectedTemplateId = matchedTpl.id;
      const tplSel = document.getElementById('cpptTemplateSelect');
      if (tplSel) tplSel.value = matchedTpl.id;
      applyTemplateToForm(matchedTpl, pt);
    } else {
      updateObjekFromVitals();
    }
  }

  function onShiftChange() {
    const sel = document.getElementById('cpptShiftSelect');
    cpptState.selectedShift = sel ? sel.value : detectShiftWib();
    const dtEl = document.getElementById('cpptDateTimeInput');
    if (dtEl) {
      const w = getWibNow();
      const dd = pad2(w.getDate());
      const mm = pad2(w.getMonth() + 1);
      const yyyy = w.getFullYear();
      const defaultTime = cpptState.selectedShift === 'Pagi' ? '08:00'
        : cpptState.selectedShift === 'Sore' ? '15:00' : '21:00';
      dtEl.value = `${dd}/${mm}/${yyyy} ${defaultTime}`;
    }
  }

  function applySelectedTemplate() {
    const sel = document.getElementById('cpptTemplateSelect');
    const id = sel ? sel.value : '';
    cpptState.selectedTemplateId = id;
    const tpl = loadTemplates().find(t => t.id === id);
    if (!tpl) return;
    applyTemplateToForm(tpl, findSelectedPatient());
    toast(`Template "${tpl.title}" diterapkan ke formulir SOAPIER.`, 'info');
  }

  function applyTemplateToForm(tpl, pt) {
    const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ''; };
    setVal('cpptFieldSubjek', tpl.subjek);
    setVal('cpptFieldObjek', buildObjekText(pt));
    setVal('cpptFieldAsesmen', tpl.asesmen);
    setVal('cpptFieldPlanning', tpl.planning);
    setVal('cpptFieldImplementation', tpl.implementation);
    setVal('cpptFieldEvaluation', tpl.evaluation);
    setVal('cpptFieldRevised', tpl.revised);
  }

  function duplicateFromPrevious() {
    if (!cpptState.selectedPatientKey) {
      toast('Pilih pasien terlebih dahulu.', 'warning');
      return;
    }
    const hist = loadHistoryMap();
    const prev = hist[cpptState.selectedPatientKey];
    if (!prev) {
      toast('Belum ada draf CPPT sebelumnya untuk pasien ini di browser ini.', 'info');
      return;
    }
    const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ''; };
    setVal('cpptFieldSubjek', prev.subjek);
    setVal('cpptFieldObjek', prev.objek);
    setVal('cpptFieldAsesmen', prev.asesmen);
    setVal('cpptFieldPlanning', prev.planning);
    setVal('cpptFieldImplementation', prev.implementation);
    setVal('cpptFieldEvaluation', prev.evaluation);
    setVal('cpptFieldRevised', prev.revised);
    // Tanggal & jam diperbarui ke shift sekarang
    onShiftChange();
    toast('Draf CPPT sebelumnya berhasil digandakan. Silakan perbarui bagian yang berubah.', 'success');
  }

  function collectFormPayload() {
    const getVal = (id) => (document.getElementById(id)?.value || '').trim();
    return {
      v: 1,
      tanggal: getVal('cpptDateTimeInput'),
      pemeriksa: getVal('cpptExaminerSelect'),
      subjek: getVal('cpptFieldSubjek'),
      objek: getVal('cpptFieldObjek'),
      asesmen: getVal('cpptFieldAsesmen'),
      planning: getVal('cpptFieldPlanning'),
      implementation: getVal('cpptFieldImplementation'),
      evaluation: getVal('cpptFieldEvaluation'),
      revised: getVal('cpptFieldRevised')
    };
  }

  async function copyTextToClipboard(text) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (_) {}
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return ok;
    } catch (_) {
      return false;
    }
  }

  async function copySingleField(fieldId, label) {
    const el = document.getElementById(fieldId);
    if (!el) return;
    const ok = await copyTextToClipboard(el.value || '');
    toast(ok ? `Isian ${label} berhasil disalin.` : `Gagal menyalin otomatis. Silakan blok teks ${label} lalu salin manual.`, ok ? 'success' : 'warning');
  }

  async function copyAllPackage() {
    const payload = collectFormPayload();
    // Simpan ke riwayat lokal per pasien untuk fitur "Gandakan dari CPPT sebelumnya"
    if (cpptState.selectedPatientKey) {
      saveHistoryForPatient(cpptState.selectedPatientKey, payload);
      const dupBtn = document.getElementById('btnCpptDuplicatePrev');
      if (dupBtn) dupBtn.disabled = false;
    }

    const encoded = PACKAGE_PREFIX + JSON.stringify(payload);
    const previewBox = document.getElementById('cpptPackageOutput');
    if (previewBox) previewBox.value = encoded;

    const ok = await copyTextToClipboard(encoded);
    if (ok) {
      toast('Paket CPPT berhasil disalin! Sekarang buka form CPPT SIMRS lalu klik Tombol Pintar.', 'success');
    } else {
      toast('Paket CPPT sudah disiapkan di kotak bawah. Silakan blok & salin manual (Ctrl+C).', 'warning');
    }
    return encoded;
  }

  // =========================================================================
  // KELOLA TEMPLATE PRIBADI (TAMBAH / EDIT / HAPUS)
  // =========================================================================
  function openTemplateEditor(id) {
    const modal = document.getElementById('cpptTemplateModal');
    if (!modal) return;
    const tpl = id ? loadTemplates().find(t => t.id === id) : null;
    document.getElementById('cpptTplEditId').value = tpl ? tpl.id : '';
    document.getElementById('cpptTplTitle').value = tpl ? tpl.title : '';
    document.getElementById('cpptTplSdki').value = tpl ? (tpl.sdkiCode || '') : '';
    document.getElementById('cpptTplSubjek').value = tpl ? tpl.subjek : '';
    document.getElementById('cpptTplAsesmen').value = tpl ? tpl.asesmen : '';
    document.getElementById('cpptTplPlanning').value = tpl ? tpl.planning : '';
    document.getElementById('cpptTplImpl').value = tpl ? tpl.implementation : '';
    document.getElementById('cpptTplEval').value = tpl ? tpl.evaluation : '';
    document.getElementById('cpptTplRev').value = tpl ? tpl.revised : '';
    modal.style.display = 'flex';
  }

  function closeTemplateEditor() {
    const modal = document.getElementById('cpptTemplateModal');
    if (modal) modal.style.display = 'none';
  }

  function saveTemplateFromModal() {
    const id = (document.getElementById('cpptTplEditId').value || '').trim();
    const title = (document.getElementById('cpptTplTitle').value || '').trim();
    if (!title) {
      toast('Nama template wajib diisi.', 'warning');
      return;
    }
    const obj = {
      id: id || ('tpl_custom_' + Date.now()),
      sdkiCode: (document.getElementById('cpptTplSdki').value || '').trim().toUpperCase(),
      title,
      subjek: document.getElementById('cpptTplSubjek').value || '',
      asesmen: document.getElementById('cpptTplAsesmen').value || '',
      planning: document.getElementById('cpptTplPlanning').value || '',
      implementation: document.getElementById('cpptTplImpl').value || '',
      evaluation: document.getElementById('cpptTplEval').value || '',
      revised: document.getElementById('cpptTplRev').value || ''
    };
    const list = loadTemplates();
    const idx = list.findIndex(t => t.id === obj.id);
    if (idx >= 0) list[idx] = obj;
    else list.unshift(obj);
    saveTemplates(list);
    cpptState.selectedTemplateId = obj.id;
    renderTemplateDropdown();
    closeTemplateEditor();
    toast(`Template "${title}" berhasil disimpan di browser Anda.`, 'success');
  }

  function editTemplate(id) { openTemplateEditor(id); }

  function deleteTemplate(id) {
    if (!confirm('Hapus template ini dari perpustakaan Anda?')) return;
    const list = loadTemplates().filter(t => t.id !== id);
    saveTemplates(list);
    renderTemplateDropdown();
    toast('Template dihapus.', 'info');
  }

  function toggleSection(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
  }

  // =========================================================================
  // TOMBOL PINTAR (BOOKMARKLET) PENGISI FORM CPPT SIMRS
  // Membaca isian secara fleksibel lewat label/atribut + Mode "Periksa Form"
  // TIDAK PERNAH mengklik tombol Simpan secara otomatis!
  // =========================================================================
  function getBookmarkletSource() {
    // Fungsi mandiri yang berjalan di halaman form CPPT SIMRS (http maupun https)
    return `(function(){
if(document.getElementById('kakapSimrsBox')){document.getElementById('kakapSimrsBox').remove();return;}
function norm(s){return String(s||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();}
function getLabelText(el){
  var parts=[];
  if(el.id){var lb=document.querySelector('label[for="'+CSS.escape(el.id)+'"]');if(lb)parts.push(lb.innerText);}
  var p=el.closest('label');if(p)parts.push(p.innerText);
  var fg=el.closest('.form-group,tr,.row,div');
  if(fg){var lbs=fg.querySelectorAll('label,th,.control-label');for(var i=0;i<lbs.length&&i<2;i++)parts.push(lbs[i].innerText);}
  if(el.placeholder)parts.push(el.placeholder);
  if(el.name)parts.push(el.name);
  if(el.id)parts.push(el.id);
  if(el.getAttribute('aria-label'))parts.push(el.getAttribute('aria-label'));
  return parts.join(' | ');
}
function fireEvents(el){
  ['input','change','blur'].forEach(function(ev){
    try{el.dispatchEvent(new Event(ev,{bubbles:true}));}catch(e){}
  });
  try{if(window.jQuery){window.jQuery(el).trigger('change').trigger('input');}}catch(e){}
}
function findField(tagSel,keywords){
  var els=Array.from(document.querySelectorAll(tagSel)).filter(function(el){
    if(el.closest('#kakapSimrsBox'))return false;
    if(el.type==='hidden'&&!(el.classList&&el.classList.contains('select2-hidden-accessible')))return false;
    return true;
  });
  for(var k=0;k<keywords.length;k++){
    var kw=keywords[k];
    for(var i=0;i<els.length;i++){
      var info=norm(getLabelText(els[i]));
      if(info.indexOf(kw)!==-1)return els[i];
    }
  }
  return null;
}
function setSelectByName(sel,targetName){
  if(!sel||!targetName)return {ok:false,msg:'Nama pemeriksa kosong atau dropdown tidak ditemukan'};
  var cleanTarget=norm(targetName.replace(/\\b(ns|s\\.?kep|m\\.?a\\.?r\\.?s|a\\.?md\\.?kep|dr|sp\\.?\\w+)\\b/gi,''));
  var rawTarget=norm(targetName);
  var best=null,bestScore=0;
  for(var i=0;i<sel.options.length;i++){
    var opt=sel.options[i];
    if(!opt.value)continue;
    var txt=norm(opt.text);
    var txtClean=norm(opt.text.replace(/\\b(ns|s\\.?kep|m\\.?a\\.?r\\.?s|a\\.?md\\.?kep|dr|sp\\.?\\w+)\\b/gi,''));
    if(txt===rawTarget||txtClean===cleanTarget){best=opt;bestScore=100;break;}
    if(cleanTarget&&txtClean&&(txtClean.indexOf(cleanTarget)!==-1||cleanTarget.indexOf(txtClean)!==-1)){
      if(80>bestScore){best=opt;bestScore=80;}
    }else{
      var words=cleanTarget.split(' ').filter(function(w){return w.length>=3;});
      var hit=0;words.forEach(function(w){if(txtClean.indexOf(w)!==-1)hit++;});
      var sc=words.length?Math.round((hit/words.length)*70):0;
      if(sc>=50&&sc>bestScore){best=opt;bestScore=sc;}
    }
  }
  if(!best)return {ok:false,msg:'Nama "'+targetName+'" tidak cocok dengan daftar dropdown SIMRS (tidak dipilih asal)'};
  sel.value=best.value;
  fireEvents(sel);
  try{if(window.jQuery&&window.jQuery(sel).data('select2')){window.jQuery(sel).val(best.value).trigger('change');}}catch(e){}
  return {ok:true,matched:best.text};
}
function fillAll(rawText){
  var s=String(rawText||'').trim();
  if(s.indexOf('KAKAP_CPPT_V1::')===0)s=s.slice('KAKAP_CPPT_V1::'.length);
  var data;
  try{data=JSON.parse(s);}catch(e){return {error:'Format paket tidak valid. Pastikan Anda menekan "Salin Semua" di CPPT Generator lalu tempel di sini.'};}
  var okList=[],failList=[];
  var elTgl=findField('input',['tanggal cppt','tgl cppt','tanggal','datetime']);
  if(elTgl&&data.tanggal){
    var val=data.tanggal;
    if(elTgl.type==='datetime-local'){
      var m=val.match(/(\\d{2})\\/(\\d{2})\\/(\\d{4})\\s+(\\d{2}):(\\d{2})/);
      if(m)val=m[3]+'-'+m[2]+'-'+m[1]+'T'+m[4]+':'+m[5];
    }
    elTgl.value=val;fireEvents(elTgl);okList.push('Tanggal CPPT');
  }else{failList.push('Tanggal CPPT');}
  var elPem=findField('select',['pemeriksa','paramedis','dokter','petugas','nama pemeriksa']);
  if(elPem&&data.pemeriksa){
    var r=setSelectByName(elPem,data.pemeriksa);
    if(r.ok)okList.push('Pemeriksa ('+r.matched+')');
    else failList.push('Pemeriksa: '+r.msg);
  }else{failList.push('Pemeriksa (dropdown tidak ditemukan / nama kosong)');}
  var map=[
    ['SUBJEK',data.subjek,['subjek','subyektif','subjective','cppt subjek','soap s']],
    ['OBJEK',data.objek,['objek','obyektif','objective','cppt objek','soap o']],
    ['ASESMEN',data.asesmen,['asesmen','assesmen','assessment','analisa','cppt asesmen']],
    ['PLANNING',data.planning,['planning','perencanaan','rencana','cppt planning']],
    ['IMPLEMENTATION',data.implementation,['implementation','implementasi','tindakan','pelaksanaan']],
    ['EVALUATION',data.evaluation,['evaluation','evaluasi']],
    ['REVISED',data.revised,['revised','revisi','tindak lanjut']]
  ];
  map.forEach(function(item){
    var el=findField('textarea,input[type="text"]',item[2]);
    if(el){el.value=item[1]||'';fireEvents(el);okList.push(item[0]);}
    else{failList.push(item[0]);}
  });
  return {okCount:okList.length,total:9,okList:okList,failList:failList};
}
function inspectForm(){
  var els=Array.from(document.querySelectorAll('input,select,textarea')).filter(function(el){
    if(el.closest('#kakapSimrsBox'))return false;
    if(el.type==='hidden'&&!(el.classList&&el.classList.contains('select2-hidden-accessible')))return false;
    return true;
  });
  return els.map(function(el,idx){
    var s2=(el.classList&&el.classList.contains('select2-hidden-accessible'))?' [Select2]':'';
    return (idx+1)+'. <'+el.tagName.toLowerCase()+(el.type?' type='+el.type:'')+'>'+s2+' name="'+(el.name||'-')+'" id="'+(el.id||'-')+'" | label: '+getLabelText(el).slice(0,80);
  }).join('\\n')||'Tidak ada kolom formulir terdeteksi di halaman ini.';
}
var box=document.createElement('div');
box.id='kakapSimrsBox';
box.style.cssText='position:fixed;top:14px;right:14px;z-index:999999;width:360px;max-width:94vw;background:#0f172a;color:#f8fafc;border:2px solid #0ea5e9;border-radius:12px;padding:14px;font-family:Arial,sans-serif;font-size:13px;box-shadow:0 12px 32px rgba(0,0,0,.45);';
box.innerHTML='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
+'<strong style="font-size:14px;color:#38bdf8;">⚡ Tombol Pintar CPPT Kakap</strong>'
+'<button id="kClose" style="background:#334155;color:#fff;border:none;border-radius:6px;padding:3px 9px;cursor:pointer;font-weight:bold;">✕</button></div>'
+'<div style="font-size:12px;color:#cbd5e1;margin-bottom:6px;">Tempel (Ctrl+V) paket hasil <b>Salin Semua</b> dari CPPT Generator di kotak bawah:</div>'
+'<textarea id="kInput" rows="4" placeholder="Tempel paket KAKAP_CPPT_V1::... di sini" style="width:100%;box-sizing:border-box;padding:8px;border-radius:8px;border:1px solid #475569;background:#1e293b;color:#fff;font-size:12px;"></textarea>'
+'<div style="display:flex;gap:8px;margin-top:8px;">'
+'<button id="kFill" style="flex:1;background:#0284c7;color:#fff;border:none;border-radius:8px;padding:9px;font-weight:bold;cursor:pointer;">Isi Form SIMRS</button>'
+'<button id="kInspect" style="background:#334155;color:#e2e8f0;border:1px solid #475569;border-radius:8px;padding:9px 10px;font-weight:bold;cursor:pointer;">Periksa Form</button></div>'
+'<div id="kStatus" style="margin-top:8px;font-size:12px;line-height:1.45;max-height:180px;overflow:auto;white-space:pre-wrap;color:#e2e8f0;"></div>'
+'<div style="margin-top:6px;font-size:11px;color:#fbbf24;">⚠️ Tombol Simpan SIMRS tidak diklik otomatis. Periksa semua isian lalu klik Simpan sendiri.</div>';
document.body.appendChild(box);
document.getElementById('kClose').onclick=function(){box.remove();};
document.getElementById('kFill').onclick=function(){
  var res=fillAll(document.getElementById('kInput').value);
  var st=document.getElementById('kStatus');
  if(res.error){st.style.color='#fca5a5';st.textContent=res.error;return;}
  st.style.color=res.failList.length?'#fde68a':'#86efac';
  st.textContent='Berhasil mengisi '+res.okCount+' dari '+res.total+' isian.\\n'
    +(res.okList.length?'✓ Terisi: '+res.okList.join(', ')+'\\n':'')
    +(res.failList.length?'✕ Gagal / perlu diisi manual:\\n- '+res.failList.join('\\n- '):'Semua 9 isian berhasil terisi! Silakan periksa lalu klik Simpan.');
};
document.getElementById('kInspect').onclick=function(){
  var st=document.getElementById('kStatus');
  st.style.color='#93c5fd';
  st.textContent='Daftar isian terdeteksi di halaman ini:\\n'+inspectForm();
};
document.getElementById('kInput').focus();
})();`;
  }

  function getBookmarkletHref() {
    const code = getBookmarkletSource().replace(/\n+/g, ' ').replace(/\s{2,}/g, ' ').trim();
    return 'javascript:' + encodeURIComponent(code);
  }

  function getTampermonkeyScript() {
    return `// ==UserScript==
// @name         Tombol Pintar CPPT Ruang Kakap (SIMRS Soedarso)
// @namespace    https://yadhie28.github.io/dashboard-ruang-kakap/
// @version      1.0
// @description  Menampilkan tombol pengisi otomatis CPPT SOAPIER di halaman form CPPT SIMRS RSUD dr. Soedarso (tidak mengklik Simpan otomatis).
// @match        http://192.168.234.100/rawatinap/Cppt/*
// @grant        none
// ==/UserScript==

(function() {
  'use strict';
  const btn = document.createElement('button');
  btn.textContent = '⚡ Isi CPPT Kakap';
  btn.type = 'button';
  btn.style.cssText = 'position:fixed;bottom:18px;right:18px;z-index:999998;background:#0284c7;color:#fff;border:none;border-radius:999px;padding:10px 16px;font-weight:bold;font-size:13px;cursor:pointer;box-shadow:0 6px 18px rgba(0,0,0,.3);';
  btn.onclick = function() {
    ${getBookmarkletSource()}
  };
  document.body.appendChild(btn);
})();`;
  }

  function initBookmarkletUi() {
    const link = document.getElementById('cpptBookmarkletLink');
    if (link) {
      link.setAttribute('href', getBookmarkletHref());
    }
    const codeBox = document.getElementById('cpptBookmarkletCodeBox');
    if (codeBox) {
      codeBox.value = getBookmarkletHref();
    }
    const tmBox = document.getElementById('cpptTampermonkeyBox');
    if (tmBox) {
      tmBox.value = getTampermonkeyScript();
    }
  }

  async function copyBookmarkletCode() {
    const ok = await copyTextToClipboard(getBookmarkletHref());
    toast(ok ? 'Kode Tombol Pintar berhasil disalin! Tempel di kolom URL saat membuat bookmark baru di Chrome.' : 'Gagal menyalin otomatis. Salin dari kotak kode di bawah.', ok ? 'success' : 'warning');
  }

  async function copyTampermonkeyCode() {
    const ok = await copyTextToClipboard(getTampermonkeyScript());
    toast(ok ? 'Skrip Tampermonkey cadangan berhasil disalin.' : 'Silakan salin manual dari kotak skrip.', ok ? 'success' : 'warning');
  }

  // =========================================================================
  // INISIALISASI
  // =========================================================================
  function init() {
    cpptState.selectedShift = detectShiftWib();
    const shiftSel = document.getElementById('cpptShiftSelect');
    if (shiftSel) shiftSel.value = cpptState.selectedShift;
    const dtEl = document.getElementById('cpptDateTimeInput');
    if (dtEl && !dtEl.value) dtEl.value = formatSimrsDateTime(cpptState.selectedShift);

    renderPatientDropdown();
    renderExaminerDropdown();
    renderTemplateDropdown();
    initBookmarkletUi();
  }

  window.KakapCPPT = {
    init,
    renderPatientDropdown,
    renderExaminerDropdown,
    renderTemplateDropdown,
    onPatientChange,
    onShiftChange,
    onExaminerChange,
    addExaminer,
    removeExaminer,
    updateObjekFromVitals,
    applySelectedTemplate,
    duplicateFromPrevious,
    copySingleField,
    copyAllPackage,
    openTemplateEditor,
    closeTemplateEditor,
    saveTemplateFromModal,
    editTemplate,
    deleteTemplate,
    toggleSection,
    getBookmarkletSource,
    getBookmarkletHref,
    copyBookmarkletCode,
    copyTampermonkeyCode
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(init, 250));
  } else {
    setTimeout(init, 250);
  }
})(window);
