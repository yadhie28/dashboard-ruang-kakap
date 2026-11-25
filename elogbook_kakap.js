/**
 * E-Logbook Asuhan Keperawatan 3S (SDKI, SIKI, SLKI) — Khusus Ruang Kakap
 * RSUD dr. Soedarso Pontianak (Rawat Inap Penyakit Dalam • 41 Bed)
 *
 * Fitur:
 * - Database lengkap PPNI 3S (SDKI D.0001-D.0149, SIKI, SLKI) dari window.PPNI_3S_DATA
 * - Rekomendasi otomatis SIKI & SLKI saat diagnosis SDKI dipilih
 * - Unit Kerja terkunci "Ruang Kakap", Shift otomatis mengikuti jam Ruang Kakap (07-14 / 14-20 / 20-07)
 * - Pilihan No. RM + Bed terhubung ke sensus pasien aktif (TANPA menampilkan nama pasien)
 * - Verifikasi satuan & batch oleh Kepala Ruang (Ns. Rusmulyadi, S.Kep., M.A.R.S) dilindungi PIN Mode Klinis
 * - Mengikuti kunci Mode Klinis dashboard (riwayat tersembunyi bila Mode Klinis terkunci)
 * - Penyimpanan lokal rapi + Unduh CSV (UTF-8 BOM untuk Excel) + Pulihkan dari CSV + Opsional Sync Google Sheets
 * - Cetak Laporan A4 resmi Ruang Kakap
 */
