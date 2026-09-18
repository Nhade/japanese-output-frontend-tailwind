<script setup lang="ts">
// One numbered section of the About page. Also rendered in `compact` mode
// inside the tour's "Learn more" drawer, so the copy is written once.
import { computed } from 'vue';
import { type AboutSectionDef, aboutKey } from '../../lib/aboutContent';

const props = defineProps<{
  def: AboutSectionDef;
  index: number;
  compact?: boolean;
}>();

const number = computed(() => String(props.index + 1).padStart(2, '0'));
const bulletKeys = computed(() =>
  Array.from({ length: props.def.bullets }, (_, i) => aboutKey(props.def.id, `b${i + 1}`)),
);
</script>

<template>
  <section
    :id="compact ? undefined : def.id"
    class="about-section"
    :class="{ 'is-compact': compact }"
  >
    <header class="about-section-head">
      <span class="about-num" aria-hidden="true">{{ number }}</span>
      <h2 class="about-section-title">{{ $t(aboutKey(def.id, 'title')) }}</h2>
    </header>

    <p class="about-lede">{{ $t(aboutKey(def.id, 'lede')) }}</p>

    <div class="about-grid">
      <div class="about-how">
        <div class="eyebrow-sm">{{ $t('about.how') }}</div>
        <ul class="about-bullets">
          <li v-for="key in bulletKeys" :key="key">{{ $t(key) }}</li>
        </ul>
      </div>

      <aside class="about-note">
        <div class="eyebrow-sm eyebrow-kohaku">{{ $t('about.note_label') }}</div>
        <p class="about-note-text">{{ $t(aboutKey(def.id, 'note')) }}</p>
        <router-link v-if="def.tryTo && !compact" :to="def.tryTo" class="about-try">
          {{ $t('about.try') }} →
        </router-link>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.about-section {
  padding: 40px 0 44px;
  border-top: 1px solid color-mix(in oklab, var(--foreground) 10%, transparent);
  /* Anchor targets sit below the fixed header. */
  scroll-margin-top: calc(var(--topnav-h) + 24px);
}

.about-section-head {
  display: flex;
  align-items: baseline;
  gap: 18px;
}

.about-num {
  font-family: var(--font-sans);
  font-size: 0.66rem;
  letter-spacing: 0.24em;
  color: var(--secondary);
}

.about-section-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: clamp(1.5rem, 1.2vw + 1.1rem, 2rem);
  font-weight: 500;
  line-height: 1.2;
  color: var(--foreground);
}

.about-lede {
  margin: 12px 0 0;
  max-width: 44em;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 1.05rem;
  line-height: 1.65;
  color: color-mix(in oklab, var(--foreground) 66%, transparent);
}

.about-grid {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  gap: 40px;
  margin-top: 26px;
}

.about-bullets {
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}

.about-bullets li {
  position: relative;
  padding-left: 18px;
  margin-bottom: 10px;
  font-family: var(--font-serif);
  font-size: 0.98rem;
  line-height: 1.6;
  color: var(--foreground);
}

.about-bullets li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.72em;
  width: 8px;
  height: 1px;
  background: var(--secondary);
}

.about-note {
  padding: 16px 18px;
  background: var(--surface-container-low);
  border-left: 2px solid var(--secondary);
  align-self: start;
}

.about-note-text {
  margin: 8px 0 0;
  font-family: var(--font-sans);
  font-size: 0.82rem;
  line-height: 1.6;
  color: color-mix(in oklab, var(--foreground) 72%, transparent);
}

.about-try {
  display: inline-block;
  margin-top: 14px;
  font-family: var(--font-sans);
  font-size: 0.66rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 600;
  color: var(--primary);
  text-decoration: none;
  border-bottom: 1px solid var(--primary);
  padding-bottom: 2px;
  transition: color 160ms ease, border-color 160ms ease;
}

.about-try:hover {
  color: var(--primary-container);
  border-bottom-color: var(--secondary);
}

/* Drawer variant: single column, tighter rhythm. */
.about-section.is-compact {
  padding: 0;
  border-top: none;
}

.about-section.is-compact .about-grid {
  grid-template-columns: 1fr;
  gap: 22px;
  margin-top: 20px;
}

.about-section.is-compact .about-section-title {
  font-size: 1.45rem;
}

@media (max-width: 820px) {
  .about-grid {
    grid-template-columns: 1fr;
    gap: 22px;
  }
}
</style>
