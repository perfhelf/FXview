'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { useTheme } from './providers'

// ==========================================
// Types
// ==========================================
interface GodViewData {
  symbol: string
  trend_status: number // 1=Long, -1=Short, 2=Both, 0=Wait
  ema_slopes: {
    short: { d: number[], w: number[] }
    mid: { d: number[], w: number[] }
    long: { d: number[], w: number[] }
  }
  signals: {
    rsi: { d: boolean[], w: boolean[] }
    macd: { d: boolean[], w: boolean[] }
    adx: { d: boolean[], w: boolean[] }
  }
}

interface SnapshotRow {
  symbol: string
  updated_at: string
  data: GodViewData
}

type TrendPeriod = 'short' | 'mid' | 'long'
type ViewMode = 'card' | 'table'

// ==========================================
// Constants
// ==========================================
const SYMBOL_NAMES: Record<string, string> = {
  USD: '美元', EUR: '欧元', GBP: '英镑', JPY: '日元',
  AUD: '澳元', CAD: '加元', NZD: '纽元', CHF: '瑞郎',
  SGD: '新元', MXN: '比索', SEK: '瑞典', NOK: '挪威',
}

const TV_FORMULAS: Record<string, string> = {
  AUD: 'FX:AUDUSD/0.66047+FX:USDCAD*FX:AUDUSD/0.90476+FX:AUDUSD/FX:EURUSD/0.61763+FX:AUDUSD/FX:GBPUSD/0.53138+FX:AUDUSD*FX:USDJPY/94.23133',
  CAD: '1/FX:USDCAD/0.72965+1/(FX:USDCAD*FX:AUDUSD)/1.1055+1/(FX:EURUSD*FX:USDCAD)/0.68211+1/(FX:GBPUSD*FX:USDCAD)/0.58657+FX:USDJPY/FX:USDCAD/104.165',
  CHF: '1/FX:USDCHF/1.12406+FX:USDCAD/FX:USDCHF/1.54202+1/(FX:EURUSD*FX:USDCHF)/1.05058+1/(FX:USDCHF*FX:GBPUSD)/0.90315+FX:USDJPY/FX:USDCHF/160.83167',
  JPY: '1/FX:USDJPY/0.00703+1/(FX:USDJPY*FX:AUDUSD)/0.01063+FX:USDCAD/FX:USDJPY/0.00963+1/(FX:USDJPY*FX:GBPUSD)/0.00566+1/(FX:USDJPY*FX:EURUSD)/0.00656',
  EUR: 'FX:EURUSD/1.06973+FX:EURUSD/FX:AUDUSD/1.62021+FX:EURUSD*FX:USDCAD/1.46625+FX:EURUSD/FX:GBPUSD/0.85959+FX:EURUSD*FX:USDJPY/152.95167',
  GBP: 'FX:GBPUSD/1.24401+FX:GBPUSD/FX:AUDUSD/1.88737+FX:GBPUSD*FX:USDCAD/1.70749+FX:GBPUSD/FX:EURUSD/1.16423+FX:GBPUSD*FX:USDJPY/178.228',
  USD: 'TVC:DXY',
  NZD: 'FX:NZDUSD/0.60851+FX:USDCAD*FX:NZDUSD/0.83363+FX:NZDUSD/FX:EURUSD/0.56898+FX:NZDUSD/FX:GBPUSD/0.48991+FX:USDJPY*FX:NZDUSD/86.76033',
  SGD: '1/OANDA:USDSGD/0.74527+FX:USDCAD/OANDA:USDSGD/1.02258+1/(FX:EURUSD*OANDA:USDSGD)/0.69684+1/(OANDA:USDSGD*FX:GBPUSD)/0.59898+FX:USDJPY/OANDA:USDSGD/106.60933',
  MXN: '1/FX:USDMXN/0.05273+FX:USDCAD/FX:USDMXN/0.07218+1/(FX:EURUSD*FX:USDMXN)/0.0492+1/(FX:USDMXN*FX:GBPUSD)/0.04234+FX:USDJPY/FX:USDMXN/7.52667',
  SEK: '1/FX:USDSEK/0.09512+FX:USDCAD/FX:USDSEK/0.13038+1/(FX:EURUSD*FX:USDSEK)/0.08885+1/(FX:USDSEK*FX:GBPUSD)/0.07644+FX:USDJPY/FX:USDSEK/13.58497',
  NOK: '1/OANDA:USDNOK/0.09603+FX:USDCAD/OANDA:USDNOK/0.13154+1/(FX:EURUSD*OANDA:USDNOK)/0.08968+1/(OANDA:USDNOK*FX:GBPUSD)/0.07723+FX:USDJPY/OANDA:USDNOK/13.68007',
}

