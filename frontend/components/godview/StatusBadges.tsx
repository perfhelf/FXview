export function TrendBadge({ status }: { status: number }) {
  if (status === 1) return <span className="px-2 py-1 rounded bg-green-600/30 text-green-300 text-xs font-bold">趋势:多</span>
  if (status === -1) return <span className="px-2 py-1 rounded bg-red-600/30 text-red-300 text-xs font-bold">趋势:空</span>
  if (status === 2) return <span className="px-2 py-1 rounded bg-yellow-600/30 text-yellow-300 text-xs font-bold">趋势:双向</span>
  return <span className="px-2 py-1 rounded bg-gray-600/30 text-gray-300 text-xs font-bold">趋势:待定</span>
}

export function FWBadge({ status }: { status: number }) {
  if (status === 1) return <span className="px-2 py-1 rounded bg-cyan-600/30 text-cyan-300 text-xs font-bold">反转:多</span>
  if (status === -1) return <span className="px-2 py-1 rounded bg-orange-600/30 text-orange-300 text-xs font-bold">反转:空</span>
  if (status === 2) return <span className="px-2 py-1 rounded bg-pink-600/30 text-pink-300 text-xs font-bold">反转:双向</span>
  return <span className="px-2 py-1 rounded bg-gray-600/30 text-gray-400 text-xs font-bold">反转:待定</span>
}

export function SignalIcon({ long, short }: { long: boolean, short: boolean }) {
  if (long && short) return <span>🟡</span>
  if (long) return <span>🟢</span>
  if (short) return <span>🔴</span>
  return <span>⚪</span>
}
