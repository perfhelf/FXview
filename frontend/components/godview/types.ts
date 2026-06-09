export interface GodViewData {
  symbol: string
  trend_status: number // 1=Long, -1=Short, 2=Both, 0=Wait
  fw_status?: number // Wave 1: 1=Long, -1=Short, 2=Both, 0=Wait
  last_update?: string // Timestamp from backend payload (preferred source)
  ema_slopes: {
    short: { d: number[], w: number[] }
    mid: { d: number[], w: number[] }
    long: { d: number[], w: number[] }
  }
  signals: SignalSet
  fw_signals?: SignalSet
}

export interface SignalSet {
  rsi: { d: boolean[], w: boolean[] }
  macd: { d: boolean[], w: boolean[] }
  adx: { d: boolean[], w: boolean[] }
}

export interface SnapshotRow {
  symbol: string
  updated_at: string
  data: GodViewData
}

export type TrendPeriod = 'short' | 'mid' | 'long'
export type ViewMode = 'card' | 'table'

export interface SlopeGroup {
  d: number[]
  w: number[]
}
