<script setup>
import { watch } from 'vue';
import { useI18n } from 'vue-i18n';
import TheHeader from './components/TheHeader.vue';
import TheFooter from './components/TheFooter.vue';

const { locale } = useI18n();

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
  <div id="app-container" class="overscroll-contain">
    <TheHeader />
    <main
      class="main-content pt-16 min-h-screen bg-zinc-50 dark:bg-zinc-900 dark:bg-gradient-to-b dark:from-zinc-900 dark:to-zinc-950 transition-colors duration-300">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <TheFooter />
  </div>
</template>

<style>
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