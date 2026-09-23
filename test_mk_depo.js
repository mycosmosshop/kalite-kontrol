// Mal Kabul depo filtresi: depo listesi TÜM tablodan sayfalı okunmalı —
// tek sorgu sunucunun 1000 satır sınırına takılıp seyrek depoları düşürüyordu.
//   çalıştır:  node test_mk_depo.js
const fs = require('fs'), assert = require('assert');
const html = fs.readFileSync(__dirname + '/kalite_kontrol.html', 'utf8');

function al(ad) {
  const bas = html.indexOf('async function ' + ad + '(');
  assert(bas > 0, ad + ' bulunamadı');
  return html.slice(bas, html.indexOf('\n}', bas) + 2);
}

// Sahte Supabase: 2500 satır, "ADANA HAMMADDE DEPO" yalnız 2. sayfadan sonra
const TABLO = Array.from({ length: 2500 }, (_, i) => ({
  rec_id: i, depo: i === 2100 ? 'ADANA HAMMADDE DEPO' : i === 5 ? null : (i % 2 ? 'ÇERKEZKÖY HAMMADDE DEPO' : 'ANKARA HAMMADDE DEPO') }));
let sorgu = 0;
const sb = { from: () => {
  const q = { select: () => q, not: () => q, order: () => q,
    range: (a, b) => { sorgu++; return Promise.resolve({ data: TABLO.filter(r => r.depo != null).slice(a, b + 1), error: null }); } };
  return q; } };

const { mkDepoListesi, sifirla } = new Function('sb',
  'let _mkDepolar=null;\n' + al('mkDepoListesi') + '\nreturn {mkDepoListesi, sifirla:()=>{_mkDepolar=null;}};')(sb);

(async () => {
  const d = await mkDepoListesi();
  console.log('depolar:', d.join(' · '), '| sorgu:', sorgu);
  assert.deepStrictEqual(d, ['ADANA HAMMADDE DEPO', 'ANKARA HAMMADDE DEPO', 'ÇERKEZKÖY HAMMADDE DEPO'],
    '1000. satırdan sonraki seyrek depo da listede, Türkçe sıralı, boş depo yok');
  assert.strictEqual(sorgu, 3, '2499 satır → 3 sayfa');
  await mkDepoListesi();
  assert.strictEqual(sorgu, 3, 'ikinci çağrı önbellekten (tekrar sorgu yok)');

  // Filtre sorguya ve izlenebilirlik satırına bağlı mı (kaynak metin kontrolü)
  const r = html.slice(html.indexOf('async function renderMalKabul('), html.indexOf('\n}', html.indexOf('async function renderMalKabul(')));
  assert.ok(r.includes("if(fDepo.value) q=q.eq('depo',fDepo.value);"), 'depo sorguya eklenmeli');
  assert.ok(r.includes('hitDepo') && r.includes('&&hitDepo&&'), 'izlenebilirlik satırı da depo filtresine uymalı');
  assert.ok(r.includes("fDepo.value='';load();}},'Temizle')"), 'Temizle depoyu sıfırlamalı');

  // Sayfanın satır içi betikleri sözdizimi hatasız ayrışıyor mu
  const betikler = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  betikler.forEach((b, i) => { try { new Function(b); } catch (e) { assert.fail('betik ' + i + ' sözdizimi: ' + e.message); } });
  console.log('✔ tüm kontroller geçti (' + betikler.length + ' betik ayrıştı)');
})().catch(e => { console.error('✘', e.message); process.exit(1); });
