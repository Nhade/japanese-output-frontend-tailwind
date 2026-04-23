<script setup>
import { computed, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';
import TheHeader from './components/TheHeader.vue';
import TheFooter from './components/TheFooter.vue';
import ToastNotification from './components/ToastNotification.vue';
import { useToastStore } from './stores/toast';
import { useThemeStore } from './stores/theme';

const { locale } = useI18n();
const toastStore = useToastStore();
const route = useRoute();
const themeStore = useThemeStore();

// Theme must initialize once at app mount so bare routes (Login,
// Register — no TheHeader) get the correct theme class too. Previously
// TheHeader owned this and bare routes shipped with no class at all.
onMounted(() => {
  themeStore.initTheme();
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
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <TheFooter v-if="!hideChrome" />
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