(function (window) {
  'use strict';

  const STORAGE_KEY = 'kakap_elogbook_3s_v1';
  const STORAGE_LAST_NURSE = 'kakap_elogbook_last_nurse';
  const STORAGE_GAS_URL = 'kakap_elogbook_gas_url';
  const HEAD_NURSE_NAME = 'Ns. Rusmulyadi, S.Kep., M.A.R.S';
  const UNIT_LABEL = 'Ruang Kakap (Penyakit Dalam • 41 Bed)';

  const lbState = {
    isFormOpen: true,
    selectedSdkiCode: 'D.0077',
    selectedEtiology: '',
    selectedMonth: '',
    catalogSearch: '',
    catalogCategory: 'Semua',
    catalogSelectedCode: 'D.0077',
    catalogSelectedEtiology: '',
    pendingActionAfterPin: null
  };

  function getRefData() {
    return window.PPNI_3S_DATA || { SDKI_CATALOG: [], SIKI_CATALOG: [], SLKI_CATALOG: [], QUICK_DIAGNOSES: [] };
  }

  function esc(str) {
    return String(str === null || str === undefined ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function toast(msg, type = 'info') {
    if (typeof window.showToast === 'function') window.showToast(msg, type);
  }

  function isClinicalUnlocked() {
    return Boolean(window.state && window.state.role === 'clinical');
  }

  function getWibNow() {
    if (typeof window.getWIBTime === 'function') return window.getWIBTime();
    const now = new Date();
    return new Date(now.getTime() + (now.getTimezoneOffset() + 420) * 60000);
  }

  function getTodayIsoWib() {
    const w = getWibNow();
    return `${w.getFullYear()}-${String(w.getMonth() + 1).padStart(2, '0')}-${String(w.getDate()).padStart(2, '0')}`;
  }

  function getCurrentMonthWib() {
    return getTodayIsoWib().slice(0, 7);
  }

  // Pembagian shift resmi Dashboard Ruang Kakap:
  // Pagi 07.00-14.00, Sore 14.00-20.00, Malam 20.00-07.00
  function getCurrentKakapShift() {
    const w = getWibNow();
    const h = w.getHours();
    if (h >= 7 && h < 14) return 'Pagi';
    if (h >= 14 && h < 20) return 'Sore';
    return 'Malam';
  }

  function getRecords() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
      return [];
    }
  }

  function saveRecords(records) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
    } catch (err) {
      toast('Gagal menyimpan ke penyimpanan peramban: ' + err.message, 'error');
    }
  }

  function getGasUrl() {
    try {
      return (localStorage.getItem(STORAGE_GAS_URL) || '').trim();
    } catch (_) {
      return '';
    }
  }

  async function syncRecordToCloud(aksi, payload) {
    const url = getGasUrl();
    if (!url) return;
    try {
      await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain;charset=utf-8' },
        body: JSON.stringify({ aksi, ...payload })
      });
    } catch (_) {
      // Tetap aman tersimpan lokal bila offline
    }
  }

  async function pullFromCloudSpreadsheet() {
    const url = getGasUrl();
    if (!url) return false;
    try {
      const res = await fetch(url + (url.includes('?') ? '&' : '?') + 't=' + Date.now());
      if (!res.ok) return false;
      const json = await res.json();
      if (json && json.ok && Array.isArray(json.records)) {
        const local = getRecords();
        const byId = {};
        local.forEach(r => { byId[r.id] = r; });
        json.records.forEach(r => { byId[r.id] = r; });
        const merged = Object.values(byId).sort((a, b) => String(b.date + b.id).localeCompare(String(a.date + a.id)));
        saveRecords(merged);
        renderAll();
        return true;
      }
    } catch (_) {}
    return false;
  }

  // =========================================================================
  // DAFTAR PERAWAT RUANG KAKAP & PASIEN AKTIF (HANYA NO. RM & BED, TANPA NAMA)
  // =========================================================================
  function getKakapNursesList() {
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

  function populateNurseDropdown() {
    const sel = document.getElementById('lbNurseSelect');
    const customInput = document.getElementById('lbNurseCustomInput');
    if (!sel) return;

    const nurses = getKakapNursesList();
    const lastUsed = localStorage.getItem(STORAGE_LAST_NURSE) || '';
    const currentVal = sel.value || lastUsed;

    let html = '<option value="">-- Pilih Nama Perawat Pelaksana --</option>';
    nurses.forEach(n => {
      html += `<option value="${esc(n)}">${esc(n)}</option>`;
    });
    html += '<option value="__OTHER__">+ Ketik Nama Perawat Lainnya...</option>';
    sel.innerHTML = html;

    if (currentVal && nurses.includes(currentVal)) {
      sel.value = currentVal;
      if (customInput) customInput.style.display = 'none';
    } else if (lastUsed) {
      sel.value = '__OTHER__';
      if (customInput) {
        customInput.style.display = 'block';
        customInput.value = lastUsed;
      }
    }
  }

  function onNurseSelectChange(val) {
    const customInput = document.getElementById('lbNurseCustomInput');
    if (!customInput) return;
    if (val === '__OTHER__') {
      customInput.style.display = 'block';
      customInput.focus();
    } else {
      customInput.style.display = 'none';
      if (val) localStorage.setItem(STORAGE_LAST_NURSE, val);
    }
  }

  function getSelectedNurseName() {
    const sel = document.getElementById('lbNurseSelect');
    const customInput = document.getElementById('lbNurseCustomInput');
    if (!sel) return '';
    if (sel.value === '__OTHER__') {
      return (customInput ? customInput.value : '').trim();
    }
    return (sel.value || '').trim();
  }

  function populateActivePatientMrnPicker() {
    const picker = document.getElementById('lbPatientPicker');
    if (!picker) return;

    const d = window.state && window.state.data;
    const day = (d && d.recentDays && d.recentDays[window.state.currentDate]) || (d && d.today);
    const patients = (day && Array.isArray(day.patients)) ? day.patients.filter(p => !p.isEmpty) : [];

    let html = '<option value="">-- Pilih dari Pasien Dirawat (No. RM &amp; Bed saja) --</option>';
    patients.forEach(p => {
      const mr = String(p.mrNo || '-').trim();
      const bed = String(p.bed || '-').trim();
      const room = String(p.room || '').replace(/\s*\(.*?\)/g, '').trim();
      if (mr && mr !== '-') {
        // PENTING: Hanya tampilkan No. RM dan Bed, JANGAN menampilkan nama pasien
        html += `<option value="${esc(mr)}|${esc(bed)}">Bed ${esc(bed)} (${esc(room)}) — RM: ${esc(mr)}</option>`;
      }
    });
    picker.innerHTML = html;
  }

  function onPatientPickerChange(val) {
    if (!val) return;
    const [mr, bed] = val.split('|');
    const mrInput = document.getElementById('lbMrnInput');
    const bedInput = document.getElementById('lbBedInput');
    if (mrInput) mrInput.value = mr || '';
    if (bedInput) bedInput.value = bed || '';
  }

  // =========================================================================
  // FORMULIR 3S (SDKI -> SIKI & SLKI OTOMATIS)
  // =========================================================================
  function populateSdkiDropdown() {
    const select = document.getElementById('lbSdkiSelect');
    if (!select) return;
    const { SDKI_CATALOG } = getRefData();
    const grouped = {};
    SDKI_CATALOG.forEach(item => {
      const key = `${item.category} • ${item.subcategory}`;
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(item);
    });

    let html = '<option value="">-- Pilih Diagnosis SDKI (D.0001 s.d. D.0149) --</option>';
    Object.keys(grouped).forEach(grpKey => {
      html += `<optgroup label="${esc(grpKey)}">`;
      grouped[grpKey].forEach(item => {
        html += `<option value="${esc(item.code)}">[${esc(item.code)}] ${esc(item.name)}</option>`;
      });
      html += '</optgroup>';
    });
    select.innerHTML = html;
    if (lbState.selectedSdkiCode) select.value = lbState.selectedSdkiCode;
  }

  function populateSikiDropdown(sdkiItem) {
    const sikiSelect = document.getElementById('lbSikiSelect');
    if (!sikiSelect) return;
    const { SIKI_CATALOG } = getRefData();

    let html = '';
    const recGroup = [];
    if (sdkiItem && sdkiItem.recommendedSiki) {
      const r = sdkiItem.recommendedSiki;
      recGroup.push({
        val: `${r.code} - ${r.title} (${r.actionDetail})`,
        label: `⭐ [Rekomendasi Utama] ${r.code} - ${r.title}`
      });
    }
    if (sdkiItem && Array.isArray(sdkiItem.alternativeSiki)) {
      sdkiItem.alternativeSiki.forEach(alt => {
        recGroup.push({
          val: `${alt.code} - ${alt.title} (${alt.actionDetail})`,
          label: `🔸 [Alternatif Terkait] ${alt.code} - ${alt.title}`
        });
      });
    }
    if (recGroup.length > 0) {
      html += `<optgroup label="⭐ REKOMENDASI SIKI (${esc(sdkiItem.code)})">`;
      recGroup.forEach(it => {
        html += `<option value="${esc(it.val)}">${esc(it.label)}</option>`;
      });
      html += '</optgroup>';
    }

    const grouped = {};
    SIKI_CATALOG.forEach(s => {
      const gk = `${s.category} • ${s.subcategory}`;
      if (!grouped[gk]) grouped[gk] = [];
      grouped[gk].push(s);
    });
    Object.keys(grouped).forEach(grp => {
      html += `<optgroup label="SIKI: ${esc(grp.toUpperCase())}">`;
      grouped[grp].forEach(s => {
        const val = `${s.code} - ${s.title} (${s.actionDetail})`;
        html += `<option value="${esc(val)}">[${esc(s.code)}] ${esc(s.title)}</option>`;
      });
      html += '</optgroup>';
    });

    sikiSelect.innerHTML = html;
    if (recGroup.length > 0) sikiSelect.value = recGroup[0].val;
  }

  function populateSlkiDropdown(sdkiItem) {
    const slkiSelect = document.getElementById('lbSlkiSelect');
    if (!slkiSelect) return;
    const { SLKI_CATALOG } = getRefData();

    let html = '';
    const recGroup = [];
    if (sdkiItem && sdkiItem.recommendedSlki) {
      const r = sdkiItem.recommendedSlki;
      recGroup.push({
        val: `${r.code} - ${r.title} (${r.targetDetail})`,
        label: `⭐ [Luaran Utama] ${r.code} - ${r.title}`
      });
    }
    if (sdkiItem && Array.isArray(sdkiItem.alternativeSlki)) {
      sdkiItem.alternativeSlki.forEach(alt => {
        recGroup.push({
          val: `${alt.code} - ${alt.title} (${alt.targetDetail})`,
          label: `🔸 [Alternatif Terkait] ${alt.code} - ${alt.title}`
        });
      });
    }
    if (recGroup.length > 0) {
      html += `<optgroup label="⭐ REKOMENDASI SLKI (${esc(sdkiItem.code)})">`;
      recGroup.forEach(it => {
        html += `<option value="${esc(it.val)}">${esc(it.label)}</option>`;
      });
      html += '</optgroup>';
    }

    const grouped = {};
    SLKI_CATALOG.forEach(s => {
      const gk = `${s.category} • ${s.subcategory}`;
      if (!grouped[gk]) grouped[gk] = [];
      grouped[gk].push(s);
    });
    Object.keys(grouped).forEach(grp => {
      html += `<optgroup label="SLKI: ${esc(grp.toUpperCase())}">`;
      grouped[grp].forEach(s => {
        const val = `${s.code} - ${s.title} (${s.targetDetail})`;
        html += `<option value="${esc(val)}">[${esc(s.code)}] ${esc(s.title)}</option>`;
      });
      html += '</optgroup>';
    });

    slkiSelect.innerHTML = html;
    if (recGroup.length > 0) slkiSelect.value = recGroup[0].val;
  }

  function renderSikiPreview(sikiVal) {
    const box = document.getElementById('lbPreviewSiki');
    if (!box) return;
    if (!sikiVal) {
      box.innerHTML = '<span style="color:var(--text-muted);">Pilih intervensi SIKI untuk melihat rincian Observasi, Terapeutik, Edukasi, dan Kolaborasi.</span>';
      return;
    }
    const { SIKI_CATALOG } = getRefData();
    const m = sikiVal.match(/I\.\d{5}/);
    const obj = m ? SIKI_CATALOG.find(s => s.code === m[0]) : null;
    if (obj && obj.actions) {
      box.innerHTML = `
        <div class="lb-3s-preview-title">[${esc(obj.code)}] ${esc(obj.title)} <span class="lb-tag-soft">SIKI PPNI</span></div>
        <div class="lb-siki-grid">
          <div><strong>[O] Observasi:</strong> ${esc(obj.actions.observasi)}</div>
          <div><strong>[T] Terapeutik:</strong> ${esc(obj.actions.terapeutik)}</div>
          <div><strong>[E] Edukasi:</strong> ${esc(obj.actions.edukasi)}</div>
          <div><strong>[K] Kolaborasi:</strong> ${esc(obj.actions.kolaborasi)}</div>
        </div>
      `;
    } else {
      box.innerHTML = `<div style="font-size:0.8rem;">${esc(sikiVal)}</div>`;
    }
  }

  function renderSlkiPreview(slkiVal) {
    const box = document.getElementById('lbPreviewSlki');
    if (!box) return;
    if (!slkiVal) {
      box.textContent = 'Pilih luaran SLKI untuk melihat kriteria hasil terukur.';
      return;
    }
    const m = slkiVal.match(/\((.*?)\)$/);
    box.textContent = m ? m[1] : slkiVal;
  }

  function applySdkiSelection(code, forcedEtiology) {
    const { SDKI_CATALOG } = getRefData();
    if (!SDKI_CATALOG.length) return;
    const item = SDKI_CATALOG.find(d => d.code === code) || SDKI_CATALOG[0];
    lbState.selectedSdkiCode = item.code;

    const sel = document.getElementById('lbSdkiSelect');
    if (sel) sel.value = item.code;

    document.querySelectorAll('.lb-quick-sdki-btn').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-code') === item.code);
    });

    const etSel = document.getElementById('lbEtiologySelect');
    if (etSel) {
      let etHtml = '';
      if (Array.isArray(item.commonEtiologies) && item.commonEtiologies.length > 0) {
        etHtml += '<optgroup label="Etiologi / Faktor Penyebab (b.d)">';
        item.commonEtiologies.forEach((et, i) => {
          etHtml += `<option value="${esc(et)}">${i + 1}. ${esc(et)}</option>`;
        });
        etHtml += '</optgroup>';
      }
      etHtml += '<optgroup label="Lainnya">';
      etHtml += '<option value="Faktor individual / kondisi klinis khusus pasien">Faktor individual / kondisi klinis khusus pasien</option>';
      etHtml += '<option value="">(Tanpa etiologi tambahan)</option>';
      etHtml += '</optgroup>';
      etSel.innerHTML = etHtml;
      const defEt = (forcedEtiology !== undefined) ? forcedEtiology : ((item.commonEtiologies && item.commonEtiologies[0]) || '');
      etSel.value = defEt;
      lbState.selectedEtiology = defEt;
    }

    populateSikiDropdown(item);
    populateSlkiDropdown(item);
    updateLivePreviews();
  }

  function selectQuickDiagnosis(code) {
    applySdkiSelection(code);
  }

  function updateLivePreviews() {
    const { SDKI_CATALOG } = getRefData();
    const item = SDKI_CATALOG.find(d => d.code === lbState.selectedSdkiCode) || SDKI_CATALOG[0];
    if (!item) return;

    const et = lbState.selectedEtiology;
    const fullDiag = et ? `${item.code} - ${item.name} b.d ${et}` : `${item.code} - ${item.name}`;
    const cEl = document.getElementById('lbPreviewSdkiCode');
    const tEl = document.getElementById('lbPreviewSdkiText');
    const catEl = document.getElementById('lbPreviewSdkiCat');
    if (cEl) cEl.textContent = item.code;
    if (tEl) tEl.textContent = fullDiag;
    if (catEl) catEl.textContent = `${item.category} • ${item.subcategory}`;

    const sikiSel = document.getElementById('lbSikiSelect');
    if (sikiSel) renderSikiPreview(sikiSel.value);
    const slkiSel = document.getElementById('lbSlkiSelect');
    if (slkiSel) renderSlkiPreview(slkiSel.value);
  }

  function onEtiologyChange(val) {
    lbState.selectedEtiology = val;
    updateLivePreviews();
  }

  function onSikiChange() {
    const s = document.getElementById('lbSikiSelect');
    if (s) renderSikiPreview(s.value);
  }

  function onSlkiChange() {
    const s = document.getElementById('lbSlkiSelect');
    if (s) renderSlkiPreview(s.value);
  }

  function toggleForm(forceState) {
    const box = document.getElementById('lbFormCard');
    const btn = document.getElementById('btnLbToggleForm');
    if (!box) return;
    lbState.isFormOpen = (typeof forceState === 'boolean') ? forceState : !lbState.isFormOpen;
    box.style.display = lbState.isFormOpen ? 'block' : 'none';
    if (btn) {
      btn.textContent = lbState.isFormOpen ? '✕ Tutup Formulir' : '+ Catat Asuhan 3S Baru';
    }
    if (lbState.isFormOpen) {
      initFormDefaults();
    }
  }

  function initFormDefaults() {
    const dateEl = document.getElementById('lbDateInput');
    if (dateEl && !dateEl.value) dateEl.value = getTodayIsoWib();
    const shiftEl = document.getElementById('lbShiftSelect');
    if (shiftEl) shiftEl.value = getCurrentKakapShift();
    const unitEl = document.getElementById('lbUnitInput');
    if (unitEl) unitEl.value = UNIT_LABEL;

    populateNurseDropdown();
    populateActivePatientMrnPicker();
    populateSdkiDropdown();
    applySdkiSelection(lbState.selectedSdkiCode || 'D.0077');
  }

  function resetForm() {
    const errEl = document.getElementById('lbFormError');
    if (errEl) errEl.style.display = 'none';
    const mrEl = document.getElementById('lbMrnInput');
    const bedEl = document.getElementById('lbBedInput');
    const picker = document.getElementById('lbPatientPicker');
    const notesEl = document.getElementById('lbNotesInput');
    if (mrEl) mrEl.value = '';
    if (bedEl) bedEl.value = '';
    if (picker) picker.value = '';
    if (notesEl) notesEl.value = '';
    const dateEl = document.getElementById('lbDateInput');
    if (dateEl) dateEl.value = getTodayIsoWib();
    const shiftEl = document.getElementById('lbShiftSelect');
    if (shiftEl) shiftEl.value = getCurrentKakapShift();
  }

  function showFormError(msg, focusId) {
    const errEl = document.getElementById('lbFormError');
    if (errEl) {
      errEl.textContent = '⚠️ ' + msg;
      errEl.style.display = 'block';
    }
    toast(msg, 'warning');
    if (focusId) {
      const f = document.getElementById(focusId);
      if (f) f.focus();
    }
  }

  // =========================================================================
  // SIMPAN ENTRI BARU (VALIDASI LENGKAP WAJIB BERTANDA BINTANG)
  // =========================================================================
  function saveRecord(e) {
    if (e) e.preventDefault();
    const errEl = document.getElementById('lbFormError');
    if (errEl) errEl.style.display = 'none';

    const date = (document.getElementById('lbDateInput')?.value || '').trim();
    const shift = (document.getElementById('lbShiftSelect')?.value || '').trim();
    const nurseName = getSelectedNurseName();
    const mrn = (document.getElementById('lbMrnInput')?.value || '').trim();
    const bed = (document.getElementById('lbBedInput')?.value || '').trim();
    const sdkiCode = (document.getElementById('lbSdkiSelect')?.value || '').trim();
    const category = (document.getElementById('lbCategorySelect')?.value || '').trim();
    const sikiVal = (document.getElementById('lbSikiSelect')?.value || '').trim();
    const slkiVal = (document.getElementById('lbSlkiSelect')?.value || '').trim();
    const notes = (document.getElementById('lbNotesInput')?.value || '').trim();

    if (!date) return showFormError('Tanggal Pelaksanaan wajib diisi.', 'lbDateInput');
    if (!shift) return showFormError('Shift Dinas wajib dipilih.', 'lbShiftSelect');
    if (!nurseName) return showFormError('Nama Perawat Pelaksana wajib dipilih atau diisi.', 'lbNurseSelect');
    if (!mrn) return showFormError('No. Rekam Medis (RM) pasien wajib diisi atau dipilih.', 'lbMrnInput');
    if (!sdkiCode) return showFormError('Diagnosis Keperawatan (SDKI) wajib dipilih.', 'lbSdkiSelect');
    if (!category) return showFormError('Kategori Tindakan wajib dipilih.', 'lbCategorySelect');
    if (!sikiVal) return showFormError('Intervensi Keperawatan (SIKI) wajib dipilih.', 'lbSikiSelect');
    if (!slkiVal) return showFormError('Luaran Keperawatan (SLKI) wajib dipilih.', 'lbSlkiSelect');

    localStorage.setItem(STORAGE_LAST_NURSE, nurseName);

    const { SDKI_CATALOG } = getRefData();
    const item = SDKI_CATALOG.find(d => d.code === sdkiCode);
    const et = lbState.selectedEtiology;
    const sdkiDiagnosis = item
      ? (et ? `${item.code} - ${item.name} b.d ${et}` : `${item.code} - ${item.name}`)
      : sdkiCode;

    const newRecord = {
      id: 'KKP-' + Date.now().toString(36).toUpperCase(),
      date,
      shift,
      patientMrn: mrn,
      patientBed: bed,
      nurseName,
      workUnit: 'Ruang Kakap',
      sdkiCode: item ? item.code : sdkiCode,
      sdkiDiagnosis,
      sikiIntervention: sikiVal,
      slkiOutcome: slkiVal,
      actionCategory: category,
      notes: notes || 'Asuhan keperawatan dilaksanakan sesuai standar 3S PPNI.',
      verifiedByHeadNurse: false,
      verifiedAt: '',
      verifiedBy: ''
    };

    const records = getRecords();
    records.unshift(newRecord);
    saveRecords(records);
    syncRecordToCloud('upsert', { record: newRecord });

    // Pastikan bulan ringkasan ikut mengarah ke bulan entri yang baru disimpan
    lbState.selectedMonth = date.slice(0, 7);
    populateMonthFilter();
    renderAll();

    // Bersihkan isian pasien & catatan saja (nama perawat tetap diingat)
    const mrEl = document.getElementById('lbMrnInput');
    const bedEl = document.getElementById('lbBedInput');
    const picker = document.getElementById('lbPatientPicker');
    const notesEl = document.getElementById('lbNotesInput');
    if (mrEl) mrEl.value = '';
    if (bedEl) bedEl.value = '';
    if (picker) picker.value = '';
    if (notesEl) notesEl.value = '';

    toast(`Entri E-Logbook (${mrn} • ${newRecord.sdkiCode}) berhasil disimpan!`, 'success');
  }

  // =========================================================================
  // RINGKASAN BULANAN, TABEL RIWAYAT & KUNCI MODE KLINIS
  // =========================================================================
  function populateMonthFilter() {
    const sel = document.getElementById('lbMonthSelect');
    if (!sel) return;
    const months = new Set([getCurrentMonthWib()]);
    getRecords().forEach(r => {
      if (r.date && r.date.length >= 7) months.add(r.date.slice(0, 7));
    });
    const sorted = Array.from(months).sort((a, b) => b.localeCompare(a));
    const names = ['Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus','September','Oktober','November','Desember'];
    sel.innerHTML = sorted.map(ym => {
      const [y, m] = ym.split('-');
      const label = `${names[parseInt(m, 10) - 1] || m} ${y}`;
      return `<option value="${esc(ym)}">${esc(label)}</option>`;
    }).join('');
    if (!lbState.selectedMonth || !sorted.includes(lbState.selectedMonth)) {
      lbState.selectedMonth = getCurrentMonthWib();
    }
    sel.value = lbState.selectedMonth;
  }

  function getMonthRecords() {
    const ym = lbState.selectedMonth || getCurrentMonthWib();
    return getRecords().filter(r => (r.date || '').startsWith(ym));
  }

  function renderMetrics() {
    const records = getMonthRecords();
    const total = records.length;
    const mandiri = records.filter(r => r.actionCategory === 'Mandiri').length;
    const kolab = records.filter(r => r.actionCategory === 'Kolaboratif').length;
    const verified = records.filter(r => r.verifiedByHeadNurse).length;
    const pct = total > 0 ? Math.round((verified / total) * 100) : 0;

    const setTxt = (id, t) => { const el = document.getElementById(id); if (el) el.textContent = t; };
    setTxt('lbMetricTotal', `${total} Tindakan`);
    setTxt('lbMetricMandiri', `${mandiri} Tindakan`);
    setTxt('lbMetricKolaboratif', `${kolab} Tindakan`);
    setTxt('lbMetricKaru', total > 0 ? `${pct}% Disahkan (${verified}/${total})` : 'Belum ada entri');
    setTxt('lbTabCountBadge', String(getRecords().length));
  }

  function renderHistorySection() {
    const lockedBox = document.getElementById('lbHistoryLockedState');
    const unlockedBox = document.getElementById('lbHistoryUnlockedState');
    const unlocked = isClinicalUnlocked();

    if (lockedBox) lockedBox.style.display = unlocked ? 'none' : 'flex';
    if (unlockedBox) unlockedBox.style.display = unlocked ? 'block' : 'none';
    if (!unlocked) return;

    const tbody = document.getElementById('lbTableBody');
    if (!tbody) return;

    const shiftF = document.getElementById('lbFilterShift')?.value || 'all';
    const catF = document.getElementById('lbFilterCategory')?.value || 'all';
    const statF = document.getElementById('lbFilterStatus')?.value || 'all';
    const q = (document.getElementById('lbSearchInput')?.value || '').toLowerCase().trim();

    let list = getMonthRecords();
    if (shiftF !== 'all') list = list.filter(r => (r.shift || '').toLowerCase() === shiftF.toLowerCase());
    if (catF !== 'all') list = list.filter(r => (r.actionCategory || '').toLowerCase() === catF.toLowerCase());
    if (statF === 'verified') list = list.filter(r => r.verifiedByHeadNurse);
    if (statF === 'pending') list = list.filter(r => !r.verifiedByHeadNurse);
    if (q) {
      list = list.filter(r =>
        (r.nurseName || '').toLowerCase().includes(q) ||
        (r.patientMrn || '').toLowerCase().includes(q) ||
        (r.sdkiDiagnosis || '').toLowerCase().includes(q) ||
        (r.sikiIntervention || '').toLowerCase().includes(q) ||
        (r.slkiOutcome || '').toLowerCase().includes(q) ||
        (r.notes || '').toLowerCase().includes(q)
      );
    }

    if (list.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align:center; padding:2.25rem 1rem; color:var(--text-muted);">
            <div style="font-size:1.75rem; margin-bottom:0.4rem;">📋</div>
            <strong>Belum ada entri logbook</strong>
            <div style="font-size:0.82rem; margin-top:0.25rem;">Isi formulir di atas lalu klik <strong>Simpan Entri Logbook</strong> untuk mulai mencatat asuhan 3S Ruang Kakap.</div>
          </td>
        </tr>`;
      return;
    }

    tbody.innerHTML = list.map(r => {
      const catCls = r.actionCategory === 'Mandiri' ? 'lb-badge-mandiri'
        : r.actionCategory === 'Kolaboratif' ? 'lb-badge-kolab'
        : r.actionCategory === 'Edukasi' ? 'lb-badge-edukasi' : 'lb-badge-obs';
      const statusBadge = r.verifiedByHeadNurse
        ? '<span class="lb-badge-verified">✓ Disetujui Kepala Ruang</span>'
        : '<span class="lb-badge-pending">⏳ Menunggu Review</span>';
      const bedInfo = r.patientBed ? `<div style="font-size:0.72rem;color:var(--text-muted);">Bed ${esc(r.patientBed)}</div>` : '';

      return `
        <tr>
          <td style="white-space:nowrap;">
            <strong>${esc(r.date)}</strong>
            <div style="font-size:0.74rem;color:var(--text-muted);">Shift ${esc(r.shift)}</div>
          </td>
          <td style="white-space:nowrap;">
            <code style="font-weight:700;color:var(--accent-primary);">${esc(r.patientMrn)}</code>
            ${bedInfo}
          </td>
          <td>
            <div style="font-weight:700;font-size:0.84rem;">${esc(r.nurseName)}</div>
          </td>
          <td style="min-width:220px;">
            <div style="font-weight:700;font-size:0.83rem;">${esc(r.sdkiDiagnosis)}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);margin-top:2px;">↳ ${esc((r.sikiIntervention || '').slice(0, 90))}${(r.sikiIntervention || '').length > 90 ? '…' : ''}</div>
          </td>
          <td style="min-width:170px;font-size:0.78rem;">${esc((r.slkiOutcome || '').slice(0, 80))}${(r.slkiOutcome || '').length > 80 ? '…' : ''}</td>
          <td style="white-space:nowrap;">
            <span class="lb-cat-badge ${catCls}">${esc(r.actionCategory)}</span>
            <div style="margin-top:4px;">${statusBadge}</div>
          </td>
          <td style="white-space:nowrap;text-align:right;">
            <button type="button" class="btn btn-secondary btn-xs" onclick="KakapELogbook.viewDetail('${esc(r.id)}')">Detail</button>
            ${!r.verifiedByHeadNurse ? `<button type="button" class="btn btn-primary btn-xs" onclick="KakapELogbook.verifySingle('${esc(r.id)}')">Sahkan</button>` : ''}
            <button type="button" class="btn btn-secondary btn-xs" style="color:#dc2626;" onclick="KakapELogbook.deleteRecord('${esc(r.id)}')" title="Hapus">Hapus</button>
          </td>
        </tr>
      `;
    }).join('');
  }

  // =========================================================================
  // VERIFIKASI KEPALA RUANG (DILINDUNGI PIN MODE KLINIS YANG SUDAH ADA)
  // =========================================================================
  function requireClinicalPinFor(callback) {
    if (isClinicalUnlocked()) {
      callback();
      return true;
    }
    lbState.pendingActionAfterPin = callback;
    toast('Verifikasi Kepala Ruang memerlukan PIN Mode Klinis terlebih dahulu.', 'warning');
    if (typeof window.openPinModal === 'function') window.openPinModal();
    return false;
  }

  function verifySingle(id) {
    return requireClinicalPinFor(() => {
      const records = getRecords();
      const target = records.find(r => r.id === id);
      if (!target) return;
      target.verifiedByHeadNurse = true;
      target.verifiedBy = HEAD_NURSE_NAME;
      target.verifiedAt = getTodayIsoWib();
      saveRecords(records);
      syncRecordToCloud('upsert', { record: target });
      renderAll();
      toast(`Entri ${target.patientMrn} berhasil disahkan oleh Kepala Ruang.`, 'success');
    });
  }

  function verifyBatch() {
    return requireClinicalPinFor(() => {
      const ym = lbState.selectedMonth || getCurrentMonthWib();
      const records = getRecords();
      let count = 0;
      records.forEach(r => {
        if ((r.date || '').startsWith(ym) && !r.verifiedByHeadNurse) {
          r.verifiedByHeadNurse = true;
          r.verifiedBy = HEAD_NURSE_NAME;
          r.verifiedAt = getTodayIsoWib();
          syncRecordToCloud('upsert', { record: r });
          count++;
        }
      });
      if (count === 0) {
        toast('Semua entri pada bulan ini sudah disahkan oleh Kepala Ruang.', 'info');
        return;
      }
      saveRecords(records);
      renderAll();
      toast(`${count} entri asuhan 3S berhasil disahkan sekaligus oleh Kepala Ruang.`, 'success');
    });
  }

  function deleteRecord(id) {
    if (!confirm('Yakin ingin menghapus catatan logbook ini?')) return;
    const records = getRecords().filter(r => r.id !== id);
    saveRecords(records);
    syncRecordToCloud('delete', { id });
    renderAll();
    toast('Catatan logbook dihapus.', 'info');
  }

  // =========================================================================
  // MODAL DETAIL, MODAL KATALOG SDKI & CETAK A4
  // =========================================================================
  function openLocalModal(id) {
    const m = document.getElementById(id);
    if (m) m.style.display = 'flex';
  }

  function closeLocalModal(id) {
    const m = document.getElementById(id);
    if (m) m.style.display = 'none';
  }

  function openSdkiCatalog() {
    lbState.catalogSearch = '';
    lbState.catalogCategory = 'Semua';
    lbState.catalogSelectedCode = lbState.selectedSdkiCode || 'D.0077';
    const inp = document.getElementById('lbCatalogSearchInput');
    if (inp) inp.value = '';
    renderCatalogPills();
    renderCatalogList();
    renderCatalogDetail();
    openLocalModal('lbSdkiCatalogModal');
  }

  function renderCatalogPills() {
    const cats = ['Semua', 'Fisiologis', 'Psikologis', 'Perilaku', 'Relasional', 'Lingkungan'];
    const box = document.getElementById('lbCatalogCategoryPills');
    if (!box) return;
    box.innerHTML = cats.map(c => `
      <button type="button" class="filter-chip ${lbState.catalogCategory === c ? 'active' : ''}" onclick="KakapELogbook.setCatalogCategory('${c}')">${c}</button>
    `).join('');
  }

  function setCatalogCategory(cat) {
    lbState.catalogCategory = cat;
    renderCatalogPills();
    renderCatalogList();
  }

  function onCatalogSearch(q) {
    const val = (q === undefined) ? (document.getElementById('lbCatalogSearchInput')?.value || '') : q;
    lbState.catalogSearch = String(val || '').toLowerCase().trim();
    renderCatalogList();
  }

  function renderCatalogList() {
    const box = document.getElementById('lbCatalogList');
    const countEl = document.getElementById('lbCatalogCount');
    if (!box) return;
    const { SDKI_CATALOG } = getRefData();
    const filtered = SDKI_CATALOG.filter(it => {
      if (lbState.catalogCategory !== 'Semua' && it.category !== lbState.catalogCategory) return false;
      if (!lbState.catalogSearch) return true;
      const q = lbState.catalogSearch;
      return it.code.toLowerCase().includes(q) ||
        it.name.toLowerCase().includes(q) ||
        (it.subcategory || '').toLowerCase().includes(q) ||
        (it.definition || '').toLowerCase().includes(q);
    });
    if (countEl) countEl.textContent = `${filtered.length} Diagnosis Ditemukan`;
    if (filtered.length === 0) {
      box.innerHTML = '<div style="padding:1.5rem;text-align:center;color:var(--text-muted);">Tidak ditemukan diagnosis SDKI dengan kata kunci tersebut.</div>';
      return;
    }
    box.innerHTML = filtered.map(it => `
      <div class="lb-cat-item ${it.code === lbState.catalogSelectedCode ? 'selected' : ''}" onclick="KakapELogbook.selectCatalogItem('${esc(it.code)}')">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;">
          <span class="lb-code-pill">${esc(it.code)}</span>
          <span style="font-size:0.72rem;color:var(--text-muted);">${esc(it.category)} • ${esc(it.subcategory)}</span>
        </div>
        <div style="font-weight:700;margin-top:4px;font-size:0.88rem;">${esc(it.name)}</div>
      </div>
    `).join('');
  }

  function selectCatalogItem(code) {
    lbState.catalogSelectedCode = code;
    renderCatalogList();
    renderCatalogDetail();
  }

  function renderCatalogDetail() {
    const box = document.getElementById('lbCatalogDetail');
    if (!box) return;
    const { SDKI_CATALOG } = getRefData();
    const it = SDKI_CATALOG.find(d => d.code === lbState.catalogSelectedCode) || SDKI_CATALOG[0];
    if (!it) return;
    lbState.catalogSelectedEtiology = (it.commonEtiologies && it.commonEtiologies[0]) || '';

    const etHtml = (it.commonEtiologies && it.commonEtiologies.length > 0)
      ? it.commonEtiologies.map((et, idx) => `
          <label style="display:flex;gap:6px;align-items:flex-start;font-size:0.8rem;margin-bottom:4px;cursor:pointer;">
            <input type="radio" name="lbCatEt" value="${esc(et)}" ${idx === 0 ? 'checked' : ''} onchange="KakapELogbook.setCatalogEtiology(this.value)">
            <span>${esc(et)}</span>
          </label>
        `).join('')
      : '<div style="font-size:0.8rem;color:var(--text-muted);">Tanpa etiologi khusus.</div>';

    box.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px;">
        <span class="lb-code-pill">${esc(it.code)}</span>
        <span style="font-size:0.75rem;color:var(--text-muted);">${esc(it.category)} • ${esc(it.subcategory)}</span>
      </div>
      <h4 style="margin:0 0 6px 0;">${esc(it.name)}</h4>
      <p style="font-size:0.8rem;color:var(--text-muted);margin:0 0 10px 0;">${esc(it.definition || '')}</p>
      <div class="lb-detail-subbox"><strong>Pilih Etiologi (b.d):</strong><div style="margin-top:6px;">${etHtml}</div></div>
      <div class="lb-detail-subbox lb-subbox-siki">
        <strong>Rekomendasi SIKI Utama:</strong>
        <div style="font-weight:700;margin-top:2px;">${it.recommendedSiki ? esc(it.recommendedSiki.code + ' - ' + it.recommendedSiki.title) : '-'}</div>
        <div style="font-size:0.76rem;margin-top:2px;">${it.recommendedSiki ? esc(it.recommendedSiki.actionDetail) : ''}</div>
      </div>
      <div class="lb-detail-subbox lb-subbox-slki">
        <strong>Rekomendasi SLKI Utama:</strong>
        <div style="font-weight:700;margin-top:2px;">${it.recommendedSlki ? esc(it.recommendedSlki.code + ' - ' + it.recommendedSlki.title) : '-'}</div>
        <div style="font-size:0.76rem;margin-top:2px;">${it.recommendedSlki ? esc(it.recommendedSlki.targetDetail) : ''}</div>
      </div>
      <button type="button" class="btn btn-primary" style="width:100%;margin-top:10px;justify-content:center;" onclick="KakapELogbook.confirmCatalogSelection()">
        ✓ Gunakan Diagnosis Ini di Formulir
      </button>
    `;
  }

  function setCatalogEtiology(v) { lbState.catalogSelectedEtiology = v; }

  function confirmCatalogSelection() {
    applySdkiSelection(lbState.catalogSelectedCode, lbState.catalogSelectedEtiology);
    toggleForm(true);
    closeLocalModal('lbSdkiCatalogModal');
    toast(`Diagnosis [${lbState.catalogSelectedCode}] & rekomendasi SIKI/SLKI diterapkan ke formulir.`, 'info');
  }

  function viewDetail(id) {
    const rec = getRecords().find(r => r.id === id);
    const body = document.getElementById('lbDetailModalBody');
    if (!rec || !body) return;

    body.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:12px;">
        <div>
          <div style="font-size:0.74rem;color:var(--text-muted);">ID Dokumen: ${esc(rec.id)}</div>
          <h3 style="margin:2px 0 0 0;">RM: ${esc(rec.patientMrn)}${rec.patientBed ? ' • Bed ' + esc(rec.patientBed) : ''}</h3>
        </div>
        ${rec.verifiedByHeadNurse
          ? '<span class="lb-badge-verified">✓ Disetujui Kepala Ruang</span>'
          : '<span class="lb-badge-pending">⏳ Menunggu Review Kepala Ruang</span>'}
      </div>
      <div class="lb-detail-meta-grid">
        <div><span>Perawat Pelaksana</span><strong>${esc(rec.nurseName)}</strong></div>
        <div><span>Tanggal &amp; Shift</span><strong>${esc(rec.date)} • Shift ${esc(rec.shift)}</strong></div>
        <div><span>Kategori Tindakan</span><strong>${esc(rec.actionCategory)}</strong></div>
        <div><span>Unit Kerja</span><strong>Ruang Kakap (Penyakit Dalam)</strong></div>
      </div>
      <div class="lb-detail-subbox"><strong>Diagnosis Keperawatan (SDKI):</strong><div style="margin-top:4px;font-weight:700;">${esc(rec.sdkiDiagnosis)}</div></div>
      <div class="lb-detail-subbox lb-subbox-siki"><strong>Intervensi Keperawatan (SIKI):</strong><div style="margin-top:4px;">${esc(rec.sikiIntervention)}</div></div>
      <div class="lb-detail-subbox lb-subbox-slki"><strong>Target Luaran (SLKI):</strong><div style="margin-top:4px;">${esc(rec.slkiOutcome)}</div></div>
      <div class="lb-detail-subbox"><strong>Catatan Evaluasi / SOAP:</strong><div style="margin-top:4px;">${esc(rec.notes || '-')}</div></div>
      <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:12px;">
        ${!rec.verifiedByHeadNurse ? `<button type="button" class="btn btn-primary" onclick="KakapELogbook.verifySingle('${esc(rec.id)}'); KakapELogbook.closeLocalModal('lbDetailModal');">✓ Sahkan (Kepala Ruang)</button>` : ''}
        <button type="button" class="btn btn-secondary" onclick="KakapELogbook.closeLocalModal('lbDetailModal')">Tutup</button>
      </div>
    `;
    openLocalModal('lbDetailModal');
  }

  function openPrintModal() {
    if (!isClinicalUnlocked()) {
      toast('Buka Mode Klinis dengan PIN terlebih dahulu untuk mencetak laporan logbook.', 'warning');
      if (typeof window.openPinModal === 'function') window.openPinModal();
      return;
    }
    const records = getMonthRecords();
    const box = document.getElementById('lbPrintModalBody');
    if (!box) return;

    const sel = document.getElementById('lbMonthSelect');
    const periodeLabel = sel && sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text : lbState.selectedMonth;
    const todayStr = typeof window.formatIndonesianDate === 'function' ? window.formatIndonesianDate(getTodayIsoWib()) : getTodayIsoWib();
    const nursesInReport = Array.from(new Set(records.map(r => r.nurseName).filter(Boolean)));
    const nurseDisplay = nursesInReport.length === 1 ? nursesInReport[0] : (nursesInReport.length > 1 ? `${nursesInReport.length} Perawat Ruang Kakap` : (getSelectedNurseName() || '-'));

    const rowsHtml = records.length > 0
      ? records.map((r, idx) => `
          <tr>
            <td style="text-align:center;">${idx + 1}</td>
            <td>${esc(r.date)}<br><small>Shift ${esc(r.shift)}</small></td>
            <td style="font-family:monospace;font-weight:bold;">${esc(r.patientMrn)}${r.patientBed ? '<br><small>Bed ' + esc(r.patientBed) + '</small>' : ''}</td>
            <td>${esc(r.nurseName)}</td>
            <td><strong>${esc(r.sdkiDiagnosis)}</strong><br><small>${esc((r.sikiIntervention || '').slice(0, 120))}</small></td>
            <td>${esc((r.slkiOutcome || '').slice(0, 100))}</td>
            <td style="text-align:center;">${esc(r.actionCategory)}</td>
            <td style="text-align:center;">${r.verifiedByHeadNurse ? 'DISETUJUI' : 'Menunggu'}</td>
          </tr>
        `).join('')
      : '<tr><td colspan="8" style="text-align:center;padding:18px;">Belum ada entri logbook pada periode ini.</td></tr>';

    box.innerHTML = `
      <div id="lbPrintAreaA4" style="font-family:Arial,sans-serif;color:#000;background:#fff;padding:12px;line-height:1.4;">
        <div style="border-bottom:2px solid #000;padding-bottom:8px;margin-bottom:12px;text-align:center;">
          <div style="font-size:10pt;font-weight:bold;">PEMERINTAH PROVINSI KALIMANTAN BARAT</div>
          <div style="font-size:13pt;font-weight:bold;">RSUD dr. SOEDARSO PONTIANAK — RUANG KAKAP</div>
          <div style="font-size:9pt;">Rawat Inap Penyakit Dalam (41 Bed: Tim I 21 Bed &bull; Tim II 20 Bed)</div>
        </div>
        <div style="text-align:center;margin-bottom:12px;">
          <div style="font-size:11pt;font-weight:bold;text-decoration:underline;">LAPORAN REKAPITULASI E-LOGBOOK ASUHAN KEPERAWATAN 3S (SDKI, SIKI, SLKI)</div>
          <div style="font-size:9pt;margin-top:2px;">Periode: ${esc(periodeLabel)} &bull; Tanggal Cetak: ${esc(todayStr)}</div>
        </div>
        <div style="display:flex;justify-content:space-between;flex-wrap:wrap;font-size:9pt;margin-bottom:10px;">
          <div><strong>Unit Kerja:</strong> Ruang Kakap (Penyakit Dalam)</div>
          <div><strong>Perawat Pelaksana:</strong> ${esc(nurseDisplay)}</div>
          <div><strong>Total Entri:</strong> ${records.length} Tindakan</div>
        </div>
        <table style="width:100%;border-collapse:collapse;font-size:8pt;margin-bottom:16px;">
          <thead>
            <tr style="background:#f1f5f9;">
              <th style="border:1px solid #000;padding:5px;width:28px;">No</th>
              <th style="border:1px solid #000;padding:5px;width:72px;">Tanggal / Shift</th>
              <th style="border:1px solid #000;padding:5px;width:78px;">No. RM / Bed</th>
              <th style="border:1px solid #000;padding:5px;width:95px;">Perawat</th>
              <th style="border:1px solid #000;padding:5px;">Diagnosis SDKI &amp; Intervensi SIKI</th>
              <th style="border:1px solid #000;padding:5px;width:130px;">Luaran SLKI</th>
              <th style="border:1px solid #000;padding:5px;width:65px;">Kategori</th>
              <th style="border:1px solid #000;padding:5px;width:68px;">Verifikasi</th>
            </tr>
          </thead>
          <tbody>${rowsHtml}</tbody>
        </table>
        <div style="display:flex;justify-content:space-between;margin-top:24px;font-size:9pt;page-break-inside:avoid;">
          <div style="text-align:center;width:45%;">
            <div>Mengetahui,</div>
            <div style="font-weight:bold;">Kepala Ruang Kakap</div>
            <div style="height:56px;"></div>
            <div style="font-weight:bold;text-decoration:underline;">${HEAD_NURSE_NAME}</div>
          </div>
          <div style="text-align:center;width:45%;">
            <div>Pontianak, ${esc(todayStr)}</div>
            <div style="font-weight:bold;">Perawat Pelaksana</div>
            <div style="height:56px;"></div>
            <div style="font-weight:bold;text-decoration:underline;">${esc(nurseDisplay)}</div>
          </div>
        </div>
      </div>
    `;
    openLocalModal('lbPrintModal');
  }

  function printA4() {
    const area = document.getElementById('lbPrintAreaA4');
    if (!area) return;
    const win = window.open('', '_blank');
    if (!win) {
      window.print();
      return;
    }
    win.document.write(`<!DOCTYPE html><html lang="id"><head><meta charset="UTF-8"><title>Laporan E-Logbook 3S Ruang Kakap</title>
      <style>
        @page { size: A4 portrait; margin: 14mm; }
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; color: #000; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #000; padding: 5px; font-size: 8pt; vertical-align: top; }
        th { background: #f1f5f9; }
        tr { page-break-inside: avoid; }
      </style>
    </head><body onload="window.print();">${area.innerHTML}</body></html>`);
    win.document.close();
  }

  // =========================================================================
  // EKSPOR CSV (UTF-8 BOM) & PULIHKAN DARI CSV
  // =========================================================================
  function exportCsv() {
    if (!isClinicalUnlocked()) {
      toast('Buka Mode Klinis dengan PIN terlebih dahulu untuk mengunduh CSV logbook.', 'warning');
      if (typeof window.openPinModal === 'function') window.openPinModal();
      return;
    }
    const records = getRecords();
    const headers = ['ID','Tanggal','Shift','No_RM','Bed','Perawat','Unit','Kode_SDKI','Diagnosis_SDKI','Intervensi_SIKI','Luaran_SLKI','Kategori','Status_Verifikasi','Catatan_SOAP'];
    const q = (v) => '"' + String(v || '').replace(/"/g, '""') + '"';
    const lines = [headers.join(',')];
    records.forEach(r => {
      lines.push([
        q(r.id), q(r.date), q(r.shift), q(r.patientMrn), q(r.patientBed || ''),
        q(r.nurseName), q(r.workUnit || 'Ruang Kakap'), q(r.sdkiCode || ''),
        q(r.sdkiDiagnosis), q(r.sikiIntervention), q(r.slkiOutcome),
        q(r.actionCategory), q(r.verifiedByHeadNurse ? 'Disetujui Kepala Ruang' : 'Menunggu Review'),
        q(r.notes || '')
      ].join(','));
    });

    const csvContent = '\uFEFF' + lines.join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `E-Logbook_3S_Ruang_Kakap_${getTodayIsoWib()}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast(`File CSV (${records.length} entri) berhasil diunduh.`, 'success');
  }

  function parseCsvRows(text) {
    const rows = [];
    let cur = [];
    let val = '';
    let inQuotes = false;
    const clean = text.replace(/^\uFEFF/, '');
    for (let i = 0; i < clean.length; i++) {
      const ch = clean[i];
      if (inQuotes) {
        if (ch === '"' && clean[i + 1] === '"') { val += '"'; i++; }
        else if (ch === '"') { inQuotes = false; }
        else { val += ch; }
      } else {
        if (ch === '"') inQuotes = true;
        else if (ch === ',') { cur.push(val); val = ''; }
        else if (ch === '\n') { cur.push(val.replace(/\r$/, '')); rows.push(cur); cur = []; val = ''; }
        else { val += ch; }
      }
    }
    if (val.length > 0 || cur.length > 0) {
      cur.push(val.replace(/\r$/, ''));
      rows.push(cur);
    }
    return rows;
  }

  function triggerImportCsv() {
    const inp = document.getElementById('lbImportCsvInput');
    if (inp) {
      inp.value = '';
      inp.click();
    }
  }

  function importCsvText(csvText) {
    const rows = parseCsvRows(csvText);
    if (rows.length < 2) {
      toast('File CSV kosong atau format tidak sesuai.', 'warning');
      return 0;
    }
    const existing = getRecords();
    const byId = {};
    existing.forEach(r => { byId[r.id] = r; });

    let imported = 0;
    for (let i = 1; i < rows.length; i++) {
      const r = rows[i];
      if (!r || r.length < 9 || !r[1] || !r[3]) continue;
      const id = r[0] || ('KKP-IMP-' + Date.now() + '-' + i);
      byId[id] = {
        id,
        date: r[1],
        shift: r[2] || 'Pagi',
        patientMrn: r[3],
        patientBed: r[4] || '',
        nurseName: r[5] || 'Perawat Ruang Kakap',
        workUnit: 'Ruang Kakap',
        sdkiCode: r[7] || '',
        sdkiDiagnosis: r[8] || '',
        sikiIntervention: r[9] || '',
        slkiOutcome: r[10] || '',
        actionCategory: r[11] || 'Mandiri',
        verifiedByHeadNurse: (r[12] || '').toLowerCase().includes('disetujui'),
        notes: r[13] || ''
      };
      imported++;
    }
    const merged = Object.values(byId).sort((a, b) => String(b.date + b.id).localeCompare(String(a.date + a.id)));
    saveRecords(merged);
    populateMonthFilter();
    renderAll();
    toast(`${imported} entri berhasil dipulihkan dari file CSV.`, 'success');
    return imported;
  }

  function handleImportCsvFile(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => importCsvText(String(ev.target.result || ''));
    reader.readAsText(file, 'UTF-8');
  }

  function configureCloudSync() {
    const cur = getGasUrl();
    const entered = prompt(
      'Masukkan URL Web App Google Apps Script "Logbook_Kakap" (berakhiran /exec) untuk sinkronisasi bersama antar perangkat.\nBiarkan kosong untuk memakai penyimpanan perangkat saja:',
      cur
    );
    if (entered === null) return;
    const clean = entered.trim();
    if (!clean) {
      localStorage.removeItem(STORAGE_GAS_URL);
      toast('Sinkronisasi spreadsheet bersama dinonaktifkan. Data disimpan di perangkat ini.', 'info');
      return;
    }
    if (!/^https:\/\/script\.google\.com\/macros\/s\/.+\/exec/i.test(clean)) {
      toast('URL tidak valid. Pastikan berakhiran /exec dari Google Apps Script.', 'warning');
      return;
    }
    localStorage.setItem(STORAGE_GAS_URL, clean);
    toast('URL Spreadsheet Logbook_Kakap disimpan! Memuat data bersama...', 'success');
    pullFromCloudSpreadsheet();
  }

  function onClinicalRoleChanged() {
    renderHistorySection();
    if (isClinicalUnlocked() && typeof lbState.pendingActionAfterPin === 'function') {
      const fn = lbState.pendingActionAfterPin;
      lbState.pendingActionAfterPin = null;
      fn();
    }
  }

  function onMonthChange(ym) {
    lbState.selectedMonth = ym;
    renderAll();
  }

  function renderAll() {
    renderMetrics();
    renderHistorySection();
  }

  function init() {
    lbState.selectedMonth = getCurrentMonthWib();
    populateMonthFilter();
    initFormDefaults();
    renderAll();

    const form = document.getElementById('lbEntryForm');
    if (form && !form.dataset.bound) {
      form.dataset.bound = 'true';
      form.addEventListener('submit', saveRecord);
    }
    const fileInp = document.getElementById('lbImportCsvInput');
    if (fileInp && !fileInp.dataset.bound) {
      fileInp.dataset.bound = 'true';
      fileInp.addEventListener('change', (e) => handleImportCsvFile(e.target.files[0]));
    }
    if (getGasUrl()) {
      pullFromCloudSpreadsheet();
    }
  }

  window.KakapELogbook = {
    init,
    toggleForm,
    resetForm,
    initFormDefaults,
    populateNurseDropdown,
    populateActivePatientMrnPicker,
    onNurseSelectChange,
    onPatientPickerChange,
    selectQuickDiagnosis,
    applySdkiSelection,
    onEtiologyChange,
    onSikiChange,
    onSlkiChange,
    saveRecord,
    onMonthChange,
    renderAll,
    renderHistorySection,
    openSdkiCatalog,
    setCatalogCategory,
    onCatalogSearch,
    selectCatalogItem,
    setCatalogEtiology,
    confirmCatalogSelection,
    viewDetail,
    verifySingle,
    verifyBatch,
    deleteRecord,
    openPrintModal,
    printA4,
    exportCsv,
    triggerImportCsv,
    importCsvText,
    configureCloudSync,
    openLocalModal,
    closeLocalModal,
    onClinicalRoleChanged
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(init, 200));
  } else {
    setTimeout(init, 200);
  }
})(window);

