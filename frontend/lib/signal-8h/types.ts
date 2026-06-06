export type Signal8HData = Record<string, unknown>

export interface Signal8HRow {
  symbol: string
  data: Signal8HData | null
  updated_at: string
}

export interface Signal8HItem extends Signal8HData {
  symbol: string
}

export interface Signal8HResponseBody {
  signals: Signal8HItem[]
  count: number
  updated_at: string | null
  health: Signal8HHealth
}

export interface Signal8HQuery {
  symbol?: string
}

export interface Signal8HHealth {
  expected_count: number
  returned_count: number
  missing_symbols: string[]
  stale_symbols: string[]
  unavailable_symbols: string[]
  stale_after_hours: number
  oldest_updated_at: string | null
}
