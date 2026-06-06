export interface Signal8HDatabaseConfig {
  url: string
  key: string
}

export function getSignal8HDatabaseConfig(): Signal8HDatabaseConfig | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_KEY

  if (!url || !key) {
    return null
  }

  return { url, key }
}

export const SIGNAL_8H_CACHE_CONTROL = 'public, s-maxage=60, stale-while-revalidate=120'
