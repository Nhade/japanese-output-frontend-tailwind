<script setup lang="ts">
// One dialog for every "the preview can't do that" answer from the API
// (429 preview_limit / preview_busy, 403 guest_forbidden). The API client
// raises a window event so no view has to special-case guest budgets.
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { PREVIEW_BLOCKED_EVENT, type PreviewBlockedDetail } from '../lib/api';

const KNOWN_CODES = ['preview_limit', 'preview_busy', 'guest_forbidden'] as const;
type KnownCode = (typeof KNOWN_CODES)[number];

const open = ref(false);
const code = ref<KnownCode>('preview_limit');

const titleKey = computed(() => `guest.limit_${code.value}_title`);
const bodyKey = computed(() => `guest.limit_${code.value}_body`);

function onBlocked(event: Event) {
  const detail = (event as CustomEvent<PreviewBlockedDetail>).detail;
  code.value = (KNOWN_CODES as readonly string[]).includes(detail?.code)
    ? (detail.code as KnownCode)
    : 'preview_limit';
  open.value = true;
}

function close() {
  open.value = false;
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && open.value) close();
}

onMounted(() => {
  window.addEventListener(PREVIEW_BLOCKED_EVENT, onBlocked);
  window.addEventListener('keydown', onKeydown);
});

onUnmounted(() => {
  window.removeEventListener(PREVIEW_BLOCKED_EVENT, onBlocked);
  window.removeEventListener('keydown', onKeydown);
});
</script>

<template>
  <transition name="pl-entry">
    <div
      v-if="open"
      class="pl-overlay"
      role="dialog"
      aria-modal="true"
      :aria-label="$t(titleKey)"
    >
      <div class="pl-backdrop" @click="close" />
      <div class="pl-card" @click.stop>
        <div class="eyebrow-sm eyebrow-kohaku">{{ $t('guest.banner_eyebrow') }}</div>
        <h2 class="pl-title">{{ $t(titleKey) }}</h2>
        <p class="pl-body">{{ $t(bodyKey) }}</p>
        <div class="pl-actions">
          <router-link to="/register" class="pl-primary" @click="close">
            {{ $t('guest.create_account') }} →
          </router-link>
          <button type="button" class="pl-secondary" @click="close">
            {{ $t('guest.limit_keep_browsing') }}
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.pl-overlay {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

/* Glass is allowed on transient overlays only (design system §2). */
.pl-backdrop {
  position: absolute;
  inset: 0;
  background: color-mix(in oklab, var(--foreground) 28%, transparent);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
}

.pl-card {
  position: relative;
  width: min(440px, 100%);
  padding: 30px 34px 28px;
  background: var(--surface-container-lowest);
  border: 1px solid color-mix(in oklab, var(--foreground) 12%, transparent);
  border-radius: 4px;
  box-shadow:
    0 32px 64px -24px color-mix(in oklab, var(--foreground) 18%, transparent),
    0 4px 12px -6px color-mix(in oklab, var(--foreground) 8%, transparent);
}

.pl-title {
  margin: 10px 0 8px;
  font-family: var(--font-serif);
  font-size: 1.55rem;
  line-height: 1.2;
  font-weight: 500;
  color: var(--foreground);
}

.pl-body {
  margin: 0 0 22px;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.98rem;
  line-height: 1.6;
  color: color-mix(in oklab, var(--foreground) 66%, transparent);
}

.pl-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.pl-primary {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  font-weight: 600;
  color: var(--primary-foreground);
  background: var(--primary);
  padding: 12px 20px;
  border-radius: 2px;
  text-decoration: none;
  transition: background 160ms ease;
}

.pl-primary:hover {
  background: var(--primary-container);
}

.pl-secondary {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.95rem;
  color: color-mix(in oklab, var(--foreground) 62%, transparent);
  background: none;
  border: none;
  padding: 4px 0;
  border-bottom: 1px solid transparent;
  cursor: pointer;
  transition: color 160ms ease, border-color 160ms ease;
}

.pl-secondary:hover {
  color: var(--foreground);
  border-bottom-color: var(--secondary);
}

.pl-entry-enter-active,
.pl-entry-leave-active {
  transition: opacity 200ms ease;
}

.pl-entry-enter-from,
.pl-entry-leave-to {
  opacity: 0;
}
</style>
