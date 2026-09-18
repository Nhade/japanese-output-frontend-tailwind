<script setup>
import { computed, onMounted, onUnmounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';
import TheHeader from './components/TheHeader.vue';
import TheFooter from './components/TheFooter.vue';
import ToastNotification from './components/ToastNotification.vue';
import GuestBanner from './components/GuestBanner.vue';
import PreviewLimitDialog from './components/PreviewLimitDialog.vue';
import AboutDrawer from './components/about/AboutDrawer.vue';
import { UNAUTHORIZED_EVENT } from './lib/api';
import { installTour, startTour } from './lib/tour';
import { useAuthStore } from './stores/auth';
import { useToastStore } from './stores/toast';
import { useThemeStore } from './stores/theme';

const { locale, t, te } = useI18n();
const toastStore = useToastStore();
const route = useRoute();
const router = useRouter();
const themeStore = useThemeStore();
const authStore = useAuthStore();

// The auth store clears the session on 401 (its listener is registered in
// main.ts, so it runs first). If that session was a guest preview, restart
// the preview instead of dropping the visitor on the login form.
function onUnauthorized() {
  if (authStore.lastSessionWasGuest && route.name !== 'preview') {
    router.replace({ name: 'preview', query: { expired: '1' } });
  }
}

// The guided tour needs the router (it moves between pages) and i18n.
installTour({ router, t, te });

// `/preview` lands on Today with `?tour=1`; strip the flag and start.
watch(() => route.query.tour, (value) => {
  if (value !== '1' || !authStore.isAuthenticated) return;
  const { tour: _tour, ...rest } = route.query;
  router.replace({ path: route.path, query: rest }).then(() => startTour());
}, { immediate: true });

// Theme must initialize once at app mount so bare routes (Login,
// Register — no TheHeader) get the correct theme class too. Previously
// TheHeader owned this and bare routes shipped with no class at all.
onMounted(() => {
  themeStore.initTheme();
  window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
});

onUnmounted(() => {
  window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
});

// Routes (Login, Register) set meta.hideChrome to opt out of the
// global header + footer so their editorial layout can go full-bleed.
const hideChrome = computed(() => !!route.meta?.hideChrome);

// Map internal locales to BCP 47 standard codes for fonts
const localeMap = {
  'ja': 'ja',
  'zh-tw': 'zh-Hant',
  'en': 'en'
};

// Update <html> lang attribute when locale changes
watch(locale, (newLocale) => {
  const lang = localeMap[newLocale] || newLocale;
  document.documentElement.lang = lang;
}, { immediate: true });
</script>

<template>
  <div id="app-container" class="overscroll-contain" :class="{ 'is-bare': hideChrome }">
    <TheHeader v-if="!hideChrome" />
    <ToastNotification :show="toastStore.show" :message="toastStore.message" :type="toastStore.type"
      @close="toastStore.close" />
    <main class="main-content" :class="{ 'has-chrome': !hideChrome }">
      <GuestBanner v-if="!hideChrome && authStore.isGuest" />
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <TheFooter v-if="!hideChrome" />
    <PreviewLimitDialog />
    <AboutDrawer />
  </div>
</template>

<style>
/* Main surface — warm paper by default. The top offset uses --topnav-h
   so it stays in sync if the header height is ever retuned in the
   tokens. Bare routes (hideChrome) opt out of both. */
.main-content {
  background: var(--background);
  color: var(--foreground);
  transition: background-color 300ms ease, color 300ms ease;
}
.main-content.has-chrome {
  padding-top: var(--topnav-h);
  padding-bottom: var(--bottomnav-h);
}

.page-enter-active,
.page-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.page-enter-from,
.page-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
