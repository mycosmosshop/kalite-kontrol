// Tutarlilik denetimi: kontrol plani <-> operasyon karti <-> PFMEA karsilastirmasi.
// Senaryolar bu oturumda ELLE bulunan GERCEK vakalardan alindi:
//  - kontrol planinda olup rotada olmayan op (SETLEME/op7)
//  - ekipman adinda tek harf yazim hatasi (BLS BSL204 / BLS BLS204) -> SORUN DEGIL
//  - gercekten farkli makine -> SORUN
//   calistir:  node test_tutarlilik.js
const fs = require('fs'), assert = require('assert');
const html = fs.readFileSync(__dirname + '/kalite_kontrol.html', 'utf8');

function al(ad) {
  const i = html.indexOf('function ' + ad + '(');
  assert(i > 0, ad + ' bulunamadi');
  const j = html.indexOf('\n}', i);
  return html.slice(i, j + 2);
}
// Gercek kod HTML'den alinir (kopya degil): yazim-hatasi toleransli eslestirici dahil
const { tutarlilikKarsilastir, tdPfmeaOzet } = new Function(
  al('deTr') + '\n' + 'const _kkWords = x => [...new Set(deTr(String(x||"")).split(/[^a-z0-9]+/).filter(w=>w.length>=4))];\n' +
  al('_tokenYakin') + '\n' + al('equipScore') + '\n' +
  al('tdNorm') + '\n' + al('tutarlilikKarsilastir') + '\n' + al('tdPfmeaOzet') + '\n' +
  'return {tutarlilikKarsilastir, tdPfmeaOzet};')();

const rota = (ops) => ops.map(o => ({ header_id: 1, op_no: o.op, makine_kodu: o.mc || '', makine_adi: o.mn, rota_adi: 'Rota-1', varsayilan: true }));
const plan = (ops) => ops.map(o => ({ op_no: o.op, olculecek: o.ol || 'ölçü', uretim_ekipman: o.eq }));
const tur = (b) => b.map(x => x.tur);

// --- 1) Her sey tutarli: bulgu YOK ---
let b = tutarlilikKarsilastir('X',
  plan([{ op: 1, eq: 'VARGEL KESIM MAK 1' }, { op: 2, eq: 'PLAKALAMA (ESK)' }]),
  rota([{ op: 1, mn: 'VARGEL KESIM MAK 1' }, { op: 2, mn: 'PLAKALAMA (ESK)' }]), null);
assert.deepStrictEqual(b, [], 'tutarli veride bulgu olmamali, cikan: ' + JSON.stringify(b));

// --- 2) GERCEK VAKA: tek harf yazim hatasi ayni makinedir -> bulgu YOK ---
b = tutarlilikKarsilastir('X',
  plan([{ op: 1, eq: 'BLS BLS204 YATAY KESIM MAKINESI' }]),
  rota([{ op: 1, mn: 'BLS BSL204 YATAY KESIM' }]), null);
assert.deepStrictEqual(b, [], 'tek harf hatasi "uyusmuyor" sayilmamali, cikan: ' + JSON.stringify(b));

// --- 3) Gercekten farkli makine -> bulgu VAR ---
b = tutarlilikKarsilastir('X',
  plan([{ op: 1, eq: 'VARGEL KESIM MAK 1' }]),
  rota([{ op: 1, mn: 'KP11-KISSCUT' }]), null);
assert.deepStrictEqual(tur(b), ['Ekipman uyuşmuyor'], 'farkli makine yakalanmali');

// --- 4) GERCEK VAKA: planda olan op rotada yok (SETLEME) ---
b = tutarlilikKarsilastir('X',
  plan([{ op: 1, eq: 'A' }, { op: 7, eq: 'SETLEME (ANK)' }]),
  rota([{ op: 1, mn: 'A' }]), null);
assert.deepStrictEqual(tur(b), ['Rotada olmayan op']);
assert.ok(b[0].detay.includes('Op 7'), 'detayda op numarasi olmali');

// --- 5) Rotada olan op planda yok ---
b = tutarlilikKarsilastir('X', plan([{ op: 1, eq: 'A' }]),
  rota([{ op: 1, mn: 'A' }, { op: 2, mn: 'AMBALAJLAMA' }]), null);
assert.deepStrictEqual(tur(b), ['Planda olmayan op']);
assert.ok(b[0].detay.includes('AMBALAJLAMA'), 'detayda makine adi olmali');

// --- 6) Tek yonlu eksikler ---
assert.deepStrictEqual(tur(tutarlilikKarsilastir('X', plan([{ op: 1, eq: 'A' }]), [], null)), ['Operasyon kartı yok']);
assert.deepStrictEqual(tur(tutarlilikKarsilastir('X', [], rota([{ op: 1, mn: 'A' }]), null)), ['Kontrol planı yok']);

// --- 7) Varsayilan rota tercih edilir (ikinci rota yanlis alarm uretmemeli) ---
const ikiRota = [
  { header_id: 1, op_no: 1, makine_adi: 'A', rota_adi: 'Rota-1', varsayilan: false },
  { header_id: 2, op_no: 1, makine_adi: 'B', rota_adi: 'Rota-2', varsayilan: true }];
assert.deepStrictEqual(tur(tutarlilikKarsilastir('X', plan([{ op: 1, eq: 'B' }]), ikiRota, null)), [],
  'varsayilan rota (B) ile karsilastirilmali');

// --- 8) PFMEA ayagi ---
b = tutarlilikKarsilastir('X', plan([{ op: 1, eq: 'A' }, { op: 2, eq: 'B' }]),
  rota([{ op: 1, mn: 'A' }, { op: 2, mn: 'B' }]), { ops: [1] });
assert.deepStrictEqual(tur(b), ['PFMEA’da olmayan op']);
b = tutarlilikKarsilastir('X', plan([{ op: 1, eq: 'A' }]), rota([{ op: 1, mn: 'A' }]), { ops: [1, 9] });
assert.deepStrictEqual(tur(b), ['Planda olmayan PFMEA op']);

// --- 9) PFMEA JSON ozeti: ic ice yapidan op numaralarini toplar ---
const oz = tdPfmeaOzet({ partNumber: '36.72010-6345', structure: { items: [{ operationNumber: '10' }, { operationNumber: 20, alt: [{ operationNumber: '30' }] }] } });
assert.strictEqual(oz.kod, '36.72010-6345');
assert.deepStrictEqual(oz.ops, [10, 20, 30], 'ic ice op numaralari toplanmali');
assert.deepStrictEqual(tdPfmeaOzet({ partNumber: 'A', x: { operationNumber: 'yok' } }).ops, [], 'sayi olmayan op atlanmali');

console.log('OK tutarlilik denetimi: 9 senaryo — op farklari, yazim hatasi toleransi, varsayilan rota ve PFMEA ayagi dogru');
