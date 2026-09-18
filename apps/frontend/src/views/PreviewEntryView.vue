<script setup lang="ts">
// Entry point for the guest preview. This is the URL linked from outside
// (`/preview`, optionally `?lang=zh-tw`): it mints a guest session, then
// lands on Today. It is also where an expired guest is sent to start over.
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ApiError } from '../lib/api';
import { useAuthStore } from '../stores/auth';

const SUPPORTED_LOCALES = ['en', 'ja', 'zh-tw'];

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const { locale } = useI18n();

const failed = ref(false);
const errorCode = ref<string | null>(null);
const errorMessage = ref('');

const expired = computed(() => route.query.expired === '1');

const failureKey = computed(() => {
  if (errorCode.value === 'preview_disabled') return 'guest.entry_disabled';
  if (errorCode.value === 'preview_busy') return 'guest.limit_preview_busy_body';
  return 'guest.entry_failed';
});

function applyLocaleFromQuery() {
  const raw = route.query.lang;
  const lang = typeof raw === 'string' ? raw.toLowerCase() : '';
  if (!SUPPORTED_LOCALES.includes(lang)) return;
  locale.value = lang;
  try {
    localStorage.setItem('user-locale', lang);
  } catch {
    /* storage may be unavailable (private mode) — non-fatal */
  }
}

async function start() {
  failed.value = false;
  errorCode.value = null;
  errorMessage.value = '';

  if (!auth.hasHydrated) await auth.hydrateSession();
  if (auth.isAuthenticated) {
    router.replace({ name: 'today' });
    return;
  }

  try {
    await auth.startGuestSession();
    router.replace({ name: 'today' });
  } catch (err) {
    failed.value = true;
    if (err instanceof ApiError) {
      const data = err.data as { code?: string } | null;
      errorCode.value = data?.code ?? null;
      errorMessage.value = err.message;
    } else {
      errorMessage.value = err instanceof Error ? err.message : '';
    }
  }
}

onMounted(() => {
  applyLocaleFromQuery();
  start();
});
</script>

<template>
  <main class="pv-shell">
    <div class="pv-page">
      <div class="brand-lockup">
        <span class="brand-kanji" lang="ja">栞</span>
        <span class="brand-romaji">SHIORI</span>
      </div>

      <div class="pv-body">
        <div class="eyebrow-sm eyebrow-kohaku">{{ $t('guest.banner_eyebrow') }}</div>

        <template v-if="!failed">
          <h1 class="pv-title">{{ $t('guest.entry_opening') }}</h1>
          <p v-if="expired" class="pv-sub">{{ $t('guest.entry_expired') }}</p>
          <p v-else class="pv-sub">{{ $t('guest.entry_sub') }}</p>
          <span class="pv-dots" aria-hidden="true"><span /><span /><span /></span>
        </template>

        <template v-else>
          <h1 class="pv-title">{{ $t('guest.entry_failed_title') }}</h1>
          <p class="pv-sub">{{ $t(failureKey) }}</p>
          <p v-if="errorMessage && errorCode !== 'preview_disabled'" class="pv-detail">{{ errorMessage }}</p>
          <div class="pv-actions">
            <button v-if="errorCode !== 'preview_disabled'" type="button" class="pv-retry" @click="start">
              {{ $t('guest.entry_retry') }}
            </button>
            <router-link to="/login" class="auth-toggle-link">{{ $t('guest.entry_sign_in') }} →</router-link>
            <router-link to="/register" class="auth-toggle-link">{{ $t('guest.create_account') }} →</router-link>
          </div>
        </template>
      </div>

      <footer class="pv-footer">
        {{ $t('chrome.edition', { year: new Date().getFullYear() }) }}
      </footer>
    </div>
  </main>
</template>

<style scoped>
.pv-shell {
  min-height: 100vh;
  background: var(--background);
  display: flex;
  justify-content: center;
}

.pv-page {
  width: min(560px, 100%);
  padding: 56px 32px 40px;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.brand-lockup {
  display: inline-flex;
  align-items: baseline;
  gap: 14px;
}

.brand-kanji {
  font-family: var(--font-serif);
  font-size: 40px;
  line-height: 1;
  font-weight: 600;
  color: var(--primary);
}

.brand-romaji {
  font-family: var(--font-serif);
  font-size: 11px;
  letter-spacing: 0.42em;
  font-weight: 500;
  color: var(--primary);
  text-transform: uppercase;
}

.pv-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 10px;
  padding: 48px 0;
}

.pv-title {
  margin: 4px 0 0;
  font-family: var(--font-serif);
  font-size: clamp(2rem, 4vw + 0.5rem, 2.8rem);
  line-height: 1.1;
  font-weight: 500;
  color: var(--foreground);
}

.pv-sub {
  margin: 6px 0 0;
  max-width: 40em;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 1.02rem;
  line-height: 1.65;
  color: color-mix(in oklab, var(--foreground) 64%, transparent);
}

.pv-detail {
  margin: 0;
  font-family: var(--font-sans);
  font-size: 0.78rem;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
}

.pv-actions {
  margin-top: 22px;
  display: flex;
  align-items: baseline;
  gap: 24px;
  flex-wrap: wrap;
}

.pv-retry {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  font-weight: 600;
  color: var(--primary-foreground);
  background: var(--primary);
  border: none;
  padding: 12px 20px;
  border-radius: 2px;
  cursor: pointer;
  transition: background 160ms ease;
}

.pv-retry:hover {
  background: var(--primary-container);
}

.pv-dots {
  display: inline-flex;
  gap: 6px;
  margin-top: 18px;
}

.pv-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--secondary);
  animation: pv-pulse 1.2s ease-in-out infinite;
}

.pv-dots span:nth-child(2) { animation-delay: 0.2s; }
.pv-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes pv-pulse {
  0%, 80%, 100% { opacity: 0.25; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}

@media (prefers-reduced-motion: reduce) {
  .pv-dots span { animation: none; opacity: 0.6; }
}

.pv-footer {
  font-family: var(--font-sans);
  font-size: 0.62rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 45%, transparent);
}
</style>
