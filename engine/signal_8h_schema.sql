-- Create the table for 8H Signal snapshots
create table if not exists public.signal_8h (
    symbol text primary key,
    updated_at timestamptz default now(),
    data jsonb not null
);

-- Enable RLS
alter table public.signal_8h enable row level security;

-- Allow public read access (anon)
create policy "Allow public read access"
on public.signal_8h
for select
to anon
using (true);

-- Allow service role full access for provider updates
create policy "Allow service role full access"
on public.signal_8h
for all
to service_role
using (true)
with check (true);
