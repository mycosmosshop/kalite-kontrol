// PFMEA otomatik uretimi: iskelet yapisi + S/O/D kurallari + AP tablosu.
// Kod HTML'den ALINIR (kopya degil), boylece uygulama degisirse test de olcer.
//   calistir:  node test_pfmea_uret.js
const fs = require('fs'), assert = require('assert');
const html = fs.readFileSync(__dirname + '/kalite_kontrol.html', 'utf8');

function al(ad, tip) {
  const bas = (tip === 'const') ? ('const ' + ad + ' =') : ('function ' + ad + '(');
  const i = html.indexOf(bas);
  assert(i > 0, ad + ' bulunamadi');
  const j = (tip === 'const') ? html.indexOf(';', i) + 1 : html.indexOf('\n}', i) + 2;
  return html.slice(i, j);
}
const K = new Function(
  al('AP_MATRIS', 'const') + '\n' + al('apHesapla') + '\n' +
  html.slice(html.indexOf('const _pfSay='), html.indexOf('const _pfKup=') + 80) + '\n' +
  al('pfSiddet') + '\n' + al('pfOlasilik') + '\n' + al('pfTespit') + '\n' +
  al('pfOnleme') + '\n' + al('pfTespitKontrol') + '\n' + al('pfAksiyonlar') + '\n' +
  al('pfmeaIskeletUret') + '\n' +
  'return {AP_MATRIS,apHesapla,pfGirdiMalzemeMi,pfSiddet,pfOlasilik,pfTespit,pfOnleme,pfTespitKontrol,pfAksiyonlar,pfmeaIskeletUret};')();

// ── AP tablosu resmi AIAG-VDA degerleriyle tutmali ──
assert.strictEqual(K.AP_MATRIS.length, 1000, 'AP matrisi 10x10x10 olmali');
[[7,4,5,'M'],[7,3,4,'L'],[7,6,5,'H'],[1,1,1,'L'],[10,10,10,'H'],[10,1,1,'L'],[9,5,5,'H']]
  .forEach(([S,O,D,b]) => assert.strictEqual(K.apHesapla(S,O,D), b, `AP S${S}/O${O}/D${D} = ${b} olmali`));
assert.strictEqual(K.apHesapla(0,0,0), K.apHesapla(1,1,1), 'sinir disi deger 1e kirpilmali');
assert.strictEqual(K.apHesapla(99,99,99), K.apHesapla(10,10,10), 'sinir disi deger 10a kirpilmali');

// ── Girdi hammaddesi ayrimi: kodun ORTA parcasi ──
assert.strictEqual(K.pfGirdiMalzemeMi('909.4.018'), true, '.4. girdi hammaddesi');
assert.strictEqual(K.pfGirdiMalzemeMi('952.10.004'), true, '.10. girdi hammaddesi');
assert.strictEqual(K.pfGirdiMalzemeMi('205.0.214-C'), false, '.0. yari mamul — girdi degil');
assert.strictEqual(K.pfGirdiMalzemeMi('700.0.454'), false, 'urun kodu girdi degil');
assert.strictEqual(K.pfGirdiMalzemeMi(''), false);
assert.strictEqual(K.pfGirdiMalzemeMi(null), false);
assert.strictEqual(K.pfGirdiMalzemeMi('909.5.018'), false, 'listede olmayan orta kod girdi sayilmaz');

// ── Siddet: karakteristik turunden ──
assert.strictEqual(K.pfSiddet({ special_characteristic: '◆' }, false), 8, 'ozel karakteristik yuksek siddet');
assert.strictEqual(K.pfSiddet({ final_control: true }, false), 7, 'son kontrol musteriye son bariyer');
assert.strictEqual(K.pfSiddet({}, true), 5);
assert.strictEqual(K.pfSiddet({}, false), 5);

// ── Olasilik: onleyici kontrolun varligindan ──
assert.strictEqual(K.pfOlasilik({ process_control: 'SPC' }), 3, 'tanimli proses kontrolu olasiligi dusurur');
assert.strictEqual(K.pfOlasilik({}), 5, 'proses kontrolu yoksa daha yuksek');
assert.strictEqual(K.pfOlasilik({ process_control: 'SPC', periodic_days: 30 }), 4, 'yalniz periyodik bakiliyorsa artar');

