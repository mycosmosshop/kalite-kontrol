// Kalite Kayıtları (salt-okunur LeanSys görünümü) — kalite_kayitlari.html
//   node test_kalite_kayitlari.js
// 1) Sayfa Supabase'e YALNIZ select atar (insert/update/delete/upsert/rpc yok) — LeanSys/ERP'ye yazma yok
// 2) satir(): giriş ve seri başı kayıtları LeanSys sütunlarına doğru eşlenir (gerçek fonksiyon gövdesi)
// 3) Betik sözdizimi hatasız ayrışır; portal kartı en başta
const fs = require('fs'), assert = require('assert');
const html = fs.readFileSync(__dirname + '/kalite_kayitlari.html', 'utf8');
const js = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');

// 1) salt okunur
assert(!/\.(insert|update|delete|upsert|rpc)\s*\(/.test(js), 'sayfa Supabase\'e yazıyor!');
assert((js.match(/\.select\(/g) || []).length >= 3, 'select çağrıları yok');
assert(js.includes("from('control_records')") && js.includes("from('productions')") && js.includes("from('operasyon_kartlari')"));

// 3) sözdizimi
new Function(js);

// 2) satir() + bolum() — gerçek gövdeyi çek, sahte PROD/GROUP ile çalıştır
function cek(ad) { const i = js.indexOf('function ' + ad + '('); assert(i > 0, ad + ' yok'); let d = 0, b = false, k = i; for (; k < js.length; k++) { if (js[k] === '{') { d++; b = true; } else if (js[k] === '}') { d--; if (b && d === 0) { k++; break; } } } return js.slice(i, k); }
const helpers = js.slice(js.indexOf('const fmtDate ='), js.indexOf('let GROUP = {}'))     // fmt* + deTr + SUBE_ETIKET
  .replace(/^\s*\/\/.*$/gm, '');
const F = new Function('stage', 'PROD', 'GROUP',
  helpers + '\n' + cek('bolum') + '\n' + cek('satir') + '\nreturn {satir,bolum};');

// start_time Supabase'ten timestamptz olarak "+00:00" ekiyle gelir (LeanSys duvar saati UTC etiketli) — fmtTimeWall UTC gösterir
const prod = { id: 7, customer: 'ARÇELİK A.S ESKISEHIR', stock_code: '350.0.219', stock_name: '4081860200 - SÜNGER', machine_code: '910.5.001', machine_name: 'VARGEL KESIM MAK 3', start_time: '2026-09-24T03:08:00+00:00', end_time: '2026-09-24T03:08:00+00:00', quantity: 2232, unit: 'Ad', shift: 1, work_order: 'İE-1' };
const rec = { id: 1, production_id: 7, stage: 'seri_basi', checked_at: '2026-09-24T03:12:00+03:00', shift: 1, overall_result: 'OK', operator: 'Eskişehir Kalite', vals: [] };
let s = F('seri_basi', { 7: prod }, { '910.5.001': 'ESKISEHIR SUBESI' }).satir(rec);
assert.strictEqual(s.tarih, '24.09.2026'); assert.strictEqual(s.cari, 'ARÇELİK A.S ESKISEHIR');
assert.strictEqual(s.bolum, 'ESKISEHIR SUBESI', 'bölüm operasyon kartı grubundan');
assert.strictEqual(s.bas, '03:08', 'başlama duvar saati (UTC olarak okunur, +3 kaymaz)');
assert.strictEqual(s.miktar, '2232'); assert.strictEqual(s.birim, 'Ad'); assert.strictEqual(s.ok, true);
// grup haritasında yoksa makine adından şube
s = F('seri_basi', { 7: { ...prod, machine_code: 'X', machine_name: 'ESKISEHIR AMBALAJLAMA ISÇILIGI' } }, {}).satir(rec);
assert.strictEqual(s.bolum, 'ESKISEHIR SUBESI', 'yedek etiket operasyon kartı grup adıyla aynı yazımda');
// giriş kalite: tedarikçi / irsaliye / gelen miktar kayıttan
const g = { id: 2, production_id: null, stage: 'giris', checked_at: '2026-09-11T09:15:00', overall_result: 'RET', giris_cari: 'AVS AMBALAJ', giris_irsaliye: 'AIR26AV / 898', giris_miktar: 3770, giris_birim: 'm2', stock_code: '952.4.010', operator: 'Volkan' };
s = F('giris', {}, {}).satir(g);
assert.strictEqual(s.cari, 'AVS AMBALAJ'); assert.strictEqual(s.irsaliye, 'AIR26AV / 898'); assert.strictEqual(s.miktar, '3770'); assert.strictEqual(s.ok, false);

// portal kartı: DEFAULT_MODULES'un İLK öğesi
const portal = fs.readFileSync('D:/Yazılım/erp-portal/erp_portal.html', 'utf8');
const i0 = portal.indexOf('const DEFAULT_MODULES = ['), i1 = portal.indexOf("id:'kalitekayitlari'"), i2 = portal.indexOf("id:'bakim'");
assert(i0 > 0 && i1 > i0 && i1 < i2, 'Kalite Kayıtları kartı listenin başında değil');
assert(portal.includes("kaynak:'https://mycosmosshop.github.io/kalite-kontrol/kalite_kayitlari.html'"));
console.log('✔ kalite_kayitlari: salt okunur, sütun eşlemesi doğru, portal kartı ilk sırada');
