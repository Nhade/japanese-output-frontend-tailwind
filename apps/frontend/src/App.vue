<script setup>
import { computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';
import TheHeader from './components/TheHeader.vue';
import TheFooter from './components/TheFooter.vue';
import ToastNotification from './components/ToastNotification.vue';
import { useToastStore } from './stores/toast';

const { locale } = useI18n();
const toastStore = useToastStore();
const route = useRoute();

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
    <main
      class="main-content bg-zinc-50 dark:bg-zinc-900 dark:bg-linear-to-b dark:from-zinc-900 dark:to-zinc-950 transition-colors duration-300"
      :class="{ 'pt-16': !hideChrome }">
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