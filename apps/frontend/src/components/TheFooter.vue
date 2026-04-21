<script setup lang="ts">
import { computed } from 'vue';

// Year is derived each render so the colophon stays honest without a
// build-time date to maintain.
const currentYear = computed(() => new Date().getFullYear());
</script>

<template>
  <footer class="site-footer">
    <div class="site-footer-inner">
      <span class="colophon-eyebrow">{{ $t('chrome.colophon') }}</span>
      <span class="colophon-rule" aria-hidden="true" />
      <span class="colophon-text">
        &copy; {{ currentYear }}
        <span class="brand-word">Shiori</span>
        — <span class="colophon-tag" lang="ja">栞</span>
      </span>
    </div>
  </footer>
</template>

<style scoped>
.site-footer {
  background: var(--background);
  border-top: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
  /* Fixed chrome height — view shells subtract this from 100vh so
     single-screen layouts fit without introducing a scroll. */
  height: var(--footer-h);
  display: flex;
  align-items: center;
}
.site-footer-inner {
  width: 100%;
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 32px;
  display: flex;
  align-items: baseline;
  gap: 14px;
  font-size: 0.7rem;
  color: color-mix(in oklab, var(--foreground) 52%, transparent);
}
.colophon-eyebrow {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.28em;
  font-size: 0.6rem;
  color: var(--secondary);
  font-weight: 500;
}
.colophon-rule {
  flex: 1;
  height: 1px;
  background: color-mix(in oklab, var(--foreground) 8%, transparent);
}
.colophon-text {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.85rem;
  letter-spacing: 0.01em;
}
.brand-word {
  color: color-mix(in oklab, var(--foreground) 75%, transparent);
}
.colophon-tag {
  font-family: var(--font-serif);
  font-style: normal;
  color: var(--primary);
}
@media (max-width: 720px) {
  .site-footer-inner { padding: 14px 16px; gap: 10px; }
  .colophon-text { font-size: 0.78rem; }
}
</style>
