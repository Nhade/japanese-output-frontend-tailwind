<script setup lang="ts">
import { useAuthStore } from '../stores/auth'
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const isLoggedIn = computed(() => authStore.user_id !== null)

const logout = () => {
  authStore.logout()
  router.push('/login')
}

const isActive = (path: string) => route.path === path
</script>

<template>
  <header class="fixed top-0 z-50 w-full border-b border-white/5 bg-zinc-900/70 backdrop-blur">
    <nav class="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
      <router-link to="/" class="flex items-center gap-2">
        <span class="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-400 font-bold">O</span>
        <span class="text-lg font-semibold text-zinc-100 tracking-wide">OWO</span>
      </router-link>
      <ul class="flex items-center gap-1 text-sm">
        <template v-if="isLoggedIn">
          <li>
            <router-link
              to="/"
              class="rounded-lg px-3 py-2 text-zinc-300 hover:text-white hover:bg-white/5"
              :class="isActive('/') ? 'bg-emerald-500/20 text-emerald-300' : ''"
            >Exercise</router-link>
          </li>
          <li>
            <router-link
              to="/mistakes"
              class="rounded-lg px-3 py-2 text-zinc-300 hover:text-white hover:bg-white/5"
              :class="isActive('/mistakes') ? 'bg-emerald-500/20 text-emerald-300' : ''"
            >Mistakes</router-link>
          </li>
          <li>
            <router-link
              to="/statistics"
              class="rounded-lg px-3 py-2 text-zinc-300 hover:text-white hover:bg-white/5"
              :class="isActive('/statistics') ? 'bg-emerald-500/20 text-emerald-300' : ''"
            >Statistics</router-link>
          </li>
          <li>
            <router-link
              to="/news"
              class="rounded-lg px-3 py-2 text-zinc-300 hover:text-white hover:bg-white/5"
              :class="isActive('/news') ? 'bg-emerald-500/20 text-emerald-300' : ''"
            >News</router-link>
          </li>
          <li class="ml-1 hidden sm:block">
            <a
              href="#"
              @click.prevent="logout"
              class="rounded-lg px-3 py-2 text-zinc-300 hover:text-white hover:bg-white/5"
            >Logout</a>
          </li>
        </template>
        <template v-else>
          <li class="ml-1 hidden sm:block">
            <router-link
              to="/login"
              class="rounded-lg px-3 py-2 text-zinc-300 hover:text-white hover:bg-white/5"
              :class="isActive('/login') ? 'bg-emerald-500/20 text-emerald-300' : ''"
            >Login</router-link>
          </li>
          <li class="hidden sm:block">
            <router-link
              to="/register"
              class="rounded-lg px-3 py-2 text-zinc-300 hover:text-white hover:bg-white/5"
              :class="isActive('/register') ? 'bg-emerald-500/20 text-emerald-300' : ''"
            >Register</router-link>
          </li>
        </template>
      </ul>
    </nav>
  </header>
</template>

<style scoped>
</style>
