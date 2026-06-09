'use client'

import { useState } from 'react'
import { ThemeToggle, TrendPeriodSelector, ViewModeToggle } from './Controls'
import { CurrencyCard } from './CurrencyCard'
import { CurrencyRows } from './CurrencyRows'
import type { TrendPeriod, ViewMode } from './types'
import { useGodViewSnapshot } from './useGodViewSnapshot'

export default function GodViewDashboard() {
  const { data, loading, lastUpdate } = useGodViewSnapshot()
  const [trendPeriod, setTrendPeriod] = useState<TrendPeriod>('short')
  const [viewMode, setViewMode] = useState<ViewMode>('card')

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-xl animate-pulse">Loading GodView...</div>
      </div>
    )
  }

  return (
    <main className="p-4 md:p-8 relative min-h-screen">
      <header className="mb-4">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <h1 className="text-xl sm:text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent text-center sm:text-left">
            🌐 鲲侯FXView · 外汇指数上帝视角
          </h1>
          <ThemeToggle />
        </div>
        <p className="text-sm text-slate-400 mt-2 text-center sm:text-left">
          Last Update: {lastUpdate ? new Date(lastUpdate).toLocaleString() : 'N/A'}
        </p>
      </header>

      <div className="mb-6">
        <TrendPeriodSelector selected={trendPeriod} onSelect={setTrendPeriod} />
        <ViewModeToggle selected={viewMode} onSelect={setViewMode} />
      </div>

      {viewMode === 'table' && (
        <div className="overflow-x-auto rounded-lg border border-slate-700 shadow-xl">
          <table className="w-full text-sm">
            <thead className="bg-slate-800/90 text-slate-200">
              <tr>
                <th className="px-3 py-3 text-left font-semibold" rowSpan={2}>货币</th>
                <th className="px-2 py-2 text-center font-semibold text-xs">引擎</th>
                <th className="px-3 py-2 text-center font-semibold">司令部</th>
                <th className="px-3 py-2 text-center font-semibold text-xs opacity-70">RSI</th>
                <th className="px-3 py-2 text-center font-semibold text-xs opacity-70">MACD</th>
                <th className="px-3 py-2 text-center font-semibold text-xs opacity-70">ADX</th>
                <th className="px-2 py-2 text-center bg-teal-900/40 text-teal-200 text-xs font-mono">20D</th>
                <th className="px-2 py-2 text-center bg-teal-900/40 text-teal-200 text-xs font-mono">50D</th>
                <th className="px-2 py-2 text-center bg-teal-900/40 text-teal-200 text-xs font-mono">100D</th>
                <th className="px-2 py-2 text-center bg-teal-900/40 text-teal-200 text-xs font-mono">200D</th>
                <th className="px-2 py-2 text-center bg-purple-900/40 text-purple-200 text-xs font-mono">20W</th>
                <th className="px-2 py-2 text-center bg-purple-900/40 text-purple-200 text-xs font-mono">50W</th>
                <th className="px-2 py-2 text-center bg-purple-900/40 text-purple-200 text-xs font-mono">100W</th>
                <th className="px-2 py-2 text-center bg-purple-900/40 text-purple-200 text-xs font-mono">200W</th>
              </tr>
            </thead>
            <tbody className="divide-y-0 bg-slate-900/50">
              {data.map((row) => (
                <CurrencyRows key={row.symbol} row={row} trendPeriod={trendPeriod} />
              ))}
            </tbody>
          </table>
        </div>
      )}

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
