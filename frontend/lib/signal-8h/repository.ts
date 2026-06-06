import type { SupabaseClient } from '@supabase/supabase-js'

import type { Signal8HQuery, Signal8HRow } from './types'

const SIGNAL_8H_COLUMNS = 'symbol, data, updated_at'

export async function fetchSignal8HRows(
  supabase: SupabaseClient,
  query: Signal8HQuery
): Promise<Signal8HRow[]> {
  let request = supabase
    .from('signal_8h')
    .select(SIGNAL_8H_COLUMNS)
    .order('symbol', { ascending: true })

  if (query.symbol) {
    request = request.eq('symbol', query.symbol)
  }

  const { data, error } = await request

  if (error) {
    throw error
  }

  return (data || []) as Signal8HRow[]
}
