'use client'

import { useSyncExternalStore } from 'react'
import { useTheme } from '@/app/providers'
import { TREND_PERIODS } from './catalog'
import type { TrendPeriod, ViewMode } from './types'

export function TrendPeriodSelector({ selected, onSelect }: { selected: TrendPeriod, onSelect: (p: TrendPeriod) => void }) {
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

export function ViewModeToggle({ selected, onSelect }: { selected: ViewMode, onSelect: (m: ViewMode) => void }) {
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

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const isClient = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  )

  if (!isClient) return null

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
