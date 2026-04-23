<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';

interface Article {
  article_id: string;
  title: string;
  category?: string;
  publish_timestamp: string | null;
}

const { t, locale } = useI18n();
const router = useRouter();

const articles = ref<Article[]>([]);
const loading = ref(true);
const filterDate = ref('');
const filterCategory = ref('');

// Categories encountered in the backend (mirrors NewsListView's prior list).
const categories = ['国際', '社会', '気象・災害', '科学・文化', '政治', '経済', '暮らし'];

// Issue number = number of distinct calendar days this user has opened the
// news view. Persists across sessions in localStorage.
const EDITION_KEY = 'shiori-news-edition';
const issueNumber = ref<number>(1);

function bumpIssueNumber(): number {
  const today = new Date().toISOString().slice(0, 10);
  try {
    const raw = localStorage.getItem(EDITION_KEY);
    let state: { count: number; last: string } | null = raw ? JSON.parse(raw) : null;
    if (!state || typeof state.count !== 'number') {
      state = { count: 1, last: today };
    } else if (state.last !== today) {
      state.count += 1;
      state.last = today;
    }
    localStorage.setItem(EDITION_KEY, JSON.stringify(state));
    return state.count;
  } catch {
    return 1;
  }
}

const editionLabel = computed(() => {
  const h = new Date().getHours();
  if (h < 12) return t('news.morning_edition');
  if (h < 17) return t('news.afternoon_edition');
  return t('news.evening_edition');
});

function intlLocale(): string {
  if (locale.value === 'ja') return 'ja-JP';
  if (locale.value === 'zh-tw') return 'zh-Hant';
  return 'en-US';
}

function formatLongDate(d: Date): string {
  return new Intl.DateTimeFormat(intlLocale(), {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  }).format(d);
}

