-- ================================================================
--  KEEPALIVE tablosu — HER Supabase projesinde BİR KEZ çalıştır.
--  Ücretsiz planda 7 gün hareketsiz proje otomatik duraklatılır.
--
--  Neden okuma yetmiyor olabilir: RLS yüzünden SELECT 0 satır dönebiliyor
--  (Content-Range: */0). Sorgu çalışsa da "hareket" olarak sayılmama riski var.
--  YAZMA (upsert) her seferinde gerçek bir DB değişikliği + WAL üretir; tartışmasızdır.
--
--  Güvenli: tek satırlık ayrı bir tablo, uygulama verisine hiç dokunmaz.
--  Çalıştırılacak projeler (SQL Editor > New query > Run):
--    bgraqliedgmksqdbddkp  (CMMS — duraklatma uyarısı bundan geliyor)
--    nnubrxbpthmkitueixbh  (KaliteKontrol / ERP)
--    donjfzetqpzrgforhenu
--    chchaielttnimuuezazb  (tedarikçi senkron)
-- ================================================================
create table if not exists public.keepalive (
  id         int primary key default 1,
  ping_at    timestamptz not null default now(),
  ping_count bigint not null default 0,
  constraint keepalive_tek_satir check (id = 1)
);

insert into public.keepalive (id) values (1) on conflict (id) do nothing;

alter table public.keepalive enable row level security;

-- anon VE authenticated yazabilsin (GitHub Actions anon anahtarla çağırır).
-- Tabloda hiçbir iş verisi yok; yalnız zaman damgası ve sayaç.
drop policy if exists keepalive_all on public.keepalive;
create policy keepalive_all on public.keepalive
  for all to anon, authenticated using (true) with check (true);
