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
