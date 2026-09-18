<script setup lang="ts">
// Slim strip shown above every chrome'd view while a guest session is
// active. It says what a guest is looking at (sample history), what happens
// to their data (purged after 7 days), and offers the two exits: keep the
// history by registering, or end the preview.
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';

const auth = useAuthStore();
const router = useRouter();

function endPreview() {
  auth.logout();
  router.push({ name: 'login' });
}
</script>

<template>
  <div class="guest-banner" role="status">
    <div class="guest-banner-inner">
      <span class="eyebrow-sm eyebrow-kohaku guest-banner-eyebrow">{{ $t('guest.banner_eyebrow') }}</span>
      <span class="guest-banner-text">{{ $t('guest.banner_text') }}</span>
      <span class="guest-banner-actions">
        <router-link to="/register" class="guest-banner-cta">
          {{ $t('guest.create_account') }} →
        </router-link>
        <button type="button" class="guest-banner-end" @click="endPreview">
          {{ $t('guest.end_preview') }}
        </button>
      </span>
    </div>
  </div>
</template>

<style scoped>
.guest-banner {
  background: var(--surface-container-low);
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
}

.guest-banner-inner {
  max-width: 1400px;
  margin: 0 auto;
  padding: 10px 32px;
  display: flex;
  align-items: baseline;
  gap: 16px;
  flex-wrap: wrap;
  border-left: 2px solid var(--secondary);
}

.guest-banner-eyebrow {
  flex-shrink: 0;
}

.guest-banner-text {
  flex: 1 1 320px;
  min-width: 0;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.92rem;
  line-height: 1.5;
  color: color-mix(in oklab, var(--foreground) 68%, transparent);
}

.guest-banner-actions {
  display: inline-flex;
  align-items: baseline;
  gap: 18px;
  flex-shrink: 0;
}

.guest-banner-cta,
.guest-banner-end {
  font-family: var(--font-sans);
  font-size: 0.68rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 600;
  background: none;
  border: none;
  padding: 2px 0;
  cursor: pointer;
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: color 160ms ease, border-color 160ms ease;
}

.guest-banner-cta {
  color: var(--primary);
  border-bottom-color: var(--primary);
}

.guest-banner-cta:hover {
  color: var(--primary-container);
  border-bottom-color: var(--secondary);
}

.guest-banner-end {
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}

.guest-banner-end:hover {
  color: var(--foreground);
  border-bottom-color: var(--secondary);
}

@media (max-width: 720px) {
  .guest-banner-inner {
    padding: 10px 16px 12px;
    gap: 8px 14px;
  }
}
</style>
