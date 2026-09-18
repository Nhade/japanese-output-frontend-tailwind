import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useThemeStore = defineStore('theme', () => {
    const theme = ref<string>('light')

    // Initialize theme
    const initTheme = () => {
        // Dark mode is disabled until a dark palette exists (see
        // shiori-design-system.md §7). Only a few legacy views carry `dark:`
        // utilities, so honouring the OS preference produced half-styled
        // pages (near-white headings on the paper background). Always render
        // light and drop any previously persisted preference.
        theme.value = 'light'
        try {
            localStorage.removeItem('theme')
        } catch {
            /* storage may be unavailable (private mode) — non-fatal */
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
