/**
 * Google Apps Script Web App — Penyimpanan Bersama "Logbook_Kakap"
 * Ruang Rawat Inap Kakap (Penyakit Dalam • 41 Bed) - RSUD dr. Soedarso Pontianak
 *
 * Cara pasang singkat (2 menit):
 * 1. Buka https://sheets.new lalu beri nama spreadsheet: Logbook_Kakap
 * 2. Klik menu Ekstensi -> Apps Script
 * 3. Hapus kode lama, tempel seluruh isi file ini, lalu klik ikon Simpan
 * 4. Klik Terapkan (Deploy) -> Deployment baru -> Jenis: Aplikasi web
 *    - Jalankan sebagai: Saya (Me)
 *    - Yang memiliki akses: Siapa saja (Anyone)
 * 5. Klik Terapkan, izinkan akses Google, lalu salin URL yang berakhiran /exec
 * 6. Tempel URL tersebut di menu E-Logbook Asuhan 3S -> tombol "Sinkron Spreadsheet"
 */

var SHEET_NAME = 'Logbook_Kakap';

function getSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.appendRow([
      'id', 'date', 'shift', 'patientMrn', 'patientBed', 'nurseName',
      'workUnit', 'sdkiCode', 'sdkiDiagnosis', 'sikiIntervention',
      'slkiOutcome', 'actionCategory', 'notes', 'verifiedByHeadNurse',
      'verifiedAt', 'verifiedBy', 'updatedAt'
    ]);
    sh.getRange('A1:Q1').setFontWeight('bold');
  }
  return sh;
}

function jsonOut_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function doGet() {
  var sh = getSheet_();
  var rows = sh.getDataRange().getValues();
  var list = [];
  for (var i = 1; i < rows.length; i++) {
    var r = rows[i];
    if (!r[0]) continue;
    list.push({
      id: String(r[0]),
      date: String(r[1]),
      shift: String(r[2]),
      patientMrn: String(r[3]),
      patientBed: String(r[4] || ''),
      nurseName: String(r[5]),
      workUnit: String(r[6] || 'Ruang Kakap'),
      sdkiCode: String(r[7] || ''),
      sdkiDiagnosis: String(r[8]),
      sikiIntervention: String(r[9]),
      slkiOutcome: String(r[10]),
      actionCategory: String(r[11]),
      notes: String(r[12] || ''),
      verifiedByHeadNurse: String(r[13]) === 'TRUE' || r[13] === true,
      verifiedAt: String(r[14] || ''),
      verifiedBy: String(r[15] || '')
    });
  }
  return jsonOut_({ ok: true, records: list.reverse() });
}

function doPost(e) {
  try {
    var body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    var aksi = String(body.aksi || 'upsert');
    var sh = getSheet_();
    var rows = sh.getDataRange().getValues();

    if (aksi === 'delete' && body.id) {
      for (var i = rows.length - 1; i >= 1; i--) {
        if (String(rows[i][0]) === String(body.id)) {
          sh.deleteRow(i + 1);
          return jsonOut_({ ok: true, deleted: body.id });
        }
      }
      return jsonOut_({ ok: true, deleted: null });
    }

    var rec = body.record || body;
    if (!rec.id) return jsonOut_({ ok: false, message: 'ID entri wajib ada.' });

    var rowVals = [
      rec.id, rec.date || '', rec.shift || '', rec.patientMrn || '', rec.patientBed || '',
      rec.nurseName || '', 'Ruang Kakap', rec.sdkiCode || '', rec.sdkiDiagnosis || '',
      rec.sikiIntervention || '', rec.slkiOutcome || '', rec.actionCategory || 'Mandiri',
      rec.notes || '', Boolean(rec.verifiedByHeadNurse), rec.verifiedAt || '',
      rec.verifiedBy || '', new Date().toISOString()
    ];

    for (var j = 1; j < rows.length; j++) {
      if (String(rows[j][0]) === String(rec.id)) {
        sh.getRange(j + 1, 1, 1, rowVals.length).setValues([rowVals]);
        return jsonOut_({ ok: true, updated: rec.id });
      }
    }
    sh.appendRow(rowVals);
    return jsonOut_({ ok: true, created: rec.id });
  } catch (err) {
    return jsonOut_({ ok: false, message: err.message });
  }
}