const INTERVALS = [
  { label: '1H', value: '60' }, { label: '2H', value: '120' }, { label: '4H', value: '240' },
  { label: '日', value: 'D' }, { label: '周', value: 'W' }, { label: '月', value: 'M' },
]

const TREND_PERIODS = [
  { key: 'short', label: '短期趋势', period: 20 },
  { key: 'mid', label: '中期趋势', period: 50 },
  { key: 'long', label: '长期趋势', period: 90 },
] as const

const THRESHOLDS = { flat: 0.001, weak: 0.003, healthy: 0.005 }
const EMA_LABELS = ['EMA20', 'EMA50', 'EMA100', 'EMA200']

// ==========================================
// Helper Components & Functions
// ==========================================
function getTradingViewUrl(symbol: string, interval: string = '30') {
  const formula = TV_FORMULAS[symbol]
  if (!formula) return '#'
  const encodedSymbol = encodeURIComponent(formula)
  return `https://cn.tradingview.com/chart/?symbol=${encodedSymbol}&interval=${interval}`
}

function getSlopeStatus(slope: number) {
  const abs = Math.abs(slope)
  if (abs >= THRESHOLDS.healthy) {
    return { icon: slope >= 0 ? '🟢' : '🔴', text: '健康', color: slope >= 0 ? 'text-green-400' : 'text-red-400' }
  }
  if (abs >= THRESHOLDS.weak) {
    return { icon: '🔵', text: '渐弱', color: 'text-blue-400' }
  }
  if (abs >= THRESHOLDS.flat) {
    return { icon: '🟡', text: '谨慎', color: 'text-yellow-400' }
  }
  return { icon: '⚪', text: '平缓', color: 'text-gray-400' }
}

function TrendBadge({ status }: { status: number }) {
  if (status === 1) return <span className="px-2 py-1 rounded bg-green-600/30 text-green-300 text-xs font-bold">趋势:多</span>
  if (status === -1) return <span className="px-2 py-1 rounded bg-red-600/30 text-red-300 text-xs font-bold">趋势:空</span>
  if (status === 2) return <span className="px-2 py-1 rounded bg-yellow-600/30 text-yellow-300 text-xs font-bold">趋势:双向</span>
  return <span className="px-2 py-1 rounded bg-gray-600/30 text-gray-300 text-xs font-bold">趋势:待定</span>
}

function SlopeCell({ slope }: { slope: number }) {
  const { icon, text, color } = getSlopeStatus(slope)
  return (
    <td className={`px-2 py-1 text-center text-xs ${color}`}>
      <div>{icon} {slope.toFixed(4)}</div>
      <div className="text-[10px] opacity-70">{text}</div>
    </td>
  )
}

// Card version of SlopeCell (as a div, not td)
function SlopeCellDiv({ slope, label }: { slope: number, label?: string }) {
  const { icon, text, color } = getSlopeStatus(slope)
  return (
    <div className={`text-center text-xs ${color} flex-1`}>
      {label && <div className="text-[9px] text-slate-500 font-mono mb-0.5">{label}</div>}
      <div>{icon} {slope.toFixed(4)}</div>
      <div className="text-[10px] opacity-70">{text}</div>
    </div>
  )
}

function SignalIcon({ long, short }: { long: boolean, short: boolean }) {
  if (long && short) return <span>🟡</span>
  if (long) return <span>🟢</span>
  if (short) return <span>🔴</span>
  return <span>⚪</span>
}

function CurrencyCell({ symbol }: { symbol: string }) {
  const name = SYMBOL_NAMES[symbol] || symbol

  return (
    <td className="px-2 py-2">
      <div className="flex items-center gap-1 flex-wrap">
        <a
          href={getTradingViewUrl(symbol, '30')}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-blue-300 hover:text-blue-100 hover:underline cursor-pointer"
        >
          {name} {symbol}
        </a>
        <div className="flex gap-0.5">
          {INTERVALS.map((int) => (
            <a
              key={int.value}
              href={getTradingViewUrl(symbol, int.value)}
              target="_blank"
              rel="noopener noreferrer"
              className="px-1.5 py-0.5 text-[10px] bg-slate-700 hover:bg-slate-600 rounded text-slate-300 hover:text-white transition-colors"
            >
              {int.label}
            </a>
          ))}
        </div>
      </div>
    </td>
  )
}

