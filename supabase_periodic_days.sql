-- Kalan süre (periyodik vade) — kriter bazında EKLE/KALDIR için override sütunu.
-- Kalite Kontrol Supabase projesi → SQL Editor → yapıştır → Run.
-- periodic_days: NULL = otomatik (madde metninden), >0 = elle eklendi (gün periyodu), 0 = kaldırıldı.

alter table public.control_plan_items
  add column if not exists periodic_days int;
