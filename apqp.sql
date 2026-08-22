-- APQP / PPAP kayıtları. Mevcut Supabase projesinde (nnubrxbpthmkitueixbh)
-- SQL Editor'de bir kez çalıştırın. Yapı pfmea_projects ile aynı.
create table if not exists public.apqp_projeler (
  id          text primary key,
  name        text,
  data        jsonb not null default '{}'::jsonb,
  updated_at  timestamptz not null default now()
);

alter table public.apqp_projeler enable row level security;

-- Portal modülleri anon anahtarla çalışıyor (pfmea_projects ile aynı düzen).
drop policy if exists apqp_oku   on public.apqp_projeler;
drop policy if exists apqp_yaz   on public.apqp_projeler;
drop policy if exists apqp_guncelle on public.apqp_projeler;
drop policy if exists apqp_sil   on public.apqp_projeler;

create policy apqp_oku      on public.apqp_projeler for select using (true);
create policy apqp_yaz      on public.apqp_projeler for insert with check (true);
create policy apqp_guncelle on public.apqp_projeler for update using (true) with check (true);
create policy apqp_sil      on public.apqp_projeler for delete using (true);

-- Kayıt güncellendiğinde updated_at kendiliğinden yenilensin
create or replace function public.apqp_tarih_guncelle() returns trigger as $$
begin
  new.updated_at := now();
  return new;
end $$ language plpgsql;

drop trigger if exists apqp_tarih on public.apqp_projeler;
create trigger apqp_tarih before update on public.apqp_projeler
  for each row execute function public.apqp_tarih_guncelle();
