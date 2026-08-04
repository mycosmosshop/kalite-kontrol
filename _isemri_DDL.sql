-- ================================================================
--  İş Emri OPERASYON PLANI ara tablosu — Supabase SQL Editor'de BİR KEZ çalıştır.
--  Proje: nnubrxbpthmkitueixbh (KaliteKontrol)
--
--  NEDEN: LeanSys, her iş emrinin her operasyonu için "üretilecek miktarı" DOĞRU BİRİMDE
--  zaten hesaplıyor (PLN002_ISEMRIDETAY_TBL). Sanal üretim miktarını ürün ağacından
--  türetmek yerine buradan okumak gerekiyor; çünkü ara operasyonların GERÇEKLEŞEN
--  miktarı LeanSys'te bazen stok biriminde değil (ör. LMN2 "30000 Rulo" aslında metre)
--  ve o sayıdan yapılan çevrim milyarlık adetler üretiyor.
--
--    İş emri 2091150347 · 350.0.831 · 10000 Adet
--      op1 LMN3  →   14,42 m²
--      op3 LMN2  →  0,2884 Rulo   (gerçekleşen 30000 yazılmış — hatalı)
--      op5 KP11  →  10000 Adet    ← sanal KP11'in doğru miktarı
--
--  _isemri_refresh.ps1 buraya anon ile yazar (LeanSys yalnız SELECT ile okunur).
-- ================================================================
create table if not exists public.isemri_operasyonlari (
  detay_rec_id   bigint primary key,          -- ISEMRIDETAY_REC_ID
  is_emri        text,                        -- ISEMRI_KODU
  stok_kodu      text,
  stok_adi       text,
  isemri_miktar  double precision,            -- iş emrinin mamul miktarı
  isemri_birim   text,
  op_no          integer,
  makine_kodu    text,
  makine_adi     text,
  planlanan      double precision,            -- ISEMRIDETAY_URETILECEK_MIKTAR (o operasyonun birimiyle)
  op_birim       text,
  uretilen       double precision,            -- ISEMRIDETAY_URETILEN_MIKTAR (bilgi amaçlı)
  guncelleme     timestamptz default now()
);

create index if not exists isemri_op_wo_idx  on public.isemri_operasyonlari (is_emri);
create index if not exists isemri_op_kod_idx on public.isemri_operasyonlari (stok_kodu);

alter table public.isemri_operasyonlari enable row level security;

-- anon VE authenticated: uygulama giriş yapınca authenticated rolü gönderir;
-- yalnız "to anon" olursa giriş yapmış kullanıcı 0 satır görür (bilinen tuzak).
drop policy if exists isemri_op_all on public.isemri_operasyonlari;
create policy isemri_op_all on public.isemri_operasyonlari
  for all to anon, authenticated using (true) with check (true);
