// Çevrim süresi = LeanSys op kartı Std.Zaman (dk) × 60. Aynı makine rotada birden çok
// adımdaysa EN KÜÇÜK op_no'nunki alınır (büyük op_no'lular Kapasite=1 olan dolgu satırları).
//   çalıştır:  node test_cyc.js
const assert=require('assert');

// operasyon_kartlari'ndan okunan gerçek satırlar (351.0.022 / 351.0.227, 2026-08-04)
const kartlar=[
  {stok_kodu:'351.0.022',op_no:1,makine_kodu:'910.5.608',std_zaman:0.166},
  {stok_kodu:'351.0.022',op_no:2,makine_kodu:'910.5.053',std_zaman:0.25},
  {stok_kodu:'351.0.022',op_no:3,makine_kodu:'910.5.159',std_zaman:0.18},
  {stok_kodu:'351.0.022',op_no:4,makine_kodu:'910.5.159',std_zaman:1},      // dolgu satırı
  {stok_kodu:'351.0.227',op_no:3,makine_kodu:'910.5.159',std_zaman:1},      // sıra bozuk gelse de
  {stok_kodu:'351.0.227',op_no:2,makine_kodu:'910.5.159',std_zaman:0.18},   //   küçük op kazanmalı
];
const map={};
for(const o of [...kartlar].sort((a,b)=>a.op_no-b.op_no)){       // uygulama .order('op_no') ile okur
  const v=Number(o.std_zaman); if(!(v>0)||!o.makine_kodu) continue;
  const k=o.stok_kodu+'|'+o.makine_kodu; if(map[k]==null) map[k]=v;
}
const sn=k=>Math.round(map[k]*60*1000)/1000;

assert.strictEqual(sn('351.0.022|910.5.608'),9.96);    // PLAKALAMA
assert.strictEqual(sn('351.0.022|910.5.053'),15);      // KP5
assert.strictEqual(sn('351.0.022|910.5.159'),10.8);    // EL İŞÇİLİĞİ — dolgu (1 dk) değil
assert.strictEqual(sn('351.0.227|910.5.159'),10.8);    // sıra karışık gelse de aynı

// ekran görüntüsündeki gerçek satırlarla doğrulama: bitiş = başlama + adet × çevrim
const bitisDk=(adet,k)=>Math.round(adet*sn(k)/60);
assert.strictEqual(bitisDk(320,'351.0.022|910.5.608'),53);  // 23:42 → 00:35 ✔ (ekranda böyle)
assert.strictEqual(bitisDk(180,'351.0.022|910.5.608'),30);  // 21:35 → 22:05 ✔
assert.strictEqual(bitisDk(320,'351.0.022|910.5.053'),80);  // 23:42 → 01:02 ✔ (gerçek üretim)
assert.strictEqual(bitisDk(320,'351.0.022|910.5.159'),58);  // eskiden 23:42→23:42 idi, artık 00:40

// eksik çevrim tespiti (🎲 Üret uyarısı)
const combos={'A||X':{key:'A||X'},'B||X':{key:'B||X'}}, cyc={'A||X':10};
assert.deepStrictEqual(Object.values(combos).filter(c=>!(cyc[c.key]>0)).map(c=>c.key),['B||X']);
console.log('✔ çevrim seçimi + süre hesabı doğru (EL İŞÇİLİĞİ 10,8 sn — dolgu satırı elenmiş)');
