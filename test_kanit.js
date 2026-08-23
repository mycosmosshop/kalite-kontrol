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

// ── Sayfa sozdizimi + FR91 butunlugu ────────────────────────────────────
// NEDEN: FR91 sabitine bir adim eklerken "\n" kacisi GERCEK SATIR SONUNA
// donustu; JS dizesi ortadan kirildi ve modul hic acilmadi
// ("Uncaught SyntaxError: Invalid or unexpected token", satir 131).
// Sozdizimi hatasi sessizdir — ancak tarayicida fark edilir. Artik burada
// yakalanir.
const betik = (s.match(/<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/g) || [])
  .map(b => b.replace(/^<script[^>]*>/, '').replace(/<\/script>$/, ''))
  .join('\n');
try {
  new Function(betik);
} catch (e) {
  console.error('  HATA apqp.html icindeki betik AYRISTIRILAMIYOR: ' + e.message);
  process.exit(1);
}
console.log('  OK   apqp.html betigi ayristiriliyor');

const fr91Ham = blok(s, 'const FR91 = ', '];').replace(/^const FR91 = /, '').replace(/;$/, '');
let FR91;
try {
  FR91 = JSON.parse(fr91Ham);
} catch (e) {
  console.error('  HATA FR91 gecerli JSON degil: ' + e.message);
  process.exit(1);
}
const adimSayisi = FR91.reduce((t, b) => t + b.adimlar.length, 0);
if (FR91.length !== 7 || adimSayisi !== 77) {
  console.error('  HATA FR91 beklenen 7 bolum / 77 adim degil: '
    + FR91.length + ' / ' + adimSayisi);
  process.exit(1);
}
console.log('  OK   FR91 gecerli JSON — ' + FR91.length + ' bolum / ' + adimSayisi + ' adim');
console.log('sayfa butunlugu: TAMAM');

// ── Belge -> adim (ters yon) ────────────────────────────────────────────
// NEDEN: uc belge (D/TLD oz denetimi, TL 1010 yanmazlik, ISO 845 yogunluk)
// HICBIR adima baglanmiyordu — uretiliyor ama modulde gorunmuyorlardi.
// Ayrica FR243 BES adima birden dusuyordu: DOSYA_ANAHTAR'daki "fr ?24"
// deseni "FR243"un icine takiliyor (PPA/PPAP ile ayni tipte hata).
const FR91_LISTE = JSON.parse(blok(s, 'const FR91 = ', '];')
  .replace(/^const FR91 = /, '').replace(/;$/, ''));

function adimlariBul(dosyaAdi) {
  const bulunan = [];
  FR91_LISTE.forEach(b => b.adimlar.forEach(a => {
    if (esle(a.form, [{ ad: dosyaAdi, yol: dosyaAdi }]).length) bulunan.push(a.no);
  }));
  return bulunan;
}

// [dosya, baglanmasi BEKLENEN adimlar]
const BELGE_ADIM = [
  ['Run @ Rate 700.0.454.xlsm', ['5.12']],
  ['Sanifoam_D_TLD_audit_VW 700.0.454.xlsm', ['6.17']],
  ['FR90 EK1 QTR Kalite Teknik Gereklilik 700.0.454.xlsx', ['2.9']],
  ['FR243 Proje Tanıtım Formu 700.0.454.docx', ['2.11']],
  ['FR215 İletişim Matrisi 700.0.454.xlsx', ['2.11']],
];

let hata3 = 0;
for (const [dosya, bekle] of BELGE_ADIM) {
  const bulunan = adimlariBul(dosya);
  const ok = JSON.stringify(bulunan.sort()) === JSON.stringify([...bekle].sort());
  if (!ok) hata3++;
  console.log((ok ? '  OK   ' : '  HATA ') + dosya.slice(0, 44).padEnd(46)
    + '-> ' + (bulunan.join(', ') || 'HICBIR ADIM'));
  if (!ok) console.log('         beklenen: ' + bekle.join(', '));
}
// Test raporlari birden fazla adima kanittir; en az bir malzeme/performans
// adimina baglanmalari YETER.
for (const dosya of ['Flammability Test Report VW 700.0.454.xlsx',
  'ISO 845 Density&Weight Test Report 700.0.454.xlsx']) {
  const bulunan = adimlariBul(dosya);
  const ok = bulunan.includes('6.14') || bulunan.includes('6.15');
  if (!ok) hata3++;
  console.log((ok ? '  OK   ' : '  HATA ') + dosya.slice(0, 44).padEnd(46)
    + '-> ' + (bulunan.join(', ') || 'HICBIR ADIM'));
}
if (hata3) { console.error('\nBASARISIZ: ' + hata3 + ' belge'); process.exit(1); }
console.log('belge-adim baglama: TAMAM');
