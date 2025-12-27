<script setup lang="ts">
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/theme'
import ThemeToggle from './ThemeToggle.vue'
import { computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const authStore = useAuthStore()
const themeStore = useThemeStore()
const router = useRouter()
const route = useRoute()

const isLoggedIn = computed(() => authStore.user_id !== null)

const logout = () => {
  authStore.logout()
  router.push('/login')
}

// Initialize theme on mount
onMounted(() => {
  themeStore.initTheme()
})

const isActive = (path: string) => route.path === path
</script>

<template>
  <header
    class="fixed top-0 z-50 w-full border-b backdrop-blur transition-colors duration-300 border-zinc-200 bg-white/70 dark:border-white/10 dark:bg-zinc-900/50">
    <nav class="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
      <router-link to="/" class="flex items-center gap-2">
        <span
          class="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:bg-emerald-400/15 dark:text-emerald-200 font-bold transition-colors">O</span>
        <span class="text-lg font-semibold tracking-wide text-zinc-900 dark:text-zinc-100 transition-colors">OWO</span>
      </router-link>
      <div class="flex items-center gap-2">
        <ul class="flex items-center gap-1 text-sm">
          <template v-if="isLoggedIn">
            <li>
              <router-link to="/" class="rounded-lg px-3 py-2 transition-colors hover:bg-zinc-100 dark:hover:bg-white/7"
                :class="isActive('/') ? 'bg-emerald-500/10 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-200' : 'text-zinc-600 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-white'">Exercise</router-link>
            </li>
            <li>
              <router-link to="/mistakes"
                class="rounded-lg px-3 py-2 transition-colors hover:bg-zinc-100 dark:hover:bg-white/7"
                :class="isActive('/mistakes') ? 'bg-emerald-500/10 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-200' : 'text-zinc-600 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-white'">Mistakes</router-link>
            </li>
            <li>
              <router-link to="/statistics"
                class="rounded-lg px-3 py-2 transition-colors hover:bg-zinc-100 dark:hover:bg-white/7"
                :class="isActive('/statistics') ? 'bg-emerald-500/10 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-200' : 'text-zinc-600 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-white'">Statistics</router-link>
            </li>
            <li>
              <router-link to="/news"
                class="rounded-lg px-3 py-2 transition-colors hover:bg-zinc-100 dark:hover:bg-white/7"
                :class="isActive('/news') ? 'bg-emerald-500/10 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-200' : 'text-zinc-600 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-white'">News</router-link>
            </li>
            <li class="ml-1 hidden sm:block">
              <a href="#" @click.prevent="logout"
                class="rounded-lg px-3 py-2 text-zinc-600 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-white/7 transition-colors">Logout</a>
            </li>
          </template>
          <template v-else>
            <li class="ml-1 hidden sm:block">
              <router-link to="/login"
                class="rounded-lg px-3 py-2 transition-colors hover:bg-zinc-100 dark:hover:bg-white/7"
                :class="isActive('/login') ? 'bg-emerald-500/10 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-200' : 'text-zinc-600 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-white'">Login</router-link>
            </li>
            <li class="hidden sm:block">
              <router-link to="/register"
                class="rounded-lg px-3 py-2 transition-colors hover:bg-zinc-100 dark:hover:bg-white/7"
                :class="isActive('/register') ? 'bg-emerald-500/10 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-200' : 'text-zinc-600 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-white'">Register</router-link>
            </li>
          </template>
        </ul>
        <!-- Theme Toggle -->
        <div class="ml-2 pl-2 border-l border-zinc-200 dark:border-white/10">
          <ThemeToggle />
        </div>
      </div>
    </nav>
  </header>
</template>

<style scoped></style>
