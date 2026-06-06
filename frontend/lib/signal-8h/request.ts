import type { Signal8HQuery } from './types'

export function parseSignal8HQuery(request: Request): Signal8HQuery {
  const { searchParams } = new URL(request.url)
  const symbol = searchParams.get('symbol')?.trim().toUpperCase()

  return symbol ? { symbol } : {}
}
