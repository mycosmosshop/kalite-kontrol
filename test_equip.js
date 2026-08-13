// Ekipman adı eşleştirmesi: LeanSys'te elle yazılan alanlardaki TEK harf hatası
// (makine kartı "BLS BSL204" ↔ kontrol planı "BLS BLS204", ikisi de 910.5.003)
// aynı makineyi "eşleşmiyor" göstermemeli; farklı makineler de eşleşmemeli.
//   çalıştır:  node test_equip.js
const fs = require('fs'), assert = require('assert');
const html = fs.readFileSync(__dirname + '/kalite_kontrol.html', 'utf8');

function al(ad) {
  const bas = html.indexOf('function ' + ad + '(');
  assert(bas > 0, ad + ' bulunamadı');
  const son = html.indexOf('\n}', bas);
  return html.slice(bas, son + 2);
}

const deTr = s => String(s || '').toLowerCase()
  .replace(/ı/g, 'i').replace(/ş/g, 's').replace(/ğ/g, 'g')
  .replace(/ü/g, 'u').replace(/ö/g, 'o').replace(/ç/g, 'c').replace(/İ/g, 'i');
const _kkWords = x => [...new Set(deTr(String(x || '')).split(/[^a-z0-9]+/).filter(w => w.length >= 4))];

const { _tokenYakin, equipScore } = new Function(
  'deTr', '_kkWords',
  al('_tokenYakin') + '\n' + al('equipScore') + '\nreturn {_tokenYakin, equipScore};'
)(deTr, _kkWords);

// --- token seviyesi ---
assert.strictEqual(_tokenYakin('bsl20', 'bls20'), true,  'bitişik harf yer değiştirmesi tolere edilmeli');
assert.strictEqual(_tokenYakin('kesim', 'kesin'), true,  'tek harf farkı tolere edilmeli');
assert.strictEqual(_tokenYakin('kesim', 'kesi'),  true,  'tek harf eksik tolere edilmeli');
assert.strictEqual(_tokenYakin('yatay', 'kesim'), false, 'alakasız token eşleşmemeli');
assert.strictEqual(_tokenYakin('kp11', 'kp12'),   true,  'tek karakter farkı');

// --- GERÇEK VAKA: aynı makine (910.5.003), tek harf hatası ---
const s1 = equipScore('BLS BSL204 YATAY KESIM', 'BLS BLS204 YATAY KESIM MAKINESI');
console.log('BSL204 ↔ BLS204           :', s1.toFixed(2), s1 >= 0.6 ? '✔ eşleşiyor' : '✘ eşleşmiyor');
assert.ok(s1 >= 0.6, 'aynı makine eşleşmeli (tek harf hatası)');

// --- gerçekten farklı makineler eşleşmemeli (regresyon) ---
const s2 = equipScore('VARGEL KESIM MAK 1', 'KP11-KISSCUT');
const s3 = equipScore('ESKISEHIR EL ISCILIGI (ELYAF UCLAMA)', 'AMBALAJLAMA');
const s4 = equipScore('LMN2 RULO DILIMLEME MAKINASI', 'LMN3 SICAK SILINDIR LAMINASYON');
console.log('VARGEL ↔ KP11-KISSCUT     :', s2.toFixed(2), s2 >= 0.6 ? '✘ HATA' : '✔ ayrı');
console.log('EL İŞÇİLİĞİ ↔ AMBALAJLAMA :', s3.toFixed(2), s3 >= 0.6 ? '✘ HATA' : '✔ ayrı');
console.log('LMN2 ↔ LMN3               :', s4.toFixed(2), s4 >= 0.6 ? '✘ HATA' : '✔ ayrı');
assert.ok(s2 < 0.6 && s3 < 0.6 && s4 < 0.6, 'farklı makineler eşleşmemeli');

// --- birebir aynı ad ---
assert.strictEqual(equipScore('PLAKALAMA (ESK)', 'PLAKALAMA (ESK)'), 1);
assert.strictEqual(equipScore('', 'PLAKALAMA'), 0);

console.log('✔ yazım hatası tolere ediliyor, farklı makineler ayrı kalıyor');
