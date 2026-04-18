<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import { useThemeStore } from '../stores/theme';

import ThemeToggle from './ThemeToggle.vue';
import LanguageSelector from './LanguageSelector.vue';

const authStore = useAuthStore();
const themeStore = useThemeStore();
const router = useRouter();
const route = useRoute();

const isLoggedIn = computed(() => authStore.user_id !== null);

function logout() {
  authStore.logout();
  router.push('/login');
}

onMounted(() => {
  themeStore.initTheme();
});

// Exercise is mounted at "/", so treat any descendant of "/" that isn't
// another top-level route as the active one.
function isActive(path: string): boolean {
  if (path === '/') return route.path === '/';
  return route.path === path || route.path.startsWith(`${path}/`);
}

const primaryLinks = [
  { to: '/', key: 'exercise' },
  { to: '/news', key: 'news' },
  { to: '/videos', key: 'videos' },
  { to: '/chat', key: 'chat' },
  { to: '/mistakes', key: 'mistakes' },
  { to: '/statistics', key: 'statistics' },
] as const;
</script>

<template>
  <header class="top-nav">
    <nav class="top-nav-inner">
      <!-- Brand ---------------------------------------------- -->
      <router-link to="/" class="brand" aria-label="Shiori">
        <img src="/shiori_no_romaji.png" class="brand-mark" alt="" aria-hidden="true" />
        <span class="brand-name">Shiori</span>
      </router-link>

      <!-- Primary nav ---------------------------------------- -->
      <ul v-if="isLoggedIn" class="nav-links">
        <li v-for="link in primaryLinks" :key="link.to">
          <router-link
            :to="link.to"
            class="nav-link"
            :class="{ 'is-active': isActive(link.to) }"
          >
            {{ $t(`nav.${link.key}`) }}
          </router-link>
        </li>
      </ul>
      <ul v-else class="nav-links">
        <li>
          <router-link
            to="/login"
            class="nav-link"
            :class="{ 'is-active': isActive('/login') }"
          >
            {{ $t('nav.login') }}
          </router-link>
        </li>
        <li>
          <router-link
            to="/register"
            class="nav-link"
            :class="{ 'is-active': isActive('/register') }"
          >
            {{ $t('nav.register') }}
          </router-link>
        </li>
      </ul>

      <!-- Tail: language + theme + logout -------------------- -->
      <div class="nav-tail">
        <LanguageSelector />
        <ThemeToggle />
        <button
          v-if="isLoggedIn"
          type="button"
          class="nav-logout"
          @click="logout"
        >
          {{ $t('nav.logout') }}
        </button>
      </div>
    </nav>
  </header>
</template>

<style scoped>
.top-nav {
  position: fixed;
  top: 0; left: 0;
  z-index: 50;
  width: 100%;
  background: var(--background);
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 10%, transparent);
}

.top-nav-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  padding: 14px 32px;
  max-width: 1400px;
  margin: 0 auto;
}
@media (max-width: 720px) {
  .top-nav-inner { padding: 12px 16px; gap: 16px; }
}

/* Brand --------------------------------------------------- */
.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--foreground);
  flex-shrink: 0;
}
.brand-mark {
  width: 28px;
  height: 28px;
  object-fit: contain;
}
.brand-name {
  font-family: var(--font-serif);
  font-size: 1.1rem;
  letter-spacing: 0.04em;
  color: var(--foreground);
}
@media (max-width: 720px) {
  .brand-name { display: none; }
}

/* Primary nav --------------------------------------------- */
.nav-links {
  display: flex;
  gap: 26px;
  align-items: center;
  margin: 0;
  padding: 0;
  list-style: none;
  min-width: 0;
  flex-wrap: wrap;
}
.nav-link {
  font-family: var(--font-serif);
  font-size: 0.98rem;
  letter-spacing: 0.01em;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  padding: 6px 0;
  border-bottom: 1px solid transparent;
  transition: color 180ms ease, border-color 180ms ease;
  text-decoration: none;
  white-space: nowrap;
  display: inline-block;
}
.nav-link:hover { color: var(--foreground); }
.nav-link.is-active {
  color: var(--foreground);
  border-bottom-color: var(--secondary);
  font-weight: 500;
  font-style: italic;
}
@media (max-width: 960px) {
  .nav-links { gap: 18px; }
  .nav-link { font-size: 0.9rem; }
}
@media (max-width: 720px) {
  .nav-links { gap: 12px; }
  .nav-link { font-size: 0.82rem; }
}

/* Tail -------------------------------------------------- */
.nav-tail {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 16px;
  border-left: 1px solid color-mix(in oklab, var(--foreground) 8%, transparent);
  flex-shrink: 0;
}
.nav-logout {
  font-family: var(--font-sans);
  font-size: 0.68rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  background: none;
  border: none;
  padding: 8px 2px;
  margin-left: 4px;
  cursor: pointer;
  border-bottom: 1px solid transparent;
  transition: color 160ms ease, border-color 160ms ease;
}
.nav-logout:hover {
  color: var(--foreground);
  border-bottom-color: var(--secondary);
}
@media (max-width: 720px) {
  .nav-logout { display: none; }
  .nav-tail { padding-left: 10px; gap: 4px; }
}
</style>
