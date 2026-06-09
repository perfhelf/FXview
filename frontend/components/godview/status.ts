const THRESHOLDS = { flat: 0.001, weak: 0.003, healthy: 0.005 }

export function getSlopeStatus(slope: number) {
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

export const DEFAULT_FW_SIGNALS = {
  rsi: { d: [false, false], w: [false, false] },
  macd: { d: [false, false], w: [false, false] },
  adx: { d: [false, false], w: [false, false] },
}
