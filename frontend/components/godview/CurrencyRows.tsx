import { EMA_LABELS, INTERVALS, SYMBOL_NAMES } from './catalog'
import { DEFAULT_FW_SIGNALS } from './status'
import { getTradingViewUrl } from './tradingview'
import type { SnapshotRow, SlopeGroup, TrendPeriod } from './types'
import { SlopeCell } from './SlopeCells'
import { FWBadge, SignalIcon, TrendBadge } from './StatusBadges'

export function CurrencyRows({ row, trendPeriod }: { row: SnapshotRow, trendPeriod: TrendPeriod }) {
  const d = row.data
  const slopes = d.ema_slopes?.[trendPeriod] || d.ema_slopes as unknown as SlopeGroup
  const dailySlopes = slopes?.d || [0, 0, 0, 0]
  const weeklySlopes = slopes?.w || [0, 0, 0, 0]
  const symbol = row.symbol
  const name = SYMBOL_NAMES[symbol] || symbol
  const fwSignals = d.fw_signals || DEFAULT_FW_SIGNALS

  return (
    <>
      <tr className="border-t border-slate-700 hover:bg-slate-800/50 transition-colors">
        <td className="px-2 py-2" rowSpan={2}>
          <div className="flex flex-col">
            <a
              href={getTradingViewUrl(symbol, '30')}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-blue-300 hover:text-blue-100 hover:underline cursor-pointer"
            >
              {name} {symbol}
            </a>
            <div className="flex gap-0.5 mt-1 flex-wrap">
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
        <td className="px-2 py-1 text-center text-xs text-teal-400 font-medium">趋势</td>
        <td className="px-3 py-1 text-center"><TrendBadge status={d.trend_status} /></td>
        <td className="px-3 py-1 text-center">
          <SignalIcon long={d.signals.rsi.d[0]} short={d.signals.rsi.d[1]} />
          <span className="text-[10px] text-slate-500">D</span>
          <SignalIcon long={d.signals.rsi.w[0]} short={d.signals.rsi.w[1]} />
          <span className="text-[10px] text-slate-500">W</span>
        </td>
        <td className="px-3 py-1 text-center">
          <SignalIcon long={d.signals.macd.d[0]} short={d.signals.macd.d[1]} />
          <span className="text-[10px] text-slate-500">D</span>
          <SignalIcon long={d.signals.macd.w[0]} short={d.signals.macd.w[1]} />
          <span className="text-[10px] text-slate-500">W</span>
        </td>
        <td className="px-3 py-1 text-center">
          <SignalIcon long={d.signals.adx.d[0]} short={d.signals.adx.d[1]} />
          <span className="text-[10px] text-slate-500">D</span>
          <SignalIcon long={d.signals.adx.w[0]} short={d.signals.adx.w[1]} />
          <span className="text-[10px] text-slate-500">W</span>
        </td>
        <SlopeCell slope={dailySlopes[0]} />
        <SlopeCell slope={dailySlopes[1]} />
        <SlopeCell slope={dailySlopes[2]} />
        <SlopeCell slope={dailySlopes[3]} />
        <SlopeCell slope={weeklySlopes[0]} />
        <SlopeCell slope={weeklySlopes[1]} />
        <SlopeCell slope={weeklySlopes[2]} />
        <SlopeCell slope={weeklySlopes[3]} />
      </tr>
      <tr className="border-b border-slate-600 hover:bg-slate-800/30 transition-colors bg-slate-800/20">
        <td className="px-2 py-1 text-center text-xs text-cyan-400 font-medium">一浪</td>
        <td className="px-3 py-1 text-center"><FWBadge status={d.fw_status || 0} /></td>
        <td className="px-3 py-1 text-center">
          <SignalIcon long={fwSignals.rsi.d[0]} short={fwSignals.rsi.d[1]} />
          <span className="text-[10px] text-slate-500">D</span>
          <SignalIcon long={fwSignals.rsi.w[0]} short={fwSignals.rsi.w[1]} />
          <span className="text-[10px] text-slate-500">W</span>
        </td>
        <td className="px-3 py-1 text-center">
          <SignalIcon long={fwSignals.macd.d[0]} short={fwSignals.macd.d[1]} />
          <span className="text-[10px] text-slate-500">D</span>
          <SignalIcon long={fwSignals.macd.w[0]} short={fwSignals.macd.w[1]} />
          <span className="text-[10px] text-slate-500">W</span>
        </td>
        <td className="px-3 py-1 text-center">
          <SignalIcon long={fwSignals.adx.d[0]} short={fwSignals.adx.d[1]} />
          <span className="text-[10px] text-slate-500">D</span>
          <SignalIcon long={fwSignals.adx.w[0]} short={fwSignals.adx.w[1]} />
          <span className="text-[10px] text-slate-500">W</span>
        </td>
        {EMA_LABELS.flatMap((label) => [
          <td key={`${label}-d`} className="px-2 py-1 text-center text-xs text-slate-600">-</td>,
          <td key={`${label}-w`} className="px-2 py-1 text-center text-xs text-slate-600">-</td>,
        ])}
      </tr>
    </>
  )
}
