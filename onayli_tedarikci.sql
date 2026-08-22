-- Onaylı tedarikçi listesi (PL11). Tedarikçi modülü listeyi buraya yazar;
-- APQP belge üreteci lokasyon + otomotiv filtresiyle buradan okur.
-- Mevcut Supabase projesinde (nnubrxbpthmkitueixbh) bir kez çalıştırın.
create table if not exists public.onayli_tedarikci (
  ad          text primary key,          -- tedarikçi adı (normalize edilmemiş hâli)
  durum       text,                      -- Onaylı / Şartlı / Red
  lokasyon    text[] not null default '{}',   -- ['Çerkezköy','Ankara'] — birden fazla olabilir
  sinif       text,                      -- A / B / C / D (düzeltilmiş sınıf)
  puan        numeric,
  ppm         numeric,
  otomotiv    boolean not null default false, -- Tip A (Otomotiv)
  iatf        boolean not null default false,
  iso9001     boolean not null default false,
  belgeler    text,                      -- belge listesi (metin)
  tavan_not   text,                      -- sınıf tavanı uygulandıysa gerekçe
  guncelleme  timestamptz not null default now()
);

alter table public.onayli_tedarikci enable row level security;

drop policy if exists otd_oku      on public.onayli_tedarikci;
drop policy if exists otd_yaz      on public.onayli_tedarikci;
drop policy if exists otd_guncelle on public.onayli_tedarikci;
drop policy if exists otd_sil      on public.onayli_tedarikci;

create policy otd_oku      on public.onayli_tedarikci for select using (true);
create policy otd_yaz      on public.onayli_tedarikci for insert with check (true);
create policy otd_guncelle on public.onayli_tedarikci for update using (true) with check (true);
create policy otd_sil      on public.onayli_tedarikci for delete using (true);

-- Lokasyon dizisinde arama hızlansın (PL11 lokasyona göre süzülüyor)
create index if not exists onayli_tedarikci_lokasyon on public.onayli_tedarikci using gin (lokasyon);
