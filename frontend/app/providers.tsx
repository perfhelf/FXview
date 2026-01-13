'use client'

import { createContext, useContext, useEffect, useState } from 'react'

type Theme = 'dark' | 'light' | 'system'

const ThemeContext = createContext<{
    theme: Theme
    setTheme: (theme: Theme) => void
}>({
    theme: 'system',
    setTheme: () => { },
})

export function ThemeProvider({ children }: { children: React.ReactNode }) {
    const [theme, setTheme] = useState<Theme>('system')
    const [mounted, setMounted] = useState(false)

    useEffect(() => {
        setMounted(true)
        const saved = localStorage.getItem('theme') as Theme
        if (saved) {
            setTheme(saved)
        }
    }, [])

    useEffect(() => {
        if (!mounted) return

        const root = window.document.documentElement
        root.classList.remove('light', 'dark')

        if (theme === 'system') {
            const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
            root.classList.add(systemTheme)
        } else {
            root.classList.add(theme)
        }
        localStorage.setItem('theme', theme)
    }, [theme, mounted])

    useEffect(() => {
        const media = window.matchMedia('(prefers-color-scheme: dark)')
        const listener = () => {
            if (theme === 'system') {
                const root = window.document.documentElement
                root.classList.remove('light', 'dark')
                root.classList.add(media.matches ? 'dark' : 'light')
            }
        }
        media.addEventListener('change', listener)
        return () => media.removeEventListener('change', listener)
    }, [theme])

    // Return children immediately to avoid hydration mismatch, 
    // but theme effect runs after mount. 
    // To avoid FOUC, we might render invisible until mounted, 
    // but here we just accept a potential flash or system default.
    // Ideally use next-themes, but this is a quick custom implementation.
    return (
        <ThemeContext.Provider value={{ theme, setTheme }}>
            {children}
        </ThemeContext.Provider>
    )
}

export const useTheme = () => useContext(ThemeContext)
