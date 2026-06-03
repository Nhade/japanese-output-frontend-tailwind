<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import {
  BarChart3,
  BookOpen,
  Clapperboard,
  Home,
  Menu,
  MessageCircle,
  PenLine,
  RotateCcw,
  Sparkles,
} from 'lucide-vue-next';
import { useAuthStore } from '../stores/auth';

import ThemeToggle from './ThemeToggle.vue';
import LanguageSelector from './LanguageSelector.vue';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();

const isLoggedIn = computed(() => authStore.isAuthenticated);
const openTopMenu = ref<string | null>(null);
const mobileMoreOpen = ref(false);

function logout() {
  authStore.logout();
  openTopMenu.value = null;
  mobileMoreOpen.value = false;
  router.push('/login');
}

interface NavChild {
  to: string;
  key: string;
  descriptionKey?: string;
  icon?: unknown;
  activeNames: string[];
}

interface NavItem {
  id: string;
  to?: string;
  key: string;
  icon: unknown;
  activeNames: string[];
  children?: NavChild[];
}

const studyChildren: NavChild[] = [
  {
    to: '/study/exercise',
    key: 'adaptive',
    descriptionKey: 'adaptive_desc',
    icon: Sparkles,
    activeNames: ['exercise'],
  },
  {
    to: '/practice',
    key: 'practice',
    descriptionKey: 'practice_desc',
    icon: RotateCcw,
    activeNames: ['practice'],
  },
];

const progressChildren: NavChild[] = [
  {
    to: '/mistakes',
    key: 'mistakes',
    descriptionKey: 'mistakes_desc',
    icon: RotateCcw,
    activeNames: ['mistakes'],
  },
  {
    to: '/statistics',
    key: 'statistics',
    descriptionKey: 'statistics_desc',
    icon: BarChart3,
    activeNames: ['statistics'],
  },
];

const primaryNav: NavItem[] = [
  {
    id: 'today',
    to: '/',
    key: 'today',
    icon: Home,
    activeNames: ['today'],
  },
  {
    id: 'study',
    key: 'study',
    icon: PenLine,
    activeNames: ['exercise', 'practice'],
    children: studyChildren,
  },
  {
    id: 'read',
    to: '/news',
    key: 'read',
    icon: BookOpen,
    activeNames: ['news-list', 'news-reader'],
  },
  {
    id: 'watch',
    to: '/videos',
    key: 'watch',
    icon: Clapperboard,
    activeNames: ['video-list', 'video-study'],
  },
  {
    id: 'tutor',
    to: '/chat',
    key: 'tutor',
    icon: MessageCircle,
    activeNames: ['chat'],
  },
  {
    id: 'progress',
    key: 'progress',
    icon: BarChart3,
    activeNames: ['mistakes', 'statistics'],
    children: progressChildren,
  },
];

const mobileTabs = [
  primaryNav[0],
  primaryNav[1],
  primaryNav[2],
  primaryNav[4],
] as NavItem[];

const mobileMoreItems: NavChild[] = [
  // Practice is the one study mode not surfaced as a bottom tab (the Study
  // tab goes straight to the adaptive exercise), so expose it here.
  studyChildren[1],
  {
    to: '/videos',
    key: 'watch',
    icon: Clapperboard,
    activeNames: ['video-list', 'video-study'],
  },
  ...progressChildren,
];

function routeName(): string {
  return typeof route.name === 'string' ? route.name : '';
}

function isActive(item: NavItem | NavChild): boolean {
  return item.activeNames.includes(routeName());
}

function primaryTarget(item: NavItem): string {
  return item.to ?? item.children?.[0]?.to ?? '/';
}

function toggleTopMenu(id: string) {
  openTopMenu.value = openTopMenu.value === id ? null : id;
}

function closeMenus() {
  openTopMenu.value = null;
  mobileMoreOpen.value = false;
}

watch(() => route.fullPath, closeMenus);
</script>

