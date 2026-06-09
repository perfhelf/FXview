import type { TrendPeriod } from './types'

export const SYMBOL_NAMES: Record<string, string> = {
  USD: '美元', EUR: '欧元', GBP: '英镑', JPY: '日元',
  AUD: '澳元', CAD: '加元', NZD: '纽元', CHF: '瑞郎',
  SGD: '新元', MXN: '比索', SEK: '瑞典', NOK: '挪威',
  CNH: '人民币', MYR: '林吉特',
  XAU: '黄金', XAG: '白银', USO: '原油', XCU: '铜', WHEAT: '小麦',
  ZAR: '南非兰特', KRW: '韩元', BRL: '雷亚尔',
  // Stock Indices
  CN50: '中国A50', HK50: '恒生指数', SG30: '新加坡30',
  ASX200: '澳洲200', CA60: '加拿大60',
  NL25: '荷兰25', FRA40: '法国40', GER40: '德国40',
  EUSTX50: '欧洲50', IT40: '意大利40', SWI20: '瑞士20',
  UK100: '英国100',
  SPX500: '标普500', NDQ100: '纳指100', US2000: '罗素2000', US30: '道指30',
  JPN225: '日经225',
}

export const SYMBOL_ORDER = Object.keys(SYMBOL_NAMES)

export const INTERVALS = [
  { label: '1H', value: '60' }, { label: '2H', value: '120' }, { label: '4H', value: '240' },
  { label: '日', value: 'D' }, { label: '周', value: 'W' }, { label: '月', value: 'M' },
]

export const TREND_PERIODS: Array<{ key: TrendPeriod, label: string, period: number }> = [
  { key: 'short', label: '短期趋势', period: 20 },
  { key: 'mid', label: '中期趋势', period: 50 },
  { key: 'long', label: '长期趋势', period: 90 },
]

export const EMA_LABELS = ['EMA20', 'EMA50', 'EMA100', 'EMA200']