function formatTime(ts: string | null): string {
  if (!ts) return '';
  const d = new Date(ts);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

function formatShortDate(ts: string | null): string {
  if (!ts) return '';
  return new Intl.DateTimeFormat(intlLocale(), { month: 'short', day: 'numeric' }).format(new Date(ts));
}

const filtered = computed(() => {
  // The backend already filters by the query params we send; this computed
  // just mirrors the current articles list so downstream helpers can share
  // the same source when the filter shape evolves.
  return articles.value;
});

const leadArticle = computed<Article | null>(() => filtered.value[0] ?? null);
const restArticles = computed<Article[]>(() => filtered.value.slice(1));

const fetchArticles = async () => {
  loading.value = true;
  try {
    const params = new URLSearchParams();
    if (filterDate.value) params.append('date', filterDate.value);
    if (filterCategory.value) params.append('category', filterCategory.value);
    const query = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/news${query}`);
    articles.value = await res.json();
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
};

function selectCategory(c: string) {
  if (filterCategory.value === c) return;
  filterCategory.value = c;
  fetchArticles();
}

function clearFilters() {
  if (!filterCategory.value && !filterDate.value) return;
  filterCategory.value = '';
  filterDate.value = '';
  fetchArticles();
}

function openArticle(a: Article) {
  router.push(`/news/${a.article_id}`);
}

onMounted(() => {
  issueNumber.value = bumpIssueNumber();
  fetchArticles();
});
</script>

<template>
  <main class="news-shell ei-shell-bg text-foreground">
    <div class="list-page">
      <!-- Masthead ------------------------------------------------ -->
      <header class="masthead">
        <h1 class="masthead-title">{{ $t('nav.news') }}</h1>
        <div class="masthead-meta">
          <span class="issue">
            {{ $t('news.issue_no', { n: issueNumber }) }} · {{ editionLabel }}
          </span>
          <span class="date">{{ formatLongDate(new Date()) }}</span>
        </div>
      </header>
      <div class="masthead-rule" aria-hidden="true" />

      <!-- Filter bar --------------------------------------------- -->
      <div class="filter-bar">
        <div class="filter-group">
          <span class="filter-label">{{ $t('news.section') }}</span>
          <div class="chip-row" role="tablist">
            <button
              class="chip"
              :class="{ 'is-active': !filterCategory }"
              role="tab"
              :aria-selected="!filterCategory"
              @click="selectCategory('')"
            >
              {{ $t('news.filter_all') }}
            </button>
            <button
              v-for="c in categories"
              :key="c"
              class="chip chip-jp"
              role="tab"
              :aria-selected="filterCategory === c"
              :class="{ 'is-active': filterCategory === c }"
              lang="ja"
              @click="selectCategory(c)"
            >
              {{ c }}
            </button>
          </div>
        </div>

        <div class="filter-group">
          <span class="filter-label">{{ $t('news.date') }}</span>
          <input
            type="date"
            class="date-input"
            v-model="filterDate"
            @change="fetchArticles"
          />
        </div>

        <button
          v-if="filterCategory || filterDate"
          class="filter-clear"
          @click="clearFilters"
        >
          {{ $t('news.clear_filters') }}
        </button>
      </div>

      <!-- Loading ------------------------------------------------ -->
      <div v-if="loading" class="empty-state">
        {{ $t('news.loading_articles') }}
      </div>

      <template v-else>
        <!-- Lead article -------------------------------------- -->
        <section v-if="leadArticle" class="lead-article" @click="openArticle(leadArticle)">
          <div class="lead-headline-wrap">
            <div class="lead-eyebrow">
              <span class="lead-lead">{{ $t('news.top_story') }}</span>
              <span class="lead-rule" aria-hidden="true" />
              <span v-if="leadArticle.category" class="lead-category" lang="ja">
                {{ leadArticle.category }}
              </span>
            </div>
            <h2 class="lead-headline" lang="ja">
              {{ leadArticle.title }}
            </h2>
            <div v-if="leadArticle.publish_timestamp" class="lead-meta-row">
              <span class="lead-date">{{ formatShortDate(leadArticle.publish_timestamp) }}</span>
              <span class="lead-meta-dot" aria-hidden="true" />
              <span>{{ formatTime(leadArticle.publish_timestamp) }}</span>
            </div>
          </div>
        </section>

        <!-- Today's Edition grid ------------------------------ -->
        <template v-if="restArticles.length">
          <div class="section-title-row">
            <h3 class="section-title">{{ $t('news.todays_edition') }}</h3>
            <span class="section-count">
              {{ $t('news.articles_count', { n: filtered.length }) }}
            </span>
          </div>
          <div class="article-grid">
            <article
              v-for="a in restArticles"
              :key="a.article_id"
              class="article-card"
              tabindex="0"
              @click="openArticle(a)"
              @keydown.enter="openArticle(a)"
            >
              <div class="article-meta">
                <span v-if="a.category" class="article-category" lang="ja">{{ a.category }}</span>
                <span v-if="a.publish_timestamp" class="article-date">
                  {{ formatTime(a.publish_timestamp) }}
                </span>
              </div>
              <h4 class="article-headline" lang="ja">{{ a.title }}</h4>
            </article>
          </div>
        </template>

        <!-- Empty state -------------------------------------- -->
        <div v-if="filtered.length === 0" class="empty-state">
          {{ $t('news.empty_desk') }}
        </div>
      </template>
    </div>
  </main>
</template>

<style scoped>
/* --------------------------------------------------------------
   Warm paper surface — mirrors ExerciseView's vertical gradient.
-------------------------------------------------------------- */
/* .news-shell also carries the global `.ei-shell-bg` utility for the
   paper gradient; this block just adds the per-view min-height. */
.news-shell {
  min-height: calc(100vh - var(--app-chrome-h));
}

.list-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 56px 48px 96px;
  width: 100%;
}
@media (max-width: 720px) {
  .list-page { padding: 32px 20px 72px; }
}

/* Masthead ---------------------------------------------------- */
.masthead {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: end;
  padding-bottom: 24px;
  border-bottom: 2px solid var(--foreground);
  margin-bottom: 6px;
  gap: 32px;
}
.masthead-title {
  font-family: var(--font-serif);
  font-size: clamp(2.6rem, 5vw + 0.5rem, 4.2rem);
  line-height: 0.95;
  margin: 0;
  letter-spacing: -0.01em;
  font-weight: 500;
}
.masthead-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  padding-bottom: 8px;
}
.masthead-meta .date {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 1rem;
  color: color-mix(in oklab, var(--foreground) 75%, transparent);
}
.masthead-meta .issue {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.62rem;
  color: var(--secondary);
}
.masthead-rule {
  height: 1px;
  background: var(--foreground);
  margin-bottom: 40px;
}
@media (max-width: 620px) {
  .masthead { grid-template-columns: 1fr; align-items: start; }
  .masthead-meta { align-items: flex-start; }
}

/* Filter bar primitives (.filter-bar/.chip/.filter-clear) are global —
   see styles/editorial.css. This block keeps only view-specific extras. */
.chip-jp {
  font-family: var(--font-sans), 'Noto Sans JP';
  font-size: 0.85rem;
}
.date-input {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.95rem;
  border: none;
  background: transparent;
  border-bottom: 1px solid var(--input);
  padding: 4px 0;
  color: var(--foreground);
  outline: none;
  min-width: 140px;
  cursor: pointer;
}
.date-input:focus { border-bottom-color: var(--primary); }

/* Lead article ----------------------------------------------- */
.lead-article {
  padding-bottom: 56px;
  margin-bottom: 48px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
  cursor: pointer;
}
.lead-headline-wrap {
  position: relative;
  padding-left: 22px;
  max-width: 44em;
}
.lead-headline-wrap::before {
  content: '';
  position: absolute;
  left: 0; top: 8px; bottom: 12%;
  width: 2px;
  background: linear-gradient(180deg, var(--secondary) 0%, transparent 100%);
}
.lead-eyebrow {
  display: flex;
  align-items: baseline;
  gap: 14px;
  margin-bottom: 18px;
}
.lead-lead {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.62rem;
  color: var(--secondary);
  font-weight: 500;
}
.lead-rule {
  height: 1px;
  flex: 1;
  background: color-mix(in oklab, var(--foreground) 12%, transparent);
}
.lead-category {
  font-size: 0.72rem;
  letter-spacing: 0.18em;
  color: var(--secondary);
  font-weight: 600;
}
.lead-headline {
  font-family: var(--font-serif);
  font-weight: 500;
  font-size: clamp(1.9rem, 2.6vw + 0.6rem, 2.9rem);
  line-height: 1.35;
  letter-spacing: 0.005em;
  margin: 0 0 22px;
  color: var(--foreground);
  word-break: auto-phrase;
  transition: color 180ms ease;
}
.lead-article:hover .lead-headline { color: var(--primary); }
.lead-meta-row {
  display: flex;
  gap: 14px;
  align-items: center;
  font-family: var(--font-sans);
  font-size: 0.78rem;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}
.lead-date {
  font-family: var(--font-serif);
  font-style: italic;
}
.lead-meta-dot {
  width: 3px; height: 3px; border-radius: 50%;
  background: var(--secondary);
}

/* .section-title-row/.section-title/.section-count are global — see
   styles/editorial.css. */
.article-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 48px 56px;
}
@media (max-width: 1000px) {
  .article-grid { grid-template-columns: repeat(2, 1fr); gap: 40px; }
}
@media (max-width: 640px) {
  .article-grid { grid-template-columns: 1fr; gap: 32px; }
}

.article-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  cursor: pointer;
  position: relative;
  padding-top: 20px;
  border-top: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
  transition: transform 200ms ease;
  background: transparent;
  text-align: left;
}
.article-card:hover { transform: translateY(-2px); }
.article-card:hover .article-headline {
  color: var(--primary);
  background-size: 100% 1px;
}
.article-card:focus-visible {
  outline: none;
}
.article-card:focus-visible .article-headline {
  color: var(--primary);
  background-size: 100% 1px;
}
.article-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}
.article-category {
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  color: var(--secondary);
  font-weight: 600;
}
.article-date {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.78rem;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
}
.article-headline {
  font-family: var(--font-serif);
  font-size: 1.15rem;
  line-height: 1.55;
  color: var(--foreground);
  margin: 0;
  font-weight: 500;
  transition: color 180ms ease, background-size 260ms ease;
  background: linear-gradient(var(--secondary), var(--secondary)) 0 100% / 0 1px no-repeat;
  word-break: auto-phrase;
}

/* Empty / loading ------------------------------------------- */
/* .empty-state is global — see styles/editorial.css. */
</style>
