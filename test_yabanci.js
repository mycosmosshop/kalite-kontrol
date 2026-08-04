// Makinesi kontrol planında/rotada OLMAYAN üretime, op no'ya bakıp başka operasyonun
// ölçüleri YAZILMAMALI. Gerçek vaka: 350.0.214 · VARGEL KESİM MAK 1 (rotada yok).
//   çalıştır:  node test_yabanci.js
const assert=require('assert');
const deTr=x=>String(x||'').toLowerCase().replace(/ı/g,'i').replace(/ş/g,'s').replace(/ğ/g,'g').replace(/ü/g,'u').replace(/ö/g,'o').replace(/ç/g,'c');
const kk=x=>[...new Set(deTr(x).split(/[^a-z0-9]+/).filter(w=>w.length>=4))];
function equipScore(a,b){ const A=new Set(kk(a).map(w=>w.slice(0,5))), B=new Set(kk(b).map(w=>w.slice(0,5)));
  if(!A.size||!B.size) return 0; let k=0; A.forEach(x=>{if(B.has(x))k++;}); return k/(A.size+B.size-k); }

const rawRows=[ {uretim_ekipman:'LMN3(SICAKSILINDIR LAMINASYON)'},
                {uretim_ekipman:'LMN2 (ESKISEHIR RULO DILIMLEME MAKINASI)'},
                {uretim_ekipman:'KP11-KISSCUT'} ];
const opsByMachine={'350.0.214|910.5.605':[1],'350.0.214|910.5.090':[2],'350.0.214|910.5.607':[3]};
const taninir=(mc,mn)=> (opsByMachine['350.0.214|'+mc]||[]).length>0
                     || !rawRows.length
                     || rawRows.some(x=>equipScore(mn,x.uretim_ekipman)>0);

assert.strictEqual(taninir('910.5.600','VARGEL KESIM MAK 1'), false);   // rotada da planda da yok → ölçü yazılmaz
assert.strictEqual(taninir('910.5.607','KP11-KISSCUT(ESK)'),  true);    // rotada var
assert.strictEqual(taninir('910.5.999','KP11-KISSCUT yeni'),  true);    // kod farklı ama plan ekipmanıyla eşleşiyor
// VARGEL'in KP11 ölçüleriyle eşleşmediğini de doğrula (eski hatanın kaynağı)
assert.strictEqual(equipScore('VARGEL KESIM MAK 1','KP11-KISSCUT'), 0);
console.log('✔ planda olmayan makineye başka operasyonun ölçüsü yazılmıyor');
