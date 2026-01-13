import './globals.css'
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: '鲲侯FXView · 全球汇率上帝视角',
  description: '提供全球汇率实时分析，集成趋势跟随、一浪反转、流动性猎杀三大引擎。通过上帝视角洞察 RSI、MACD、ADX 多周期信号，助您精准把握市场脉搏。',
  keywords: 'FXView, 鲲侯, 汇率分析, 外汇交易, 趋势跟随, 一浪反转, 上帝视角, 交易信号, RSI, MACD, ADX, 全球汇率',
  openGraph: {
    title: '鲲侯FXView · 全球汇率上帝视角',
    description: '提供全球汇率实时分析，集成趋势跟随、一浪反转、流动性猎杀三大引擎。',
    type: 'website',
  },
}

import { ThemeProvider } from './providers'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} bg-white text-slate-900 dark:bg-slate-950 dark:text-slate-200 min-h-screen transition-colors duration-300`}>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  )
}