<template>
  <header class="top-nav">
    <nav class="top-nav-inner" :aria-label="$t('nav.primary')">
      <router-link to="/" class="brand" aria-label="Shiori">
        <img src="/shiori_no_romaji.png" class="brand-mark" alt="" aria-hidden="true" />
        <span class="brand-name">Shiori</span>
      </router-link>

      <ul v-if="isLoggedIn" class="nav-links">
        <li
          v-for="item in primaryNav"
          :key="item.id"
          class="nav-item"
          :class="{ 'has-menu': item.children }"
          @mouseenter="item.children && (openTopMenu = item.id)"
          @mouseleave="item.children && (openTopMenu = null)"
        >
          <router-link
            v-if="!item.children"
            :to="primaryTarget(item)"
            class="nav-link"
            :class="{ 'is-active': isActive(item) }"
          >
            <component :is="item.icon" class="nav-link-icon" aria-hidden="true" />
            <span>{{ $t(`nav.${item.key}`) }}</span>
          </router-link>

          <template v-else>
            <button
              type="button"
              class="nav-link nav-menu-trigger"
              :class="{ 'is-active': isActive(item), 'is-open': openTopMenu === item.id }"
              :aria-expanded="openTopMenu === item.id"
              aria-haspopup="menu"
              @click="toggleTopMenu(item.id)"
            >
              <component :is="item.icon" class="nav-link-icon" aria-hidden="true" />
              <span>{{ $t(`nav.${item.key}`) }}</span>
            </button>

            <div
              v-if="openTopMenu === item.id"
              class="nav-menu"
              role="menu"
            >
              <router-link
                v-for="child in item.children"
                :key="child.to"
                :to="child.to"
                class="nav-menu-link"
                :class="{ 'is-active': isActive(child) }"
                role="menuitem"
              >
                <component :is="child.icon" class="nav-menu-icon" aria-hidden="true" />
                <span>
                  <span class="nav-menu-title">{{ $t(`nav.${child.key}`) }}</span>
                  <span v-if="child.descriptionKey" class="nav-menu-desc">
                    {{ $t(`nav.${child.descriptionKey}`) }}
                  </span>
                </span>
              </router-link>
            </div>
          </template>
        </li>
      </ul>
      <ul v-else class="nav-links auth-links">
        <li>
          <router-link
            to="/login"
            class="nav-link"
            :class="{ 'is-active': route.name === 'login' }"
          >
            {{ $t('nav.login') }}
          </router-link>
        </li>
        <li>
          <router-link
            to="/register"
            class="nav-link"
            :class="{ 'is-active': route.name === 'register' }"
          >
            {{ $t('nav.register') }}
          </router-link>
        </li>
      </ul>

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

  <nav
    v-if="isLoggedIn"
    class="mobile-tabs"
    :aria-label="$t('nav.mobile')"
  >
    <router-link
      v-for="item in mobileTabs"
      :key="item.id"
      :to="primaryTarget(item)"
      class="mobile-tab"
      :class="{ 'is-active': isActive(item) }"
    >
      <component :is="item.icon" class="mobile-tab-icon" aria-hidden="true" />
      <span>{{ $t(`nav.${item.key}`) }}</span>
    </router-link>

    <button
      type="button"
      class="mobile-tab"
      :class="{ 'is-active': mobileMoreOpen || isActive(primaryNav[3]) || isActive(primaryNav[5]) }"
      :aria-expanded="mobileMoreOpen"
      aria-haspopup="menu"
      @click="mobileMoreOpen = !mobileMoreOpen"
    >
      <Menu class="mobile-tab-icon" aria-hidden="true" />
      <span>{{ $t('nav.more') }}</span>
    </button>

    <div v-if="mobileMoreOpen" class="mobile-more" role="menu">
      <router-link
        v-for="item in mobileMoreItems"
        :key="item.to"
        :to="item.to"
        class="mobile-more-link"
        :class="{ 'is-active': isActive(item) }"
        role="menuitem"
      >
        <component :is="item.icon" class="mobile-more-icon" aria-hidden="true" />
        <span>{{ $t(`nav.${item.key}`) }}</span>
      </router-link>
      <button type="button" class="mobile-more-link" role="menuitem" @click="logout">
        <Menu class="mobile-more-icon" aria-hidden="true" />
        <span>{{ $t('nav.logout') }}</span>
      </button>
    </div>
  </nav>
</template>

<style scoped>
.top-nav {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 50;
  width: 100%;
  height: var(--topnav-h);
  background: color-mix(in oklab, var(--background) 96%, transparent);
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 10%, transparent);
  -webkit-backdrop-filter: blur(14px);
  backdrop-filter: blur(14px);
}

.top-nav-inner {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  padding: 0 32px;
  max-width: 1400px;
  margin: 0 auto;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--foreground);
  flex-shrink: 0;
  text-decoration: none;
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

.nav-links {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
  margin: 0;
  padding: 0;
  list-style: none;
  min-width: 0;
  flex: 1 1 auto;
}

.auth-links {
  justify-content: flex-end;
}

.nav-item {
  position: relative;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 34px;
  padding: 7px 10px;
  border: 1px solid transparent;
  border-radius: 3px;
  background: transparent;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  font-family: var(--font-sans);
  font-size: 0.78rem;
  letter-spacing: 0.04em;
  text-decoration: none;
  white-space: nowrap;
  cursor: pointer;
  transition: color 160ms ease, border-color 160ms ease, background 160ms ease;
}

.nav-link:hover,
.nav-link.is-open {
  color: var(--foreground);
  background: var(--surface-container-low);
}

.nav-link.is-active {
  color: var(--primary);
  border-color: color-mix(in oklab, var(--secondary) 55%, transparent);
  background: color-mix(in oklab, var(--secondary) 7%, transparent);
}

