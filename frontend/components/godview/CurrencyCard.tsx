import { EMA_LABELS, INTERVALS, SYMBOL_NAMES } from './catalog'
import { DEFAULT_FW_SIGNALS } from './status'
import { getTradingViewUrl } from './tradingview'
import type { SnapshotRow, SlopeGroup, TrendPeriod } from './types'
import { SlopeCellDiv } from './SlopeCells'
import { FWBadge, SignalIcon, TrendBadge } from './StatusBadges'

export function CurrencyCard({ row, trendPeriod }: { row: SnapshotRow, trendPeriod: TrendPeriod }) {
  const d = row.data
  const slopes = d.ema_slopes?.[trendPeriod] || d.ema_slopes as unknown as SlopeGroup
  const dailySlopes = slopes?.d || [0, 0, 0, 0]
  const weeklySlopes = slopes?.w || [0, 0, 0, 0]
  const symbol = row.symbol
  const name = SYMBOL_NAMES[symbol] || symbol
  const fwSignals = d.fw_signals || DEFAULT_FW_SIGNALS

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 flex flex-col gap-3 shadow-lg">
      <div className="flex justify-between items-start pb-3 border-b border-slate-800">
        <a
          href={getTradingViewUrl(symbol, '30')}
          target="_blank"
          rel="noopener noreferrer"
          className="flex flex-col cursor-pointer hover:opacity-80 transition-opacity"
        >
          <span className="text-lg font-bold text-slate-100">{symbol}</span>
          <span className="text-xs text-slate-400">{name}</span>
        </a>
        <div className="flex flex-col gap-1 items-end">
          <TrendBadge status={d.trend_status} />
          <FWBadge status={d.fw_status || 0} />
        </div>
      </div>

      <div className="text-[10px] text-teal-400 font-medium text-center -mb-1">趋势跟随</div>
      <div className="grid grid-cols-3 gap-2 text-center bg-slate-800/50 rounded-lg p-2">
        <SignalGroup title="RSI" daily={d.signals.rsi.d} weekly={d.signals.rsi.w} />
        <SignalGroup title="MACD" daily={d.signals.macd.d} weekly={d.signals.macd.w} bordered />
        <SignalGroup title="ADX" daily={d.signals.adx.d} weekly={d.signals.adx.w} bordered />
      </div>

      <div className="text-[10px] text-cyan-400 font-medium text-center -mb-1">一浪反转</div>
      <div className="grid grid-cols-3 gap-2 text-center bg-cyan-900/20 rounded-lg p-2 border border-cyan-800/30">
        <SignalGroup title="RSI" daily={fwSignals.rsi.d} weekly={fwSignals.rsi.w} />
        <SignalGroup title="MACD" daily={fwSignals.macd.d} weekly={fwSignals.macd.w} bordered />
        <SignalGroup title="ADX" daily={fwSignals.adx.d} weekly={fwSignals.adx.w} bordered />
      </div>

      <div className="space-y-3 text-sm bg-slate-800/30 rounded-lg p-2">
        <div>
          <div className="text-xs text-teal-400/70 font-mono mb-1">Daily</div>
          <div className="flex gap-1">
            {dailySlopes.map((s, i) => (
              <SlopeCellDiv key={i} slope={s} label={EMA_LABELS[i]} />
            ))}
          </div>
        </div>
        <div className="border-t border-slate-800/50 pt-2">
          <div className="text-xs text-purple-400/70 font-mono mb-1">Weekly</div>
          <div className="flex gap-1">
            {weeklySlopes.map((s, i) => (
              <SlopeCellDiv key={i} slope={s} label={EMA_LABELS[i]} />
            ))}
          </div>
        </div>
      </div>

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

function SignalGroup({
  title,
  daily,
  weekly,
  bordered = false,
}: {
  title: string
  daily: boolean[]
  weekly: boolean[]
  bordered?: boolean
}) {
  return (
    <div className={`flex flex-col items-center ${bordered ? 'border-l border-slate-700/50' : ''}`}>
      <div className="text-xs text-slate-500 mb-1">{title}</div>
      <div className="flex gap-1">
        <div><SignalIcon long={daily[0]} short={daily[1]} /><span className="text-[10px] text-slate-600 block leading-none">D</span></div>
        <div><SignalIcon long={weekly[0]} short={weekly[1]} /><span className="text-[10px] text-slate-600 block leading-none">W</span></div>
      </div>
    </div>
  )
}
