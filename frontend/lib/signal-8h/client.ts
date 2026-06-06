import { createClient, type SupabaseClient } from '@supabase/supabase-js'

import type { Signal8HDatabaseConfig } from './config'

export function createSignal8HClient(config: Signal8HDatabaseConfig): SupabaseClient {
  return createClient(config.url, config.key)
}
