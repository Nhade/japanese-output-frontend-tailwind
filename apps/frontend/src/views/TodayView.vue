<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { BookOpen, Clapperboard, MessageCircle, PenLine, RotateCcw, TrendingUp } from 'lucide-vue-next';

const { locale } = useI18n();

function intlLocale(): string {
  if (locale.value === 'ja') return 'ja-JP';
  if (locale.value === 'zh-tw') return 'zh-Hant';
  return 'en-US';
}

const todayDate = computed(() => new Intl.DateTimeFormat(intlLocale(), {
  weekday: 'long',
  month: 'long',
  day: 'numeric',
}).format(new Date()));

const primaryActions = [
  {
    to: '/study/exercise',
    icon: PenLine,
    key: 'adaptive',
    accent: 'primary',
  },
  {
    to: '/practice',
    icon: RotateCcw,
    key: 'practice',
    accent: 'secondary',
  },
  {
    to: '/news',
    icon: BookOpen,
    key: 'read',
    accent: 'primary',
  },
  {
    to: '/chat',
    icon: MessageCircle,
    key: 'tutor',
    accent: 'secondary',
  },
] as const;

const secondaryActions = [
  {
    to: '/videos',
    icon: Clapperboard,
    key: 'watch',
  },
  {
    to: '/mistakes',
    icon: RotateCcw,
    key: 'mistakes',
  },
  {
    to: '/statistics',
    icon: TrendingUp,
    key: 'progress',
  },
] as const;
</script>

<template>
  <main class="today-shell ei-shell-bg text-foreground">
    <section class="today-page">
      <header class="today-hero">
        <div class="today-hero-copy">
          <div class="eyebrow eyebrow-kohaku">{{ $t('today.eyebrow') }}</div>
          <h1 class="today-h1">{{ $t('today.heading') }}</h1>
          <p class="today-sub">{{ $t('today.subtitle') }}</p>
        </div>
        <div class="today-date">
          <span class="today-date-label">{{ $t('today.date_label') }}</span>
          <span class="today-date-value">{{ todayDate }}</span>
        </div>
      </header>

      <section class="today-focus">
        <div>
          <div class="eyebrow-sm eyebrow-indigo">{{ $t('today.recommended') }}</div>
          <h2 class="today-focus-title">{{ $t('today.focus_title') }}</h2>
          <p class="today-focus-body">{{ $t('today.focus_body') }}</p>
        </div>
        <RouterLink to="/study/exercise" class="today-focus-cta">
          {{ $t('today.start') }}
        </RouterLink>
      </section>

      <section class="today-actions" :aria-label="$t('today.primary_actions')">
        <RouterLink
          v-for="action in primaryActions"
          :key="action.to"
          :to="action.to"
          class="today-action"
          :class="`is-${action.accent}`"
        >
          <component :is="action.icon" class="today-action-icon" aria-hidden="true" />
          <span class="today-action-text">
            <span class="today-action-title">{{ $t(`today.${action.key}_title`) }}</span>
            <span class="today-action-desc">{{ $t(`today.${action.key}_desc`) }}</span>
          </span>
        </RouterLink>
      </section>

      <section class="today-secondary">
        <div class="section-title-row today-section-row">
          <h2 class="section-title">{{ $t('today.more_title') }}</h2>
          <span class="section-count">{{ $t('today.more_count', { n: secondaryActions.length }) }}</span>
        </div>
        <div class="today-secondary-grid">
          <RouterLink
            v-for="action in secondaryActions"
            :key="action.to"
            :to="action.to"
            class="today-secondary-link"
          >
            <component :is="action.icon" class="today-secondary-icon" aria-hidden="true" />
            <span>
              <span class="today-secondary-title">{{ $t(`today.${action.key}_title`) }}</span>
              <span class="today-secondary-desc">{{ $t(`today.${action.key}_desc`) }}</span>
            </span>
          </RouterLink>
        </div>
      </section>
    </section>
  </main>
</template>

<style scoped>
.today-shell {
  min-height: calc(100vh - var(--app-chrome-h));
}

.today-page {
  width: 100%;
  max-width: 1180px;
  margin: 0 auto;
  padding: 56px 48px 96px;
}

.today-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 48px;
  align-items: end;
  padding-bottom: 32px;
  border-bottom: 2px solid var(--foreground);
}

