// Adim kanit kurali — apqp.html icindeki gercek fonksiyonlarla sinanir.
//
// NEDEN BU TEST VAR: "gercek kanit" ile "modul baglantisi" ayrimini iki kez
// yanlis yaptik.
//   1) Butun tur:'erp' kanitlari kanit sayilmiyordu; ERP CALISMALARI da 'erp'
//      turunde oldugu icin 14 yeterlilik/MSA calismasi bagli olan adim yine
//      "kanitsiz" gorunup %0 kaliyordu.
//   2) Calismayi "/msa/" ile ayirmak yetmiyordu: modul baglantisinin kendisi
//      de /msa/capability.html altinda. Bu yuzden modul baglantisi calisma
//      sayiliyor, ustelik tazeleme onu calisma sanip SILIYORDU.
// Ayirt edici isaret: calisma adresinde "?id=" vardir.
//
// Calistirmak icin:  node test_kanit.js
const fs = require('fs');

const s = fs.readFileSync(__dirname + '/apqp.html', 'utf8');
const al = (ad, re) => {
  const m = s.match(re);
  if (!m) throw new Error('apqp.html icinde bulunamadi: ' + ad);
  return m[0];
};
const kural = eval([
  al('met', /const met = [^\n]+/),
  al('erpCalismasi', /const erpCalismasi = [\s\S]*?;/),
  al('gercekKanitVar', /function gercekKanitVar\(kanitlar\) \{[\s\S]*?\n\}/),
  'gercekKanitVar',
].join('\n'));

const CALISMA = 'https://mycosmosshop.github.io/msa/cap-results.html?id=91';
const MODUL = 'https://mycosmosshop.github.io/msa/capability.html';

// [aciklama, kanitlar, beyan_bekleniyor]
// beyan = gercek kanit YOK (adim yine %100 kapanir, ama rozetle ayrilir)
const DURUMLAR = [
  ['yalniz modul baglantisi', [{ tur: 'erp', ad: 'Proses Yeterliligi modulu', adres: MODUL }], true],
  ['ERP calismasi (id li)', [{ tur: 'erp', ad: 'Yeterlilik: Terazi Cp/Cpk', adres: CALISMA }], false],
  ['Drive dokumani', [{ tur: 'drive', ad: 'FR24 ...xlsm', yol: 'x' }], false],
  ['LeanSys teknik resim', [{ tur: 'leansys', ad: 'resim', yol: 'y' }], false],
  ['hic kanit yok', [], true],
  ['modul + calisma birlikte', [{ tur: 'erp', ad: 'modul', adres: MODUL },
    { tur: 'erp', ad: 'MSA: ...', adres: CALISMA }], false],
];

let hata = 0;
for (const [ad, kanitlar, beklenen] of DURUMLAR) {
  const beyan = !kural(kanitlar);
  const ok = beyan === beklenen;
  if (!ok) hata++;
  console.log((ok ? '  OK   ' : '  HATA ') + ad.padEnd(26)
    + ' beyan=' + String(beyan).padEnd(5) + ' (beklenen ' + beklenen + ')');
}
if (hata) { console.error('\nBASARISIZ: ' + hata + ' kural'); process.exit(1); }
console.log('\nkanit kurali: TAMAM — hicbir adim %0 kalmaz, kanitsizlar "beyan" isaretli');

// ── Dosya -> adim baglama ───────────────────────────────────────────────
// NEDEN: musteriye giden PPA/PPF KAPAK belgeleri madde 3.10 "Alt Tedarikci
// APQP plani" adimina kanit olarak baglaniyordu. Sebep DOSYA_ANAHTAR'daki
// ciplak "ppa" deseniydi: "Alt Tedarikci PPAP" kelimesinin ICINE takiliyor.
// Kapaklar madde 6.2 "Cover Sheet"e aittir.
function blok(kaynak, bas, bit) {
  const i = kaynak.indexOf(bas);
  if (i < 0) throw new Error('apqp.html icinde bulunamadi: ' + bas);
  const j = kaynak.indexOf(bit, i);
  return kaynak.slice(i, j + bit.length);
}

const esle = eval([
  blok(s, 'const met = ', '\n'),
  blok(s, 'const formKodlari = ', '))];'),
  blok(s, 'const adSade = ', '.trim();'),
  blok(s, 'const DOSYA_ANAHTAR = [', '\n];'),
  blok(s, 'function adimDriveDosyalari', '\n}'),
  'adimDriveDosyalari',
].join('\n'));

const DOSYALAR = [
  'Alt Tedarikçi PPAP 700.0.454 - 981.4.204.xlsx',
  'PPA COVER SHEET LEAR 700.0.454.xlsx',
  'PPF Coversheet 700.0.454.docx',
  'VDA_2_2020_Anlagen_Attachments_2-6_7 MAN 700.0.454.xlsx',
].map(ad => ({ ad, yol: ad }));

// [adim formu, baglanmasi BEKLENEN dosyalar]
const BEKLENEN = [
  ['Alt Tedarikçi PPAP (VDA 2)', ['Alt Tedarikçi PPAP 700.0.454 - 981.4.204.xlsx']],
  ['Cover Sheet (Kapak)', ['PPA COVER SHEET LEAR 700.0.454.xlsx',
    'PPF Coversheet 700.0.454.docx',
    'VDA_2_2020_Anlagen_Attachments_2-6_7 MAN 700.0.454.xlsx']],
];

let hata2 = 0;
for (const [form, bekle] of BEKLENEN) {
  const bulunan = esle(form, DOSYALAR).map(d => d.ad).sort();
  const ok = JSON.stringify(bulunan) === JSON.stringify([...bekle].sort());
  if (!ok) hata2++;
  console.log((ok ? '  OK   ' : '  HATA ') + form.padEnd(28) + ' -> ' + bulunan.length + ' dosya');
  if (!ok) console.log('         beklenen: ' + JSON.stringify(bekle)
    + '\n         bulunan : ' + JSON.stringify(bulunan));
}
if (hata2) { console.error('\nBASARISIZ: ' + hata2 + ' adim eslesmesi'); process.exit(1); }
console.log('dosya-adim baglama: TAMAM — kapaklar 3.10\'a baglanmiyor');
