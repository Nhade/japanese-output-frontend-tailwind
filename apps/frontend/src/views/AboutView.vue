<script setup lang="ts">
// Public "what is this" page: the technical notes behind every feature,
// in one place. It is the landing page for signed-out visitors, the target
// of the tour's "Learn more" links, and linkable by section (#exercise …).
import { nextTick, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import AboutSection from '../components/about/AboutSection.vue';
import { ABOUT_SECTIONS, GITHUB_URL, aboutKey } from '../lib/aboutContent';
import { startTour } from '../lib/tour';
import { useAuthStore } from '../stores/auth';

const auth = useAuthStore();
const route = useRoute();

function sectionNumber(index: number): string {
  return String(index + 1).padStart(2, '0');
}

onMounted(async () => {
  if (!route.hash) return;
  await nextTick();
  try {
    document.querySelector(route.hash)?.scrollIntoView({ block: 'start' });
  } catch {
    /* an invalid hash is not worth an error */
  }
});
</script>

<template>
  <main class="about-shell ei-shell-bg text-foreground">
    <div class="about-page">
      <header class="about-hero">
        <div class="eyebrow eyebrow-kohaku">{{ $t('about.eyebrow') }}</div>
        <h1 class="about-h1">{{ $t('about.title') }}</h1>
        <p class="about-hero-lede">{{ $t('about.lede') }}</p>

        <div class="about-ctas">
          <template v-if="auth.isAuthenticated">
            <button type="button" class="about-cta-primary" @click="startTour()">
              {{ $t('about.cta_tour') }}
            </button>
            <router-link to="/" class="about-cta-link">{{ $t('about.cta_today') }} →</router-link>
          </template>
          <template v-else>
            <router-link to="/preview" class="about-cta-primary">{{ $t('about.cta_guest') }}</router-link>
            <router-link to="/login" class="about-cta-link">{{ $t('about.cta_signin') }} →</router-link>
          </template>
          <a :href="GITHUB_URL" class="about-cta-link" target="_blank" rel="noopener">
            {{ $t('about.cta_source') }} ↗
          </a>
        </div>
      </header>

      <nav class="about-toc" :aria-label="$t('about.contents')">
        <span class="eyebrow-sm">{{ $t('about.contents') }}</span>
        <ol class="about-toc-list">
          <li v-for="(s, i) in ABOUT_SECTIONS" :key="s.id">
            <a :href="'#' + s.id" class="about-toc-link">
              <span class="about-toc-num">{{ sectionNumber(i) }}</span>
              {{ $t(aboutKey(s.id, 'title')) }}
            </a>
          </li>
        </ol>
      </nav>

      <div class="about-sections">
        <AboutSection v-for="(s, i) in ABOUT_SECTIONS" :key="s.id" :def="s" :index="i" />
      </div>

      <footer class="about-closing">
        <h2 class="about-closing-title">{{ $t('about.closing_title') }}</h2>
        <p class="about-closing-body">{{ $t('about.closing_body') }}</p>
        <div class="about-ctas">
          <template v-if="auth.isGuest">
            <router-link to="/register" class="about-cta-primary">{{ $t('about.cta_register') }}</router-link>
            <router-link to="/" class="about-cta-link">{{ $t('about.cta_today') }} →</router-link>
          </template>
          <template v-else-if="auth.isAuthenticated">
            <router-link to="/" class="about-cta-primary">{{ $t('about.cta_today') }}</router-link>
          </template>
          <template v-else>
            <router-link to="/preview" class="about-cta-primary">{{ $t('about.cta_guest') }}</router-link>
            <router-link to="/register" class="about-cta-link">{{ $t('about.cta_register') }} →</router-link>
          </template>
        </div>
      </footer>
    </div>
  </main>
</template>

<style scoped>
.about-shell {
  min-height: calc(100vh - var(--app-chrome-h));
}

.about-page {
  width: 100%;
  max-width: 940px;
  margin: 0 auto;
  padding: 56px 48px 96px;
}

.about-hero {
  padding-bottom: 36px;
  border-bottom: 2px solid var(--foreground);
}

.about-h1 {
  margin: 10px 0 14px;
  font-family: var(--font-serif);
  font-weight: 500;
  font-size: clamp(2.3rem, 4.2vw + 0.5rem, 3.9rem);
  line-height: 1.02;
  color: var(--foreground);
}

.about-hero-lede {
  margin: 0;
  max-width: 46em;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 1.08rem;
  line-height: 1.7;
  color: color-mix(in oklab, var(--foreground) 66%, transparent);
}

.about-ctas {
  display: flex;
  align-items: center;
  gap: 26px;
  flex-wrap: wrap;
  margin-top: 26px;
}

.about-cta-primary {
  display: inline-flex;
  align-items: center;
  min-height: 42px;
  padding: 10px 20px;
  border: 1px solid var(--primary);
  border-radius: 2px;
  background: var(--primary);
  color: var(--primary-foreground);
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
  transition: background 160ms ease, border-color 160ms ease;
}

.about-cta-primary:hover {
  background: var(--primary-container);
  border-color: var(--primary-container);
}

.about-cta-link {
  font-family: var(--font-sans);
  font-size: 0.68rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 600;
  color: var(--primary);
  text-decoration: none;
  border-bottom: 1px solid var(--primary);
  padding-bottom: 2px;
  transition: color 160ms ease, border-color 160ms ease;
}

.about-cta-link:hover {
  color: var(--primary-container);
  border-bottom-color: var(--secondary);
}

.about-toc {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 24px;
  align-items: baseline;
  padding: 24px 0 28px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
}

.about-toc-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 22px;
}

.about-toc-link {
  font-family: var(--font-serif);
  font-size: 0.95rem;
  color: var(--foreground);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: border-color 160ms ease, color 160ms ease;
}

.about-toc-link:hover {
  color: var(--primary);
  border-bottom-color: var(--secondary);
}

.about-toc-num {
  font-family: var(--font-sans);
  font-size: 0.6rem;
  letter-spacing: 0.2em;
  color: var(--secondary);
  margin-right: 6px;
}

.about-closing {
  margin-top: 16px;
  padding-top: 40px;
  border-top: 2px solid var(--foreground);
}

.about-closing-title {
  margin: 0 0 10px;
  font-family: var(--font-serif);
  font-size: clamp(1.5rem, 1.2vw + 1.1rem, 2rem);
  font-weight: 500;
  color: var(--foreground);
}

.about-closing-body {
  margin: 0;
  max-width: 44em;
  font-family: var(--font-serif);
  font-style: italic;
  line-height: 1.65;
  color: color-mix(in oklab, var(--foreground) 64%, transparent);
}

@media (max-width: 720px) {
  .about-page {
    padding: 34px 20px 88px;
  }

  .about-toc {
    grid-template-columns: 1fr;
    gap: 12px;
  }
}
</style>
