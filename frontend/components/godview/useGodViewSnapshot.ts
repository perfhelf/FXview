'use client'

import { useEffect, useState } from 'react'
import { getSupabaseClient } from '@/lib/supabase'
import { SYMBOL_ORDER } from './catalog'
import type { SnapshotRow } from './types'

export function useGodViewSnapshot() {
  const [data, setData] = useState<SnapshotRow[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<string | null>(null)

  useEffect(() => {
    async function fetchData() {
      const supabase = getSupabaseClient()

      if (!supabase) {
        console.warn('Supabase configuration missing; GodView snapshot is unavailable.')
        setLoading(false)
        return
      }

      const { data: rows, error } = await supabase
        .from('godview_snapshot')
        .select('*')

      if (error) {
        console.error('Error fetching data:', error)
        setLoading(false)
        return
      }

      if (rows && rows.length > 0) {
        const sorted = rows.sort((a, b) => SYMBOL_ORDER.indexOf(a.symbol) - SYMBOL_ORDER.indexOf(b.symbol))
        setData(sorted as SnapshotRow[])
        // Prefer explicit last_update from payload (JSON), fallback to SQL row updated_at
        const payloadTime = rows[0]?.data?.last_update
        setLastUpdate(payloadTime || rows[0]?.updated_at)
      }
      setLoading(false)
    }

    fetchData()
    const interval = setInterval(fetchData, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  return { data, loading, lastUpdate }
}