.nav-link-icon {
  width: 15px;
  height: 15px;
  stroke-width: 1.8;
}

.nav-menu-trigger {
  appearance: none;
}

.nav-menu {
  position: absolute;
  top: calc(100% + 10px);
  left: 50%;
  transform: translateX(-50%);
  min-width: 250px;
  padding: 8px;
  background: var(--background);
  border: 1px solid color-mix(in oklab, var(--foreground) 12%, transparent);
  box-shadow: 0 18px 40px color-mix(in oklab, var(--foreground) 10%, transparent);
  z-index: 60;
}

.nav-menu::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: -12px;
  height: 12px;
}

.nav-menu-link {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr);
  gap: 12px;
  padding: 12px;
  color: var(--foreground);
  text-decoration: none;
  border-radius: 2px;
}

.nav-menu-link:hover,
.nav-menu-link.is-active {
  background: var(--surface-container-low);
}

.nav-menu-link.is-active .nav-menu-title,
.nav-menu-link.is-active .nav-menu-icon {
  color: var(--primary);
}

.nav-menu-icon {
  width: 17px;
  height: 17px;
  margin-top: 2px;
  color: color-mix(in oklab, var(--foreground) 52%, transparent);
}

.nav-menu-title,
.nav-menu-desc {
  display: block;
}

.nav-menu-title {
  font-family: var(--font-serif);
  font-size: 0.98rem;
  color: var(--foreground);
}

.nav-menu-desc {
  margin-top: 4px;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.78rem;
  line-height: 1.45;
  color: color-mix(in oklab, var(--foreground) 58%, transparent);
}

.nav-tail {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 14px;
  border-left: 1px solid color-mix(in oklab, var(--foreground) 8%, transparent);
  flex-shrink: 0;
}

.nav-logout {
  font-family: var(--font-sans);
  font-size: 0.68rem;
  letter-spacing: 0.18em;
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

.mobile-tabs {
  display: none;
}

@media (max-width: 980px) {
  .top-nav-inner {
    padding: 0 20px;
    gap: 16px;
  }

  .nav-links {
    display: none;
  }

  .nav-tail {
    margin-left: auto;
  }

  .nav-logout {
    display: none;
  }

  .mobile-tabs {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 55;
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    min-height: var(--bottomnav-h);
    padding: 6px max(10px, env(safe-area-inset-right)) max(6px, env(safe-area-inset-bottom)) max(10px, env(safe-area-inset-left));
    background: color-mix(in oklab, var(--background) 97%, transparent);
    border-top: 1px solid color-mix(in oklab, var(--foreground) 12%, transparent);
    -webkit-backdrop-filter: blur(14px);
    backdrop-filter: blur(14px);
  }

  .mobile-tab {
    display: inline-flex;
    min-width: 0;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    min-height: 46px;
    border: 1px solid transparent;
    border-radius: 3px;
    background: transparent;
    color: color-mix(in oklab, var(--foreground) 58%, transparent);
    font-family: var(--font-sans);
    font-size: 0.66rem;
    letter-spacing: 0.02em;
    text-decoration: none;
    cursor: pointer;
  }

  .mobile-tab.is-active {
    color: var(--primary);
    background: color-mix(in oklab, var(--secondary) 8%, transparent);
    border-color: color-mix(in oklab, var(--secondary) 40%, transparent);
  }

  .mobile-tab-icon {
    width: 18px;
    height: 18px;
    stroke-width: 1.8;
  }

  .mobile-more {
    position: absolute;
    right: 12px;
    bottom: calc(100% + 10px);
    width: min(260px, calc(100vw - 24px));
    padding: 8px;
    background: var(--background);
    border: 1px solid color-mix(in oklab, var(--foreground) 12%, transparent);
    box-shadow: 0 -18px 40px color-mix(in oklab, var(--foreground) 11%, transparent);
  }

  .mobile-more-link {
    width: 100%;
    display: grid;
    grid-template-columns: 22px minmax(0, 1fr);
    gap: 12px;
    align-items: center;
    padding: 12px;
    border: none;
    background: transparent;
    color: var(--foreground);
    text-align: left;
    text-decoration: none;
    font-family: var(--font-serif);
    font-size: 1rem;
    cursor: pointer;
  }

  .mobile-more-link:hover,
  .mobile-more-link.is-active {
    background: var(--surface-container-low);
  }

  .mobile-more-link.is-active {
    color: var(--primary);
  }

  .mobile-more-icon {
    width: 17px;
    height: 17px;
    color: color-mix(in oklab, var(--foreground) 54%, transparent);
  }
}

@media (max-width: 520px) {
  .brand-name {
    display: none;
  }

  .top-nav-inner {
    padding: 0 14px;
  }

  .nav-tail {
    padding-left: 10px;
    gap: 4px;
  }
}
</style>
