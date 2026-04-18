<script setup lang="ts">
import LanguageSelector from './LanguageSelector.vue';

defineProps<{
  eyebrow: string;
}>();
</script>

<template>
  <main class="auth-shell">
    <!-- ── LEFT · Editorial cover ──────────────────────────── -->
    <aside class="auth-cover" aria-hidden="false">
      <div class="auth-cover-grain" aria-hidden="true" />

      <div class="auth-cover-top">
        <div class="brand-lockup">
          <span class="brand-kanji" lang="ja">栞</span>
          <span class="brand-romaji">SHIORI</span>
        </div>
      </div>

      <div class="auth-cover-middle">
        <h1 class="auth-cover-headline">
          {{ $t('auth.cover_headline_1') }}<br />
          <span class="emphasis">{{ $t('auth.cover_headline_2') }}</span><br />
          {{ $t('auth.cover_headline_3') }}
        </h1>
        <p class="auth-cover-descriptor">{{ $t('auth.cover_descriptor') }}</p>
      </div>

      <div class="auth-cover-bottom">
        <div class="auth-cover-watermark" lang="ja" aria-hidden="true">栞</div>
        <div class="auth-cover-caption" lang="ja" aria-hidden="true">
          {{ $t('auth.cover_caption_ja') }}
        </div>
      </div>
    </aside>

    <!-- ── RIGHT · Form column ─────────────────────────────── -->
    <section class="auth-form-col">
      <div class="auth-form-top">
        <LanguageSelector />
      </div>

      <div class="auth-form-body">
        <div class="auth-eyebrow">
          <span class="auth-eyebrow-rule" aria-hidden="true" />
          {{ eyebrow }}
        </div>
        <slot />
      </div>

      <footer class="auth-footer">
        <span>Shiori · Edition {{ new Date().getFullYear() }}</span>
      </footer>
    </section>
  </main>
</template>

<style scoped>
.auth-shell {
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  min-height: 100vh;
  background: var(--background);
}

/* Cover ------------------------------------------------------- */
.auth-cover {
  position: relative;
  background: var(--surface-container);
  padding: 48px 64px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow: hidden;
  min-height: 100vh;
}
.auth-cover-grain {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    radial-gradient(circle at 20% 85%, color-mix(in oklab, var(--destructive) 4%, transparent) 0%, transparent 45%),
    radial-gradient(circle at 80% 15%, color-mix(in oklab, var(--secondary) 5%, transparent) 0%, transparent 50%);
}
.auth-cover-top,
.auth-cover-middle,
.auth-cover-bottom {
  position: relative;
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

.auth-cover-middle { margin-top: 24px; }
.auth-cover-headline {
  font-family: var(--font-serif);
  font-size: clamp(52px, 6.2vw, 84px);
  line-height: 0.98;
  font-weight: 500;
  margin: 0;
  color: var(--foreground);
  letter-spacing: -0.02em;
}
.auth-cover-headline .emphasis {
  font-style: italic;
  font-weight: 400;
  color: var(--secondary);
}
.auth-cover-descriptor {
  margin-top: 32px;
  max-width: 420px;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 15px;
  line-height: 1.7;
  color: color-mix(in oklab, var(--foreground) 62%, transparent);
  padding-left: 28px;
  border-left: 1px solid color-mix(in oklab, var(--foreground) 12%, transparent);
}

.auth-cover-bottom {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 32px;
}
.auth-cover-watermark {
  font-family: var(--font-serif);
  font-size: clamp(180px, 18vw, 260px);
  line-height: 0.8;
  color: var(--foreground);
  opacity: 0.07;
  font-weight: 700;
  margin-left: -18px;
  margin-bottom: -28px;
  user-select: none;
  flex-shrink: 0;
}
.auth-cover-caption {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  font-family: var(--font-serif);
  font-size: 11px;
  letter-spacing: 0.4em;
  color: color-mix(in oklab, var(--foreground) 62%, transparent);
  line-height: 1.8;
  padding-bottom: 6px;
}

/* Form column ------------------------------------------------ */
.auth-form-col {
  padding: 40px 56px 32px;
  display: flex;
  flex-direction: column;
  background: var(--background);
  position: relative;
  min-height: 100vh;
}
.auth-form-top {
  display: flex;
  justify-content: flex-end;
}
.auth-form-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  max-width: 460px;
  width: 100%;
  margin: 0 auto;
  padding: 20px 0;
}

.auth-eyebrow {
  display: flex;
  align-items: center;
  gap: 12px;
  font-family: var(--font-sans);
  font-size: 0.64rem;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  font-weight: 600;
  margin-bottom: 18px;
}
.auth-eyebrow-rule {
  width: 24px;
  height: 1px;
  background: var(--foreground);
}

.auth-footer {
  font-family: var(--font-sans);
  font-size: 0.66rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 40%, transparent);
  font-weight: 500;
  display: flex;
  justify-content: space-between;
  padding-top: 24px;
  border-top: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
}

/* Responsive — collapse to single column on narrow viewports */
@media (max-width: 960px) {
  .auth-shell {
    grid-template-columns: 1fr;
    min-height: 100vh;
  }
  .auth-cover {
    min-height: auto;
    padding: 40px 32px;
  }
  .auth-cover-middle { margin-top: 16px; }
  .auth-cover-headline {
    font-size: clamp(42px, 8vw, 62px);
  }
  .auth-cover-bottom {
    align-items: flex-start;
  }
  .auth-cover-watermark {
    font-size: 180px;
    margin-bottom: -30px;
  }
  .auth-form-col {
    padding: 32px 32px 24px;
    min-height: auto;
  }
}
</style>
