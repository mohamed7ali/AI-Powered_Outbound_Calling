-- Additive migration for databases that already applied 202608160001.
alter table if exists public.calls
  add column if not exists duration_seconds integer
  check (duration_seconds is null or duration_seconds >= 0);
