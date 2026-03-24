import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

/**
 * GET /api/signal-8h
 * 
 * Static API endpoint for 8H trend signals.
 * Returns pre-computed trend/first-wave signals for 53 EIGHTCAP instruments.
 * 
 * Query parameters:
 *   ?symbol=XAUUSD — Filter by specific symbol
 * 
 * Response format:
 * {
 *   "signals": [
 *     { "symbol": "XAUUSD", "trend": "多", "first_wave": "空", ... },
 *     ...
 *   ],
 *   "count": 53,
 *   "updated_at": "2026-03-24T12:00:00Z"
 * }
 * 
 * No authentication required (public read-only data).
 */
export async function GET(request: Request) {
  try {
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
    const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_KEY;

    if (!supabaseUrl || !supabaseKey) {
      return NextResponse.json(
        { error: 'Database configuration missing' },
        { status: 500 }
      );
    }

    const supabase = createClient(supabaseUrl, supabaseKey);

    // Parse query params
    const { searchParams } = new URL(request.url);
    const symbolFilter = searchParams.get('symbol');

    // Build query
    let query = supabase.from('signal_8h').select('symbol, data, updated_at');

    if (symbolFilter) {
      query = query.eq('symbol', symbolFilter.toUpperCase());
    }

    const { data: rows, error } = await query;

    if (error) {
      console.error('Supabase query error:', error);
      return NextResponse.json(
        { error: 'Database query failed' },
        { status: 500 }
      );
    }

    if (!rows || rows.length === 0) {
      return NextResponse.json(
        { signals: [], count: 0, updated_at: null },
        { status: 200 }
      );
    }

    // Extract signal data from JSONB
    const signals = rows.map((row: { symbol: string; data: Record<string, unknown>; updated_at: string }) => ({
      symbol: row.symbol,
      ...row.data,
    }));

    // Get most recent update time
    const latestUpdate = rows.reduce((latest: string, row: { updated_at: string }) => {
      return row.updated_at > latest ? row.updated_at : latest;
    }, rows[0].updated_at);

    return NextResponse.json(
      {
        signals,
        count: signals.length,
        updated_at: latestUpdate,
      },
      {
        status: 200,
        headers: {
          'Cache-Control': 'public, s-maxage=1800, stale-while-revalidate=3600',
        },
      }
    );
  } catch (err) {
    console.error('Signal API error:', err);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
