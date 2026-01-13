-- Create the table for GodView snapshots
create table if not exists public.godview_snapshot (
    symbol text primary key,
    updated_at timestamptz default now(),
    data jsonb not null
);

-- Enable RLS
alter table public.godview_snapshot enable row level security;

-- Allow public read access (anon)
create policy "Allow public read access"
on public.godview_snapshot
for select
to anon
using (true);

-- Allow service role full access (for updates)
create policy "Allow service role full access"
on public.godview_snapshot
for all
to service_role
using (true)
with check (true);
