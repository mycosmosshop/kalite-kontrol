// Sanal üretim miktarı artık İŞ EMRİ OPERASYON PLANINDAN geliyor (ürün ağacı tahmininden değil).
// Sayılar 2026-08-04'te LeanSys PLN001/PLN002'den okundu (350.0.831).
//   çalıştır:  node test_isemri.js
const assert=require('assert');

// isemri_operasyonlari: is_emri|makine_kodu -> {qty,birim}
const woPlan={
  '2091150347|910.5.605':[{qty:14.42,birim:'m2',op:1}], '2091150347|910.5.090':[{qty:0.2884,birim:'Rulo',op:3}],
  '2091150347|910.5.607':[{qty:10000,birim:'Adet',op:5}],
  '2091150347|910.5.084':[{qty:14.42,birim:'m2',op:2},{qty:10000,birim:'Adet',op:6}],   // aynı makine iki adımda
  '2091151046|910.5.605':[{qty:14.42,birim:'m2',op:1}], '2091151046|910.5.090':[{qty:0.2884,birim:'Rulo',op:2}],
  '2091151046|910.5.607':[{qty:10000,birim:'Adet',op:3}],
};
const deTr=x=>String(x||'').toLowerCase();
const wpPick=(wo,mc,istenen)=>{ const list=woPlan[(wo||'')+'|'+(mc||'')]; if(!list||!list.length) return null;
  const b=deTr(String(istenen||'').trim());
  return (b && list.find(x=>deTr(String(x.birim||'').trim())===b)) || [...list].sort((x,y)=>x.op-y.op)[0]; };
// uygulamadaki hesap (birebir)
function sanalMiktar(wo, bazMc, bazQty, hedefMc, hedefBirim, bazBirim){
  const wp=wpPick(wo,hedefMc,hedefBirim), bp=wpPick(wo,bazMc,bazBirim);
  if(!wp) return null;
  let K=1;
  if(bp && bp.qty>0 && bazQty>0){ const k=bazQty/bp.qty; if(k>=0.1&&k<=10) K=k; }
  const tam=/adet|plaka|paket|koli|rulo|top/i.test(wp.birim||'');
  return { qty: tam?Math.max(1,Math.round(wp.qty*K)):Math.round(wp.qty*K*1e4)/1e4, unit:wp.birim };
}

// 18.07 — baz LMN2 "30000 Rulo" (LeanSys'te birim HATALI, aslında metre).
// Oran 104.022 → makul aralık dışı → K=1, plan aynen kullanılır. Eskiden 1.040.221.914 Adet çıkıyordu.
assert.deepStrictEqual(sanalMiktar('2091150347','910.5.090',30000,'910.5.607'),{qty:10000,unit:'Adet'});
assert.deepStrictEqual(sanalMiktar('2091150347','910.5.090',30000,'910.5.605'),{qty:14.42,unit:'m2'});

// 27.07 — baz KP11 35000 Adet, plan 10000 → K=3,5 (makul) → plan ölçeklenir
assert.deepStrictEqual(sanalMiktar('2091151046','910.5.607',35000,'910.5.090'),{qty:1,unit:'Rulo'});      // 0,2884×3,5=1,01
assert.deepStrictEqual(sanalMiktar('2091151046','910.5.607',35000,'910.5.605'),{qty:50.47,unit:'m2'});   // 14,42×3,5

// plan yoksa null → uygulama eski ürün ağacı yöntemine düşer
assert.strictEqual(sanalMiktar('9999999','910.5.607',100,'910.5.090'),null);

// AYNI MAKİNE İKİ ADIMDA: beklenen birime göre doğru satır seçilmeli (KKP m² ve Adet)
assert.deepStrictEqual(sanalMiktar('2091150347','910.5.607',10000,'910.5.084','Adet'),{qty:10000,unit:'Adet'});
assert.deepStrictEqual(sanalMiktar('2091150347','910.5.607',10000,'910.5.084','m2'),{qty:14.42,unit:'m2'});
assert.deepStrictEqual(sanalMiktar('2091150347','910.5.607',10000,'910.5.084'),{qty:14.42,unit:'m2'});   // birim bilinmiyor → en küçük op

// LeanSys'in kendi planı ürün ağacıyla tutarlı: 10000 Adet × 0,000028×1,03 = 0,2884 Rulo
assert.ok(Math.abs(10000*0.000028*1.03 - 0.2884) < 1e-4);
console.log('✔ sanal miktar iş emri planından (bozuk baz miktar artık patlatmıyor)');
