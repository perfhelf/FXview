'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'

interface GodViewData {
  symbol: string
  trend_status: number // 1=Long, -1=Short, 2=Both, 0=Wait
  ema_slopes: {
    d: number[]
    w: number[]
    m: number[]
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

const SYMBOL_NAMES: Record<string, string> = {
  USD: '美元 USD',
  EUR: '欧元 EUR',
  GBP: '英镑 GBP',
  JPY: '日元 JPY',
  AUD: '澳元 AUD',
  CAD: '加元 CAD',
  NZD: '纽元 NZD',
  CHF: '瑞郎 CHF',
  SGD: '新元 SGD',
  MXN: '比索 MXN',
  SEK: '瑞典 SEK',
  NOK: '挪威 NOK',
}

const THRESHOLDS = { flat: 0.001, weak: 0.003, healthy: 0.005 }

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

function SignalIcon({ long, short }: { long: boolean, short: boolean }) {
  if (long && short) return <span>🟡</span>
  if (long) return <span>🟢</span>
  if (short) return <span>🔴</span>
  return <span>⚪</span>
}

export default function Home() {
  const [data, setData] = useState<SnapshotRow[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<string | null>(null)

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
    <main className="p-4 md:p-8">
      <header className="mb-6 text-center">
        <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
          🌐 FXView · 全球汇率上帝视角
        </h1>
        <p className="text-sm text-slate-400 mt-2">
          Last Update: {lastUpdate ? new Date(lastUpdate).toLocaleString() : 'N/A'}
        </p>
      </header>

      <div className="overflow-x-auto rounded-lg border border-slate-700">
        <table className="w-full text-sm">
          <thead className="bg-slate-800/80">
            <tr>
              <th className="px-3 py-2 text-left">货币</th>
              <th className="px-3 py-2 text-center">司令部</th>
              <th className="px-3 py-2 text-center">RSI</th>
              <th className="px-3 py-2 text-center">MACD</th>
              <th className="px-3 py-2 text-center">ADX</th>
              <th className="px-2 py-2 text-center bg-teal-900/30">E20D</th>
              <th className="px-2 py-2 text-center bg-teal-900/30">E50D</th>
              <th className="px-2 py-2 text-center bg-teal-900/30">E100D</th>
              <th className="px-2 py-2 text-center bg-teal-900/30">E200D</th>
              <th className="px-2 py-2 text-center bg-purple-900/30">E20W</th>
              <th className="px-2 py-2 text-center bg-purple-900/30">E50W</th>
              <th className="px-2 py-2 text-center bg-purple-900/30">E100W</th>
              <th className="px-2 py-2 text-center bg-purple-900/30">E200W</th>
              <th className="px-2 py-2 text-center bg-orange-900/30">E20M</th>
              <th className="px-2 py-2 text-center bg-orange-900/30">E50M</th>
              <th className="px-2 py-2 text-center bg-orange-900/30">E100M</th>
              <th className="px-2 py-2 text-center bg-orange-900/30">E200M</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => {
              const d = row.data
              return (
                <tr key={row.symbol} className="border-t border-slate-700 hover:bg-slate-800/50 transition-colors">
                  <td className="px-3 py-2 font-medium text-blue-300">{SYMBOL_NAMES[row.symbol] || row.symbol}</td>
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
                  <SlopeCell slope={d.ema_slopes.d[0]} />
                  <SlopeCell slope={d.ema_slopes.d[1]} />
                  <SlopeCell slope={d.ema_slopes.d[2]} />
                  <SlopeCell slope={d.ema_slopes.d[3]} />
                  {/* Weekly EMAs */}
                  <SlopeCell slope={d.ema_slopes.w[0]} />
                  <SlopeCell slope={d.ema_slopes.w[1]} />
                  <SlopeCell slope={d.ema_slopes.w[2]} />
                  <SlopeCell slope={d.ema_slopes.w[3]} />
                  {/* Monthly EMAs */}
                  <SlopeCell slope={d.ema_slopes.m[0]} />
                  <SlopeCell slope={d.ema_slopes.m[1]} />
                  <SlopeCell slope={d.ema_slopes.m[2]} />
                  <SlopeCell slope={d.ema_slopes.m[3]} />
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <footer className="mt-8 text-center text-xs text-slate-500">
        <p>Powered by Yahoo Finance + Supabase + Vercel</p>
        <p>Data refreshed every hour via GitHub Actions</p>
      </footer>
    </main>
  )
}