// ── Tespit: yontem + siklik ──
assert.strictEqual(K.pfTespit({ method: '%100 otomatik kamera' }), 2, 'otomatik %100 en iyi tespit');
assert.strictEqual(K.pfTespit({ method: 'Kumpas' }), 4, 'olcum aleti orta');
assert.strictEqual(K.pfTespit({ method: 'Gözle' }), 7, 'gorsel kontrol zayif');
assert.strictEqual(K.pfTespit({}), 9, 'yontem tanimsizsa tespit guvencesi yok');
assert.strictEqual(K.pfTespit({ method: 'Kumpas', sampling_frequency: 'Her parça' }), 3, 'her parca kontrolu iyilestirir');
assert.strictEqual(K.pfTespit({ method: 'Kumpas', sampling_frequency: 'Vardiyada 1' }), 5, 'seyrek ornekleme kotulestirir');
assert.ok(K.pfTespit({ method: '%100 otomatik', sampling_frequency: 'Her parça' }) >= 1, 'alt sinir 1');

// ── Mevcut kontroller kontrol planindan gelmeli ──
assert.strictEqual(K.pfOnleme({ process_control: 'Proses parametre takibi' }), 'Proses parametre takibi');
assert.ok(K.pfOnleme({}).includes('FR17'), 'onleme yoksa egitim/talimat onerilir');
assert.strictEqual(K.pfTespitKontrol({ method: 'Kumpas', sample_size: '5', sampling_frequency: 'Her lot' }),
  'Kumpas · 5 adet · Her lot');
assert.ok(K.pfTespitKontrol({}).includes('yok'), 'yontem yoksa acikca yazilmali');

// ── Aksiyonlar AP seviyesine gore ──
assert.ok(K.pfAksiyonlar('H', {}).length >= 3, 'yuksek AP daha fazla aksiyon');
assert.ok(JSON.stringify(K.pfAksiyonlar('H', {})).includes('Poka-yoke'));
assert.ok(JSON.stringify(K.pfAksiyonlar('M', {})).includes('FR17'));
assert.strictEqual(K.pfAksiyonlar('L', {}).length, 1);

// ── Iskelet: gercek veriye benzer girdiyle ──
const fd = K.pfmeaIskeletUret(
  { kod: '205.0.214-C', ad: 'SES VE ISI YALITIM SÜNGERİ' },
  [{ tuketim_kodu: '909.4.018', tuketim_adi: 'BASOTECT G PLUS' },
   { tuketim_kodu: '952.10.004', tuketim_adi: 'BANT' },
   { tuketim_kodu: '205.0.300',  tuketim_adi: 'YARI MAMUL SÜNGER' }],
  [{ op_no: 2, makine_adi: 'PAKETLEME' }, { op_no: 1, makine_adi: 'SU JETİ' }],
  [{ op_no: 1, measure_name: 'Kesim ölçüsü', target: '195', unit: 'mm', method: 'Kumpas',
     sample_size: '5', sampling_frequency: 'Her lot', process_control: 'Proses talimatı',
     special_characteristic: '◆' },
   { op_no: 2, measure_name: 'Etiket doğruluğu', nitel_hedef: 'Uygun', method: 'Gözle' },
   { giris_kalite: true, measure_name: 'Yoğunluk', target: '9', unit: 'kg/m³', method: 'Terazi' }],
  'kontrol planı PL41 Rev.02',
  // Her hammaddenin KENDI girdi kontrol plani
  { '909.4.018': [{ measure_name: 'Yoğunluk', target: '9', unit: 'kg/m³', method: 'Terazi' }],
    '952.10.004': [{ measure_name: 'Yapışma', nitel_hedef: 'Uygun', method: 'Gözle' }] });

assert.strictEqual(Object.keys(fd.processItems).length, 1);
assert.strictEqual(fd.processItemIds.length, 1);
// 1 hammadde (girdi) + 2 rota adimi
assert.strictEqual(Object.keys(fd.processSteps).length, 4, '2 girdi hammaddesi + 2 operasyon adimi (yari mamul elenir)');
const adimlar = Object.values(fd.processSteps);
assert.strictEqual(adimlar[0].operationNumber, '0', 'girdi kalite kontrol Op 0');
assert.deepStrictEqual(adimlar.slice(2).map(x => x.operationNumber), ['1', '2'], 'operasyonlar op no sirasinda');
assert.ok(!JSON.stringify(fd.processSteps).includes('205.0.300'), 'yari mamul icin girdi kontrol adimi acilmamali');
assert.strictEqual(adimlar[2].machineDeviceSource, 'SU JETİ');

