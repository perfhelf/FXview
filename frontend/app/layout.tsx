import './globals.css'
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'FXView · GodView',
  description: 'Global Currency Strength Dashboard',
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