function TrendPeriodSelector({ selected, onSelect }: { selected: TrendPeriod, onSelect: (p: TrendPeriod) => void }) {
  return (
    <div className="flex justify-center gap-2 flex-wrap">
      {TREND_PERIODS.map((tp) => (
        <button
          key={tp.key}
          onClick={() => onSelect(tp.key)}
          className={`px-3 py-1.5 sm:px-4 sm:py-2 rounded-lg text-xs sm:text-sm font-medium transition-all ${selected === tp.key
              ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/30'
              : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
        >
          {tp.label}
          <span className="ml-1 text-xs opacity-70">({tp.period})</span>
        </button>
      ))}
    </div>
  )
}

function ViewModeToggle({ selected, onSelect }: { selected: ViewMode, onSelect: (m: ViewMode) => void }) {
  return (
    <div className="flex justify-center gap-2 mt-3">
      <button
        onClick={() => onSelect('card')}
        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1 ${selected === 'card'
            ? 'bg-teal-600 text-white'
            : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
          }`}
      >
        📇 信息卡
      </button>
      <button
        onClick={() => onSelect('table')}
        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1 ${selected === 'table'
            ? 'bg-teal-600 text-white'
            : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
          }`}
      >
        📊 表格
      </button>
    </div>
  )
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => { setMounted(true) }, [])

  if (!mounted) return null

  const options = [
    { key: 'light' as const, icon: '☀️' },
    { key: 'dark' as const, icon: '🌙' },
    { key: 'system' as const, icon: '🖥️' },
  ]

  return (
    <div className="flex rounded-lg overflow-hidden shadow-sm border border-slate-300 dark:border-slate-700">
      {options.map((opt) => (
        <button
          key={opt.key}
          onClick={() => setTheme(opt.key)}
          className={`px-2 py-1 sm:px-3 sm:py-1.5 text-sm font-medium transition-colors ${theme === opt.key
              ? 'bg-blue-600 text-white'
              : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
            }`}
          aria-label={opt.key}
        >
          {opt.icon}
        </button>
      ))}
    </div>
  )
}

// ==========================================
// Sub-Components (Table Row & Card)
// ==========================================

function CurrencyRow({ row, trendPeriod }: { row: SnapshotRow, trendPeriod: TrendPeriod }) {
  const d = row.data
  const slopes = d.ema_slopes?.[trendPeriod] || d.ema_slopes as unknown as { d: number[], w: number[] }
  const dailySlopes = slopes?.d || [0, 0, 0, 0]
  const weeklySlopes = slopes?.w || [0, 0, 0, 0]

  return (
    <tr className="border-t border-slate-700 hover:bg-slate-800/50 transition-colors">
      <CurrencyCell symbol={row.symbol} />
      <td className="px-3 py-2 text-center"><TrendBadge status={d.trend_status} /></td>
      <td className="px-3 py-2 text-center">
        <SignalIcon long={d.signals.rsi.d[0]} short={d.signals.rsi.d[1]} />
        <span className="text-[10px] text-slate-500">D</span>
        <SignalIcon long={d.signals.rsi.w[0]} short={d.signals.rsi.w[1]} />
        <span className="text-[10px] text-slate-500">W</span>
      </td>
      <td className="px-3 py-2 text-center">
        <SignalIcon long={d.signals.macd.d[0]} short={d.signals.macd.d[1]} />
        <span className="text-[10px] text-slate-500">D</span>
        <SignalIcon long={d.signals.macd.w[0]} short={d.signals.macd.w[1]} />
        <span className="text-[10px] text-slate-500">W</span>
      </td>
      <td className="px-3 py-2 text-center">
        <SignalIcon long={d.signals.adx.d[0]} short={d.signals.adx.d[1]} />
        <span className="text-[10px] text-slate-500">D</span>
        <SignalIcon long={d.signals.adx.w[0]} short={d.signals.adx.w[1]} />
        <span className="text-[10px] text-slate-500">W</span>
      </td>
      {/* Daily EMAs */}
      <SlopeCell slope={dailySlopes[0]} />
      <SlopeCell slope={dailySlopes[1]} />
      <SlopeCell slope={dailySlopes[2]} />
      <SlopeCell slope={dailySlopes[3]} />
      {/* Weekly EMAs */}
      <SlopeCell slope={weeklySlopes[0]} />
      <SlopeCell slope={weeklySlopes[1]} />
      <SlopeCell slope={weeklySlopes[2]} />
      <SlopeCell slope={weeklySlopes[3]} />
    </tr>
  )
}

function CurrencyCard({ row, trendPeriod }: { row: SnapshotRow, trendPeriod: TrendPeriod }) {
  const d = row.data
  const slopes = d.ema_slopes?.[trendPeriod] || d.ema_slopes as unknown as { d: number[], w: number[] }
  const dailySlopes = slopes?.d || [0, 0, 0, 0]
  const weeklySlopes = slopes?.w || [0, 0, 0, 0]
  const symbol = row.symbol
  const name = SYMBOL_NAMES[symbol] || symbol

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 flex flex-col gap-4 shadow-lg">
      {/* Header */}
      <div className="flex justify-between items-center pb-3 border-b border-slate-800">
        <a
          href={getTradingViewUrl(symbol, '30')}
          target="_blank"
          rel="noopener noreferrer"
          className="flex flex-col cursor-pointer hover:opacity-80 transition-opacity"
        >
          <span className="text-lg font-bold text-slate-100">{symbol}</span>
          <span className="text-xs text-slate-400">{name}</span>
        </a>
        <TrendBadge status={d.trend_status} />
      </div>

      {/* Signals Grid */}
      <div className="grid grid-cols-3 gap-2 text-center bg-slate-800/50 rounded-lg p-2">
        <div className="flex flex-col items-center">
          <div className="text-xs text-slate-500 mb-1">RSI</div>
          <div className="flex gap-1">
            <div><SignalIcon long={d.signals.rsi.d[0]} short={d.signals.rsi.d[1]} /><span className="text-[10px] text-slate-600 block leading-none">D</span></div>
            <div><SignalIcon long={d.signals.rsi.w[0]} short={d.signals.rsi.w[1]} /><span className="text-[10px] text-slate-600 block leading-none">W</span></div>
          </div>
        </div>
        <div className="flex flex-col items-center border-l border-slate-700/50">
          <div className="text-xs text-slate-500 mb-1">MACD</div>
          <div className="flex gap-1">
            <div><SignalIcon long={d.signals.macd.d[0]} short={d.signals.macd.d[1]} /><span className="text-[10px] text-slate-600 block leading-none">D</span></div>
            <div><SignalIcon long={d.signals.macd.w[0]} short={d.signals.macd.w[1]} /><span className="text-[10px] text-slate-600 block leading-none">W</span></div>
          </div>
        </div>
        <div className="flex flex-col items-center border-l border-slate-700/50">
          <div className="text-xs text-slate-500 mb-1">ADX</div>
          <div className="flex gap-1">
            <div><SignalIcon long={d.signals.adx.d[0]} short={d.signals.adx.d[1]} /><span className="text-[10px] text-slate-600 block leading-none">D</span></div>
            <div><SignalIcon long={d.signals.adx.w[0]} short={d.signals.adx.w[1]} /><span className="text-[10px] text-slate-600 block leading-none">W</span></div>
          </div>
        </div>
      </div>

      {/* Slopes with EMA Labels */}
      <div className="space-y-3 text-sm bg-slate-800/30 rounded-lg p-2">
        {/* Daily Row */}
        <div>
          <div className="text-xs text-teal-400/70 font-mono mb-1">Daily</div>
          <div className="flex gap-1">
            {dailySlopes.map((s, i) => (
              <SlopeCellDiv key={i} slope={s} label={EMA_LABELS[i]} />
            ))}
          </div>
        </div>
        {/* Weekly Row */}
        <div className="border-t border-slate-800/50 pt-2">
          <div className="text-xs text-purple-400/70 font-mono mb-1">Weekly</div>
          <div className="flex gap-1">
            {weeklySlopes.map((s, i) => (
              <SlopeCellDiv key={i} slope={s} label={EMA_LABELS[i]} />
            ))}
          </div>
        </div>
      </div>

      {/* Footer Buttons */}
      <div className="grid grid-cols-6 gap-1 pt-2">
        {INTERVALS.map((int) => (
          <a
            key={int.value}
            href={getTradingViewUrl(symbol, int.value)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center py-1.5 text-[10px] font-bold bg-slate-800 hover:bg-slate-700 rounded text-slate-400 hover:text-white transition-colors border border-slate-700"
          >
            {int.label}
          </a>
        ))}
      </div>
    </div>
  )
}

// ==========================================
// Main Component
// ==========================================
export default function Home() {
  const [data, setData] = useState<SnapshotRow[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<string | null>(null)
  const [trendPeriod, setTrendPeriod] = useState<TrendPeriod>('short')
  const [viewMode, setViewMode] = useState<ViewMode>('card') // Default to card

  useEffect(() => {
    async function fetchData() {
      const { data: rows, error } = await supabase
        .from('godview_snapshot')
        .select('*')

      if (error) {
        console.error('Error fetching data:', error)
        setLoading(false)
        return
      }

      if (rows && rows.length > 0) {
        // Sort by symbol order
        const order = Object.keys(SYMBOL_NAMES)
        const sorted = rows.sort((a, b) => order.indexOf(a.symbol) - order.indexOf(b.symbol))
        setData(sorted as SnapshotRow[])
        setLastUpdate(rows[0]?.updated_at)
      }
      setLoading(false)
    }

    fetchData()
    // Auto-refresh every 5 minutes
    const interval = setInterval(fetchData, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-xl animate-pulse">Loading GodView...</div>
      </div>
    )
  }

  return (
    <main className="p-4 md:p-8 relative min-h-screen">
      {/* Header with Theme Toggle */}
      <header className="mb-4">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <h1 className="text-xl sm:text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent text-center sm:text-left">
            🌐 鲲侯FXView · 全球汇率上帝视角
          </h1>
          <ThemeToggle />
        </div>
        <p className="text-sm text-slate-400 mt-2 text-center sm:text-left">
          Last Update: {lastUpdate ? new Date(lastUpdate).toLocaleString() : 'N/A'}
        </p>
      </header>

      {/* Controls */}
      <div className="mb-6">
        <TrendPeriodSelector selected={trendPeriod} onSelect={setTrendPeriod} />
        <ViewModeToggle selected={viewMode} onSelect={setViewMode} />
      </div>

      {/* View Mode Switching (State-Based, not Responsive) */}

      {/* Table View */}
      {viewMode === 'table' && (
        <div className="overflow-x-auto rounded-lg border border-slate-700 shadow-xl">
          <table className="w-full text-sm">
            <thead className="bg-slate-800/90 text-slate-200">
              <tr>
                <th className="px-3 py-3 text-left font-semibold">货币</th>
                <th className="px-3 py-3 text-center font-semibold">司令部</th>
                <th className="px-3 py-3 text-center font-semibold text-xs opacity-70">RSI</th>
                <th className="px-3 py-3 text-center font-semibold text-xs opacity-70">MACD</th>
                <th className="px-3 py-3 text-center font-semibold text-xs opacity-70">ADX</th>
                <th className="px-2 py-3 text-center bg-teal-900/40 text-teal-200 text-xs font-mono">20D</th>
                <th className="px-2 py-3 text-center bg-teal-900/40 text-teal-200 text-xs font-mono">50D</th>
                <th className="px-2 py-3 text-center bg-teal-900/40 text-teal-200 text-xs font-mono">100D</th>
                <th className="px-2 py-3 text-center bg-teal-900/40 text-teal-200 text-xs font-mono">200D</th>
                <th className="px-2 py-3 text-center bg-purple-900/40 text-purple-200 text-xs font-mono">20W</th>
                <th className="px-2 py-3 text-center bg-purple-900/40 text-purple-200 text-xs font-mono">50W</th>
                <th className="px-2 py-3 text-center bg-purple-900/40 text-purple-200 text-xs font-mono">100W</th>
                <th className="px-2 py-3 text-center bg-purple-900/40 text-purple-200 text-xs font-mono">200W</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50 bg-slate-900/50">
              {data.map((row) => (
                <CurrencyRow key={row.symbol} row={row} trendPeriod={trendPeriod} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Card View */}
      {viewMode === 'card' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {data.map((row) => (
            <CurrencyCard key={row.symbol} row={row} trendPeriod={trendPeriod} />
          ))}
        </div>
      )}

      <footer className="mt-12 text-center text-sm text-slate-500 space-y-2 pb-8">
        <p>本站所有指数算法由太囍倾情提供</p>
        <p>版权所有@太囍＆鲲侯</p>
        <p className="text-xs opacity-50 pt-2">Data Source: Yahoo Finance</p>
      </footer>
    </main>
  )
}
