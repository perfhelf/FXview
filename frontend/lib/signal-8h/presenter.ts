import type { Signal8HHealth, Signal8HResponseBody, Signal8HRow } from './types'
import {
  SIGNAL_8H_EXPECTED_SYMBOLS,
  SIGNAL_8H_STALE_AFTER_HOURS,
} from './catalog'

export function toSignal8HResponse(
  rows: Signal8HRow[],
  expectedSymbols: readonly string[] = SIGNAL_8H_EXPECTED_SYMBOLS
): Signal8HResponseBody {
  const health = buildSignal8HHealth(rows, expectedSymbols)

  if (rows.length === 0) {
    return {
      signals: [],
      count: 0,
      updated_at: null,
      health,
    }
  }

  const signals = rows.map(row => ({
    symbol: row.symbol,
    ...(row.data || {}),
  }))
  const latestUpdate = rows.reduce((latest, row) => {
    return row.updated_at > latest ? row.updated_at : latest
  }, rows[0].updated_at)

  return {
    signals,
    count: signals.length,
    updated_at: latestUpdate,
    health,
  }
}

export function buildSignal8HHealth(
  rows: Signal8HRow[],
  expectedSymbols: readonly string[]
): Signal8HHealth {
  const returnedSymbols = new Set(rows.map(row => row.symbol))
  const missingSymbols = expectedSymbols.filter(symbol => !returnedSymbols.has(symbol))
  const staleCutoff = Date.now() - SIGNAL_8H_STALE_AFTER_HOURS * 60 * 60 * 1000
  const staleSymbols = rows
    .filter(row => {
      const updatedAt = new Date(row.updated_at).getTime()
      return Number.isFinite(updatedAt) && updatedAt < staleCutoff
    })
    .map(row => row.symbol)
    .sort()
  const unavailableSymbols = rows
    .filter(row => {
      const status = row.data?.data_status
      return typeof status === 'string' && status !== 'ok'
    })
    .map(row => row.symbol)
    .sort()
  const oldestUpdatedAt = rows.reduce<string | null>((oldest, row) => {
    if (!oldest || row.updated_at < oldest) return row.updated_at
    return oldest
  }, null)

  return {
    expected_count: expectedSymbols.length,
    returned_count: rows.length,
    missing_symbols: missingSymbols,
    stale_symbols: staleSymbols,
    unavailable_symbols: unavailableSymbols,
    stale_after_hours: SIGNAL_8H_STALE_AFTER_HOURS,
    oldest_updated_at: oldestUpdatedAt,
  }
}
