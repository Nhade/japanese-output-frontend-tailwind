import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useThemeStore = defineStore('theme', () => {
    const theme = ref<string>('light')

    // Initialize theme
    const initTheme = () => {
        // 1. Check localStorage
        const storedTheme = localStorage.getItem('theme')
        if (storedTheme) {
            theme.value = storedTheme
        } else {
            // 2. Fallback to system preference
            if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                theme.value = 'dark'
            } else {
                theme.value = 'light'
            }
        }
        applyTheme()
    }

    const applyTheme = () => {
        const html = document.documentElement
        if (theme.value === 'dark') {
            html.classList.add('dark')
        } else {
            html.classList.remove('dark')
        }
    }

    const toggleTheme = () => {
        theme.value = theme.value === 'light' ? 'dark' : 'light'
        applyTheme()
        localStorage.setItem('theme', theme.value)
    }

    // Watch for system changes if no preference is set (optional, simplistic for now)
    // For now, we stick to the user's manual override or initial system check.

    return {
        theme,
        initTheme,
        toggleTheme
    }
})
