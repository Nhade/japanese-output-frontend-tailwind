<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { watch } from 'vue'

const { locale } = useI18n()

watch(locale, (newLocale) => {
  localStorage.setItem('user-locale', newLocale as string)
})
</script>

<template>
  <div class="relative flex items-center">
    <select
      v-model="locale"
      class="appearance-none bg-transparent py-1 pl-2 pr-6 text-sm font-medium text-zinc-600 dark:text-zinc-200 outline-none cursor-pointer hover:text-zinc-900 dark:hover:text-white transition-colors border border-transparent hover:border-zinc-200 dark:hover:border-white/10 rounded-md focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
    >
      <option value="en">English</option>
      <option value="zh-tw">繁體中文</option>
      <option value="ja">日本語</option>
    </select>
    <div class="pointer-events-none absolute right-1 flex items-center text-zinc-500 dark:text-zinc-400">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4">
        <path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd" />
      </svg>
    </div>
  </div>
</template>
