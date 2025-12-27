<script setup lang="ts">
import { useThemeStore } from '../stores/theme'
import { computed } from 'vue'

const themeStore = useThemeStore()
const isDark = computed(() => themeStore.theme === 'dark')

const toggle = () => {
  themeStore.toggleTheme()
}
</script>

<template>
  <button
    @click="toggle"
    class="flex h-9 w-9 items-center justify-center rounded-lg border border-transparent text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 active:bg-zinc-200 dark:text-zinc-400 dark:hover:bg-white/10 dark:hover:text-zinc-200 dark:active:bg-white/20 transition-all"
    aria-label="Toggle Theme"
  >
    <!-- Sun (for switching to light, shown when dark) -->
    <svg 
      v-if="isDark" 
      xmlns="http://www.w3.org/2000/svg" 
      width="20" height="20" viewBox="0 0 24 24" 
      fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
      class="transition-transform duration-500 rotate-0"
    >
      <circle cx="12" cy="12" r="4"></circle>
      <path d="M12 2v2"></path>
      <path d="M12 20v2"></path>
      <path d="m4.93 4.93 1.41 1.41"></path>
      <path d="m17.66 17.66 1.41 1.41"></path>
      <path d="M2 12h2"></path>
      <path d="M20 12h2"></path>
      <path d="m6.34 17.66-1.41 1.41"></path>
      <path d="m19.07 4.93-1.41 1.41"></path>
    </svg>

    <!-- Moon (for switching to dark, shown when light) -->
    <svg 
      v-else 
      xmlns="http://www.w3.org/2000/svg" 
      width="20" height="20" viewBox="0 0 24 24" 
      fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
      class="transition-transform duration-500 rotate-0"
    >
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>
    </svg>
  </button>
</template>
