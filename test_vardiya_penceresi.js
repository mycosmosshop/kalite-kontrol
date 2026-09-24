// Otomatik kontrol üretimi — vardiya penceresi ve kayıt düzenleme (kontrol saati / vardiya).
//   node test_vardiya_penceresi.js
// 1) runBulkAuto'daki pencere bloğu: tek vardiya → kontroller 08:00–18:00, gece → 20:00–08:00
// 2) Kayıt düzenleme modalında saat/vardiya alanı ARTIK her aşamada (yalnız giriş'te değil)
// 3) Sayfanın satır içi betiği sözdizimi hatasız ayrışıyor
const fs = require('fs'), assert = require('assert');
const html = fs.readFileSync(__dirname + '/kalite_kontrol.html', 'utf8');

// --- 1) pencere bloğunu kaynaktan al, sahte start/end ile çalıştır
const bas = html.indexOf('// VARDİYA PENCERESİ:');
const son = html.indexOf('// seri başı / giriş kontrolü üretim başından', bas);
assert(bas > 0 && son > bas, 'vardiya penceresi bloğu bulunamadı');
const blok = html.slice(bas, son);
function pencere(shiftMode, startIso, endIso, durMin) {
  let start = new Date(startIso), end = endIso ? new Date(endIso) : null;
  return new Function('shiftMode', 'start', 'end', 'durMin', blok + '\nreturn {start,end,durMin};')(shiftMode, start, end, durMin);
}
const hh = d => d.getHours() + d.getMinutes() / 60;

// Üretim 17:35–17:47 (kullanıcının ekranındaki vaka), tek vardiya → 17:35–17:47 zaten içerde, değişmez
let r = pencere('1', '2026-09-24T17:35:00', '2026-09-24T17:47:00', 12);
assert.strictEqual(hh(r.start), 17 + 35 / 60); assert.strictEqual(hh(r.end), 17 + 47 / 60);

// Üretim 20:36–23:10 (gece), tek vardiya → 18:00'e kırpılır; en az 6 dk pencere → 17:54–18:00
r = pencere('1', '2026-09-24T20:36:00', '2026-09-24T23:10:00', 154);
assert(hh(r.start) >= 8 && hh(r.end) <= 18, 'tek vardiya 08–18 dışına taştı: ' + r.start + ' ' + r.end);
assert(r.end > r.start && r.durMin >= 6, 'pencere en az 6 dk olmalı');

// Üretim 06:00–12:00, tek vardiya → 08:00–12:00
r = pencere('1', '2026-09-24T06:00:00', '2026-09-24T12:00:00', 360);
assert.strictEqual(hh(r.start), 8); assert.strictEqual(hh(r.end), 12); assert.strictEqual(r.durMin, 240);

// Gece vardiyası seçimi: 14:00–16:00 üretim → 20:00'den başlar
r = pencere('2', '2026-09-24T14:00:00', '2026-09-24T16:00:00', 120);
assert.strictEqual(hh(r.start), 20, 'gece: 20:00’den önce olmaz');

// Boş seçim: dokunulmaz
r = pencere('', '2026-09-24T20:36:00', '2026-09-24T23:10:00', 154);
assert.strictEqual(hh(r.start), 20 + 36 / 60);

// shiftForTime ile tutarlılık: tek vardiya penceresindeki her saat → vardiya 1
const sft = new Function(html.slice(html.indexOf('function shiftForTime('), html.indexOf('}', html.indexOf('function shiftForTime(')) + 1) + '\nreturn shiftForTime;')();
assert.strictEqual(sft(new Date('2026-09-24T08:00:00')), 1); assert.strictEqual(sft(new Date('2026-09-24T17:59:00')), 1);

// --- 2) düzenleme modalı: alan her aşamada + vardiya seçici + saveEdit vardiyayı yazıyor
assert(!/if\(r\.stage==='giris' && canEdit\)\{\s*m\.append\(el\('div',\{class:'field'/.test(html), 'saat alanı hâlâ yalnız giriş aşamasında');
assert(html.includes("id:'er_shift'") && html.includes("if(vs && vs.value) patch.shift=Number(vs.value)"), 'vardiya seçici / kaydı yok');
assert(html.includes("runBulkAuto(scope,plan,cyc,regenCb.checked,fillEmptyCb.checked,status,go,who,allOpsCb.checked,opMap,virtCb.checked,shiftSel.value)"), 'shiftSel runBulkAuto’ya geçmiyor');

// --- 3) satır içi betikler ayrışıyor
[...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].forEach((m, i) => { try { new Function(m[1]); } catch (e) { assert.fail('betik ' + i + ' sözdizimi: ' + e.message); } });
console.log('✔ vardiya penceresi + kontrol saati düzenleme: tüm kontroller geçti');
