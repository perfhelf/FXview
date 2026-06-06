import { NextResponse } from 'next/server'
import { createSignal8HClient } from '@/lib/signal-8h/client'
import { SIGNAL_8H_EXPECTED_SYMBOLS } from '@/lib/signal-8h/catalog'
import {
  SIGNAL_8H_CACHE_CONTROL,
  getSignal8HDatabaseConfig,
} from '@/lib/signal-8h/config'
import { toSignal8HResponse } from '@/lib/signal-8h/presenter'
import { parseSignal8HQuery } from '@/lib/signal-8h/request'
import { fetchSignal8HRows } from '@/lib/signal-8h/repository'

/**
 * GET /api/signal-8h
 * 
 * Static API endpoint for 8H trend signals.
 * Returns pre-computed trend/first-wave signals for 53 EIGHTCAP instruments.
 * 
 * Query parameters:
 *   ?symbol=XAUUSD — Filter by specific symbol
 * 
 * Response format:
 * {
 *   "signals": [
 *     { "symbol": "XAUUSD", "trend": "多", "first_wave": "空", ... },
 *     ...
 *   ],
 *   "count": 53,
 *   "updated_at": "2026-03-24T12:00:00Z",
 *   "health": { "missing_symbols": [], "stale_symbols": [] }
 * }
 * 
 * No authentication required (public read-only data).
 */
export async function GET(request: Request) {
  try {
    const config = getSignal8HDatabaseConfig()

    if (!config) {
      return NextResponse.json(
        { error: 'Database configuration missing' },
        { status: 500 }
      )
    }

    const supabase = createSignal8HClient(config)
    const query = parseSignal8HQuery(request)
    const rows = await fetchSignal8HRows(supabase, query)
    const expectedSymbols = query.symbol
      ? [query.symbol]
      : SIGNAL_8H_EXPECTED_SYMBOLS

    return NextResponse.json(
      toSignal8HResponse(rows, expectedSymbols),
      {
        status: 200,
        headers: {
          'Cache-Control': SIGNAL_8H_CACHE_CONTROL,
        },
      }
    )
  } catch (err) {
    console.error('Signal API error:', err)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
