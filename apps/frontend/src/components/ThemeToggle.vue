<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useThemeStore } from '../stores/theme'

const themeStore = useThemeStore()
const { t } = useI18n()
const isDark = computed(() => themeStore.theme === 'dark')

// Aria label describes the action the click will perform (switch to the
// *other* mode), not the current state.
const ariaLabel = computed(() =>
  isDark.value ? t('chrome.toggle_theme_light') : t('chrome.toggle_theme_dark')
)

const toggle = () => {
  themeStore.toggleTheme()
}
</script>

<template>
  <button
    type="button"
    class="theme-toggle"
    :aria-label="ariaLabel"
    :title="ariaLabel"
    @click="toggle"
  >
    <!-- Sun — shown in dark mode (click returns to light) -->
    <svg
      v-if="isDark"
      class="theme-toggle-icon"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.6"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="m4.93 4.93 1.41 1.41" />
      <path d="m17.66 17.66 1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="m6.34 17.66-1.41 1.41" />
      <path d="m19.07 4.93-1.41 1.41" />
    </svg>

    <!-- Moon — shown in light mode (click advances to dark) -->
    <svg
      v-else
      class="theme-toggle-icon"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.6"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </svg>
  </button>
</template>

<style scoped>
.theme-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 2px;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  cursor: pointer;
  transition: color 160ms ease, border-color 160ms ease, background 160ms ease;
}
.theme-toggle:hover {
  color: var(--foreground);
  border-color: color-mix(in oklab, var(--foreground) 18%, transparent);
}
.theme-toggle:focus-visible {
  outline: none;
  color: var(--foreground);
  border-color: var(--secondary);
  box-shadow: 0 1px 0 0 var(--secondary);
}
.theme-toggle-icon {
  transition: transform 400ms ease;
}
.theme-toggle:hover .theme-toggle-icon {
  transform: rotate(-10deg);
}
</style>