.today-h1 {
  margin: 8px 0 10px;
  font-family: var(--font-serif);
  font-weight: 500;
  font-size: clamp(2.6rem, 5vw + 0.5rem, 4.6rem);
  line-height: 0.98;
  letter-spacing: 0;
  color: var(--foreground);
}

.today-sub {
  margin: 0;
  max-width: 38em;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 1.04rem;
  line-height: 1.7;
  color: color-mix(in oklab, var(--foreground) 64%, transparent);
}

.today-date {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  padding-bottom: 10px;
  min-width: 190px;
}

.today-date-label {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.62rem;
  color: var(--secondary);
}

.today-date-value {
  font-family: var(--font-serif);
  font-style: italic;
  color: color-mix(in oklab, var(--foreground) 72%, transparent);
  text-align: right;
}

.today-focus {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 32px;
  align-items: center;
  padding: 30px 0;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
}

.today-focus-title {
  margin: 8px 0 6px;
  font-family: var(--font-serif);
  font-size: clamp(1.55rem, 1.2vw + 1.1rem, 2.05rem);
  font-weight: 500;
  color: var(--foreground);
}

.today-focus-body {
  margin: 0;
  max-width: 48em;
  font-family: var(--font-serif);
  font-style: italic;
  line-height: 1.65;
  color: color-mix(in oklab, var(--foreground) 62%, transparent);
}

.today-focus-cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 42px;
  padding: 10px 20px;
  border: 1px solid var(--primary);
  border-radius: 2px;
  background: var(--primary);
  color: var(--primary-foreground);
  font-family: var(--font-sans);
  font-size: 0.72rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  text-decoration: none;
  white-space: nowrap;
  transition: background 160ms ease, border-color 160ms ease;
}

.today-focus-cta:hover {
  background: var(--primary-container);
  border-color: var(--primary-container);
}

.today-actions {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  margin-top: 34px;
  background: color-mix(in oklab, var(--foreground) 10%, transparent);
  border: 1px solid color-mix(in oklab, var(--foreground) 10%, transparent);
}

.today-action {
  min-height: 190px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 28px;
  padding: 22px;
  background: var(--background);
  color: var(--foreground);
  text-decoration: none;
  transition: background 160ms ease, color 160ms ease;
}

.today-action:hover {
  background: var(--surface-container-low);
}

.today-action-icon {
  width: 24px;
  height: 24px;
  color: color-mix(in oklab, var(--foreground) 48%, transparent);
}

.today-action.is-primary:hover .today-action-icon,
.today-action.is-primary:hover .today-action-title {
  color: var(--primary);
}

.today-action.is-secondary:hover .today-action-icon,
.today-action.is-secondary:hover .today-action-title {
  color: var(--secondary);
}

.today-action-text,
.today-secondary-link span {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.today-action-title,
.today-secondary-title {
  font-family: var(--font-serif);
  font-size: 1.25rem;
  color: var(--foreground);
}

.today-action-desc,
.today-secondary-desc {
  font-family: var(--font-serif);
  font-style: italic;
  line-height: 1.55;
  font-size: 0.92rem;
  color: color-mix(in oklab, var(--foreground) 58%, transparent);
}

.today-secondary {
  margin-top: 56px;
}

.today-section-row {
  margin-bottom: 0;
}

.today-secondary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
}

.today-secondary-link {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 16px;
  padding: 22px 22px 24px 0;
  color: var(--foreground);
  text-decoration: none;
}

.today-secondary-link:hover .today-secondary-title,
.today-secondary-link:hover .today-secondary-icon {
  color: var(--primary);
}

.today-secondary-icon {
  width: 18px;
  height: 18px;
  margin-top: 5px;
  color: color-mix(in oklab, var(--foreground) 48%, transparent);
}

@media (max-width: 960px) {
  .today-actions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .today-secondary-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .today-page {
    padding: 34px 20px 88px;
  }

  .today-hero,
  .today-focus {
    grid-template-columns: 1fr;
    gap: 20px;
  }

  .today-date {
    align-items: flex-start;
    min-width: 0;
    padding-bottom: 0;
  }

  .today-date-value {
    text-align: left;
  }

  .today-focus-cta {
    justify-self: start;
  }

  .today-actions {
    grid-template-columns: 1fr;
  }

  .today-action {
    min-height: 148px;
  }
}
</style>