// Her karakteristik icin fonksiyon + hata turu + etki uretilmeli
assert.strictEqual(Object.keys(fd.processStepFunctions).length, 4, '2 uretim + 2 girdi karakteristigi');
assert.strictEqual(Object.keys(fd.failureModes).length, 4);
assert.strictEqual(Object.keys(fd.failureEffects).length, 4);

// Ozel karakteristikli madde: S=8, spec dolu, siniflandirma isaretli
const f1 = Object.values(fd.processStepFunctions).find(f => f.productCharacteristic === 'Kesim ölçüsü');
assert.strictEqual(f1.productSpecificationTolerance, '195 mm', 'hedef + birim spec olarak yazilmali');
assert.strictEqual(f1.classificationSpecialCharacteristic, true);
assert.strictEqual(f1.evaluationMeasurementTechnique, 'Kumpas');
const m1 = fd.failureModes[f1.failureModeIds[0]];
assert.ok(m1.description.includes('Kesim ölçüsü'), 'hata turu karakteristikten turetilmeli');
assert.strictEqual(fd.failureEffects[m1.effectIds[0]].severity, 8);

// Nedenler: S/O/D + AP + aksiyon + kaynak notu
assert.strictEqual(m1.causeIds.length, 3, 'uretim adiminda 3 neden');
const c1 = fd.failureCauses[m1.causeIds[0]];
assert.strictEqual(c1.occurrence, 3);                     // proses kontrolu var
assert.strictEqual(c1.detection, 5);                      // Kumpas(4) + seyrek ornekleme? Her lot -> +1
assert.strictEqual(c1.actionPriority, K.apHesapla(8, c1.occurrence, c1.detection));
assert.ok(c1.actions.length >= 1, 'aksiyon uretilmeli');
assert.ok(c1.remarks.includes('OTOMATİK ÖNERİ'), 'kaydin otomatik oldugu yazmali');
assert.ok(c1.remarks.includes('PL41'), 'kaynak kontrol plani remarks icinde izlenebilir olmali');
assert.strictEqual(c1.preventionControl, 'Proses talimatı');
assert.ok(c1.detectionControl.includes('Kumpas'));

// Girdi adiminda nedenler tedarikci/personel odakli
const gf = Object.values(fd.processStepFunctions).find(f => f.productCharacteristic === 'Yoğunluk');
const gm = fd.failureModes[gf.failureModeIds[0]];
assert.strictEqual(gm.causeIds.length, 2, 'girdi adiminda 2 neden');
assert.ok(fd.failureCauses[gm.causeIds[0]].description.includes('Tedarikçi'));

// Girdi karakteristigi YALNIZ kendi malzemesinin adiminda olmali
const yogAdim = Object.values(fd.processSteps).find(x=> x.name.includes('909.4.018'));
const bantAdim = Object.values(fd.processSteps).find(x=> x.name.includes('952.10.004'));
const adAl = (st)=> st.functionIds.map(i=> fd.processStepFunctions[i].productCharacteristic);
assert.deepStrictEqual(adAl(yogAdim), ['Yoğunluk'], 'BASOTECT adiminda yalniz kendi karakteristigi');
assert.deepStrictEqual(adAl(bantAdim), ['Yapışma'], 'BANT adiminda yalniz kendi karakteristigi');

// Yontemsiz madde: D=9 -> daha yuksek AP
const ef = Object.values(fd.processStepFunctions).find(f => f.productCharacteristic === 'Etiket doğruluğu');
const em = fd.failureModes[ef.failureModeIds[0]];
assert.strictEqual(fd.failureCauses[em.causeIds[0]].detection, 7, 'gozle kontrol D=7');

console.log('OK PFMEA uretimi: AP tablosu resmi degerlerle tutuyor; S/O/D kurallari, mevcut kontroller,');
console.log('   aksiyonlar ve iskelet yapisi (girdi + operasyon adimlari, karakteristik->hata->neden) dogru.');
