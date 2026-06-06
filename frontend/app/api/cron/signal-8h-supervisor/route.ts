import { NextResponse } from 'next/server'
import { isAuthorizedCronRequest } from '@/lib/cron/auth'
import { SIGNAL_8H_EXPECTED_SYMBOLS } from '@/lib/signal-8h/catalog'
import { createSignal8HClient } from '@/lib/signal-8h/client'
import { getSignal8HDatabaseConfig } from '@/lib/signal-8h/config'
import { buildSignal8HHealth } from '@/lib/signal-8h/presenter'
import { fetchSignal8HRows } from '@/lib/signal-8h/repository'

export const runtime = 'nodejs'

export async function GET(request: Request) {
  if (!isAuthorizedCronRequest(request)) {
    return NextResponse.json({ ok: false, error: 'unauthorized' }, { status: 401 })
  }

  const config = getSignal8HDatabaseConfig()

  if (!config) {
    return NextResponse.json(
      { ok: false, error: 'database_configuration_missing' },
      { status: 500 }
    )
  }

  const supabase = createSignal8HClient(config)
  const rows = await fetchSignal8HRows(supabase, {})
  const health = buildSignal8HHealth(rows, SIGNAL_8H_EXPECTED_SYMBOLS)
  const problems = [
    ...health.missing_symbols.map(symbol => `missing:${symbol}`),
    ...health.stale_symbols.map(symbol => `stale:${symbol}`),
    ...health.unavailable_symbols.map(symbol => `unavailable:${symbol}`),
  ]

  return NextResponse.json(
    {
      ok: problems.length === 0,
      checked_at: new Date().toISOString(),
      problems,
      health,
    },
    { status: problems.length === 0 ? 200 : 500 }
  )
}
