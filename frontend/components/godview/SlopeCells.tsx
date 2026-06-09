import { getSlopeStatus } from './status'

export function SlopeCell({ slope }: { slope: number }) {
  const { icon, text, color } = getSlopeStatus(slope)
  return (
    <td className={`px-2 py-1 text-center text-xs ${color}`}>
      <div>{icon} {slope.toFixed(4)}</div>
      <div className="text-[10px] opacity-70">{text}</div>
    </td>
  )
}

export function SlopeCellDiv({ slope, label }: { slope: number, label?: string }) {
  const { icon, text, color } = getSlopeStatus(slope)
  return (
    <div className={`text-center text-xs ${color} flex-1`}>
      {label && <div className="text-[9px] text-slate-500 font-mono mb-0.5">{label}</div>}
      <div>{icon} {slope.toFixed(4)}</div>
      <div className="text-[10px] opacity-70">{text}</div>
    </div>
  )
}
