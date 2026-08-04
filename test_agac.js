// agacKatsayi, LeanSys "Ürün Ağacı Toplam Tüketim" ile aynı sonucu vermeli.
// Beklenenler 2026-08-04'te LeanSys'ten okundu (fn_UrunAgaciToplamTuketimDefaultByStokRecId, 351.0.181).
//   çalıştır:  node test_agac.js
const fs=require('fs'), assert=require('assert');
const html=fs.readFileSync(__dirname+'/kalite_kontrol.html','utf8');
const src=html.match(/function agacKatsayi\(from,to,tree,_d\)\{[\s\S]*?\n\}/);
assert(src,'agacKatsayi bulunamadı');
const agacKatsayi=new Function('return '+src[0])();

// LeanSys ham BOM satırları: [ana, alt, Miktar, Fire%]
const bom=[
  ['351.0.181','351.20.181',1,0],      ['351.0.181','952.4.039',0.000175,3],
  ['351.0.181','914.4.173',0.005,0],   ['351.0.181','914.4.058',0.005,0],
  ['351.0.181','981.4.109',0.00148,0], ['351.20.181','351.10.181',1,0],
  ['351.10.181','350.20.044',0.892,3], ['350.20.044','950.4.301-2',0.3,0],
  ['350.20.044','HOPO8-90.BH 80',1,0], ['350.20.044','910.4.200-1',0.03,0],
  ['350.20.044','982.4.999-8',0.07,0],
];
const tree={};
for(const [a,b,m,f] of bom){ const o=tree[a]=tree[a]||{}; o[b]=(o[b]||0)+m*(1+f/100); }

// LeanSys panelindeki TOPLAM TÜKETİM sütunu (1 Adet 351.0.181 için)
const beklenen={
  '351.20.181':1, '351.10.181':1, '350.20.044':0.918760, 'HOPO8-90.BH 80':0.918760,
  '950.4.301-2':0.275628, '982.4.999-8':0.064313, '910.4.200-1':0.027563,
  '914.4.173':0.005, '914.4.058':0.005, '952.4.039':0.000180, '981.4.109':0.001480,
};
for(const k in beklenen){
  const v=agacKatsayi('351.0.181',k,tree);
  assert(v!=null && Math.abs(v-beklenen[k])<1e-6, `${k}: ${v} ≠ ${beklenen[k]}`);
}
// 1 Plaka kaç Adet mamul: 351.0.181 için gerçekten 1:1 (LeanSys'te doğrulandı)
assert.strictEqual(agacKatsayi('351.0.181','351.10.181',tree),1);
// Çoklu yol toplanmalı (LeanSys GROUP BY + SUM davranışı)
assert.strictEqual(agacKatsayi('X','Z',{X:{A:2,B:3},A:{Z:5},B:{Z:7}}),2*5+3*7);
assert.strictEqual(agacKatsayi('X','Q',{X:{A:2}}),null);   // yok → null
console.log('✔ agacKatsayi = LeanSys Toplam Tüketim ('+Object.keys(beklenen).length+' malzeme + çoklu yol)');
