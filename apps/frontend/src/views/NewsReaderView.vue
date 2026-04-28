<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { apiUrl } from '../lib/api';

interface Paragraph {
  text: string;
  translation?: string;
  showTranslation?: boolean;
  loadingTranslation?: boolean;
}

interface Article {
  info: {
    title: string;
    category: string;
    date: string;
  };
  paragraphs: Paragraph[];
}

interface ListEntry {
  article_id: string;
  title: string;
  category?: string;
  publish_timestamp?: string | null;
}

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();

const article = ref<Article | null>(null);
const loading = ref(true);
const nextArticle = ref<ListEntry | null>(null);

const isPlaying = ref(false);
const playingIndex = ref<number>(-1);
const currentAudio = ref<HTMLAudioElement | null>(null);

const showAllTranslations = ref(false);
const progress = ref(0);

// Tracks which paragraph's margin actions should be surfaced. Only one
// paragraph may be "hovered" at a time so the reader isn't visually noisy
// with every paragraph's controls fighting for attention.
const hoveredIndex = ref<number>(-1);

function maybeClearHover(i: number, e: MouseEvent) {
  // Margin actions are absolutely positioned outside the wrap's bounding
  // box, so moving cursor from the paragraph into them fires mouseleave on
  // the wrap. Keep the hover state if we're still inside the same
  // paragraph's territory (wrap OR its margin-actions), detected via the
  // shared data-p-idx attribute.
  const related = e.relatedTarget as Element | null;
  if (related && typeof related.closest === 'function'
      && related.closest(`[data-p-idx="${i}"]`)) {
    return;
  }
  if (hoveredIndex.value === i) hoveredIndex.value = -1;
}

// -- derived ------------------------------------------------------
const readMinutes = computed(() => {
  if (!article.value) return 0;
  const chars = article.value.paragraphs.reduce((n, p) => n + [...p.text].length, 0);
  // ~400 Japanese characters per minute is a common reading-speed heuristic.
  return Math.max(1, Math.round(chars / 400));
});

function intlLocale(): string {
  if (locale.value === 'ja') return 'ja-JP';
  if (locale.value === 'zh-tw') return 'zh-Hant';
  return 'en-US';
}

const dateStr = computed(() => {
  if (!article.value?.info?.date) return '';
  return new Intl.DateTimeFormat(intlLocale(), {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  }).format(new Date(article.value.info.date));
});

const timeStr = computed(() => {
  if (!article.value?.info?.date) return '';
  const d = new Date(article.value.info.date);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
});

// -- scroll progress ----------------------------------------------
function onScroll() {
  const el = document.documentElement;
  const total = el.scrollHeight - el.clientHeight;
  progress.value = total > 0 ? (el.scrollTop / total) * 100 : 0;
}

// -- data fetching ------------------------------------------------
async function fetchArticle(id: string) {
  loading.value = true;
  article.value = null;
  try {
    const res = await fetch(`${apiUrl('/api/news/')}${id}`);
    if (!res.ok) throw new Error('Failed to fetch article');
    article.value = await res.json();
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

async function fetchNextArticle(currentId: string) {
  // Use the list endpoint to pick the next article after the current one.
  // Fallback: wrap around to the first article.
  try {
    const res = await fetch(`${apiUrl('/api/news')}`);
    if (!res.ok) return;
    const list: ListEntry[] = await res.json();
    if (!list.length) return;
    const idx = list.findIndex(a => a.article_id === currentId);
    if (idx < 0) {
      nextArticle.value = list[0];
    } else {
      nextArticle.value = list[(idx + 1) % list.length];
    }
  } catch (e) {
    console.error(e);
  }
}

// -- translation --------------------------------------------------
async function toggleTranslation(index: number) {
  if (!article.value) return;
  const para = article.value.paragraphs[index];

  if (para.showTranslation) {
    para.showTranslation = false;
    return;
  }

  para.showTranslation = true;

  if (para.translation) return;

  para.loadingTranslation = true;
  try {
    const res = await fetch(`${apiUrl('/api/translate')}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: para.text,
        target: locale.value === 'ja' ? 'zh-Hant' : locale.value,
      }),
    });
    const data = await res.json();
    para.translation = data.translated_text;
  } catch (e) {
    console.error(e);
    para.translation = t('news.translation_failed');
  } finally {
    para.loadingTranslation = false;
  }
}

async function toggleAllTranslations() {
  if (!article.value) return;
  const turningOn = !showAllTranslations.value;
  showAllTranslations.value = turningOn;

  if (!turningOn) {
    article.value.paragraphs.forEach(p => { p.showTranslation = false; });
    return;
  }

  const pending: Promise<void>[] = [];
  article.value.paragraphs.forEach((_, i) => {
    const para = article.value!.paragraphs[i];
    if (!para.showTranslation) {
      pending.push(toggleTranslation(i));
    }
  });
  await Promise.all(pending);
}

// -- TTS ----------------------------------------------------------
async function playAudio(index: number) {
  if (!article.value) return;
  const para = article.value.paragraphs[index];

  if (isPlaying.value) {
    currentAudio.value?.pause();
    currentAudio.value = null;
    const wasSame = playingIndex.value === index;
    isPlaying.value = false;
    playingIndex.value = -1;
    if (wasSame) return;
  }

  isPlaying.value = true;
  playingIndex.value = index;

  try {
    const res = await fetch(`${apiUrl('/api/tts')}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: para.text }),
    });
    if (!res.ok) throw new Error('TTS failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    currentAudio.value = audio;
    audio.onended = () => {
      isPlaying.value = false;
      playingIndex.value = -1;
      currentAudio.value = null;
      URL.revokeObjectURL(url);
    };
    await audio.play();
  } catch (e) {
    console.error(e);
    isPlaying.value = false;
    playingIndex.value = -1;
    currentAudio.value = null;
    alert(t('news.audio_error'));
  }
}

// -- navigation ---------------------------------------------------
function goBack() {
  router.push('/news');
}

function openArticle(entry: ListEntry | null) {
  if (!entry) return;
  router.push(`/news/${entry.article_id}`);
}

// -- lifecycle ----------------------------------------------------
onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  const id = String(route.params.id);
  fetchArticle(id);
  fetchNextArticle(id);
});

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll);
  if (currentAudio.value) {
    currentAudio.value.pause();
    currentAudio.value = null;
  }
});

watch(() => route.params.id, async (newId) => {
  if (!newId) return;
  window.scrollTo({ top: 0 });
  await nextTick();
  await fetchArticle(String(newId));
  await fetchNextArticle(String(newId));
});
</script>

<template>
  <main class="reader-shell ei-shell-bg text-foreground">
    <!-- Kohaku ink-wash scroll progress -->
    <div class="progress-wash" :style="{ width: `${progress}%` }" aria-hidden="true" />

    <div class="reader-page">
      <button class="reader-back" @click="goBack">
        <span class="arrow">←</span> {{ $t('news.back_to_edition') }}
      </button>

      <div v-if="loading" class="reader-loading">
        {{ $t('news.loading_article') }}
      </div>

      <template v-else-if="article">
        <!-- Masthead ----------------------------------------- -->
        <header class="reader-masthead">
          <div class="reader-meta-row">
            <span v-if="article.info.category" class="reader-cat" lang="ja">
              {{ article.info.category }}
            </span>
            <span v-if="article.info.category" class="reader-sep" aria-hidden="true" />
            <span class="reader-date">{{ dateStr }}<template v-if="timeStr"> · {{ timeStr }}</template></span>
            <span class="reader-sep" aria-hidden="true" />
            <span class="reader-readtime">
              {{ $t('news.min_read', { n: readMinutes }) }}
            </span>
          </div>
          <h1 class="reader-title" lang="ja">{{ article.info.title }}</h1>

          <div class="reader-toolbar">
            <button
              class="reader-tool"
              :class="{ 'is-active': showAllTranslations }"
              @click="toggleAllTranslations"
            >
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" aria-hidden="true">
                <path d="M2 4 L7 4 M4.5 4 L4.5 12 M2 8 L7 8" />
                <path d="M9 12 L11.5 6 L14 12 M9.8 10 L13.2 10" />
              </svg>
              {{ showAllTranslations ? $t('news.hide_all_translations') : $t('news.show_all_translations') }}
            </button>
            <button class="reader-tool" @click="playAudio(0)">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" aria-hidden="true">
                <path d="M4 3 L13 8 L4 13 Z" fill="currentColor" stroke="none" />
              </svg>
              {{ $t('news.read_aloud') }}
            </button>
          </div>
        </header>

        <!-- Article body ------------------------------------- -->
        <div class="article-body">
          <div class="reader-grid">
            <div
              v-for="(para, i) in article.paragraphs"
              :key="i"
              :data-p-idx="i"
              class="paragraph-wrap"
              :class="{
                'is-active': playingIndex === i || para.showTranslation || hoveredIndex === i,
              }"
              @mouseenter="hoveredIndex = i"
              @mouseleave="maybeClearHover(i, $event)"
            >
              <div
                class="paragraph"
                :class="{
                  'is-playing': playingIndex === i,
                }"
              >
                <span class="paragraph-num">¶ {{ String(i + 1).padStart(2, '0') }}</span>
                <p lang="ja">{{ para.text }}</p>

                <div v-if="para.showTranslation" class="translation" lang="zh-Hant">
                  <span class="tn-eyebrow">{{ $t('news.margin_note') }}</span>
                  <span v-if="para.loadingTranslation" class="translation-loading">
                    {{ $t('news.translating') }}
                  </span>
                  <template v-else>{{ para.translation }}</template>
                </div>
              </div>

              <div
                :data-p-idx="i"
                class="margin-actions"
                @mouseenter="hoveredIndex = i"
                @mouseleave="maybeClearHover(i, $event)"
              >
                <button
                  class="margin-action"
                  :class="{ 'is-on': playingIndex === i }"
                  @click="playAudio(i)"
                  :aria-label="$t('news.listen')"
                >
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
                    <rect v-if="playingIndex === i" x="4" y="4" width="8" height="8" />
                    <path v-else d="M4 3 L13 8 L4 13 Z" fill="currentColor" stroke="none" />
                  </svg>
                  {{ playingIndex === i ? $t('news.stop') : $t('news.listen') }}
                </button>
                <button
                  class="margin-action"
                  :class="{ 'is-on': para.showTranslation }"
                  @click="toggleTranslation(i)"
                  :aria-label="$t('news.translate')"
                >
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" aria-hidden="true">
                    <path d="M2 4 L7 4 M4.5 4 L4.5 12 M2 8 L7 8" />
                    <path d="M9 12 L11.5 6 L14 12 M9.8 10 L13.2 10" />
                  </svg>
                  {{ para.showTranslation ? $t('news.hide') : $t('news.translate') }}
                </button>
              </div>
            </div>
          </div>

          <!-- End-of-article signature -------------------- -->
          <div class="article-end">
            <p class="end-note">{{ $t('news.end_note') }}</p>
            <div
              class="hanko-seal"
              role="img"
              :aria-label="$t('news.end_of_article')"
            >
              <span lang="ja">了</span>
            </div>
          </div>

          <!-- Next article -------------------------------- -->
          <button
            v-if="nextArticle"
            class="next-article"
            @click="openArticle(nextArticle)"
          >
            <div class="next-article-body">
              <span class="next-article-eyebrow">{{ $t('news.read_next') }}</span>
              <h4 class="next-article-title" lang="ja">{{ nextArticle.title }}</h4>
            </div>
            <span class="next-article-arrow" aria-hidden="true">→</span>
          </button>
        </div>
      </template>

      <div v-else class="reader-loading">
        {{ $t('news.article_not_found') }}
      </div>
    </div>
  </main>
</template>

<style scoped>
.reader-shell {
  min-height: calc(100vh - var(--app-chrome-h));
  position: relative;
  /* paper gradient comes from the global .ei-shell-bg utility */
}

.reader-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 48px 120px;
  width: 100%;
  position: relative;
}
@media (max-width: 720px) {
  .reader-page { padding: 24px 20px 96px; }
}

/* Kohaku ink-wash scroll progress --------------------------- */
.progress-wash {
  position: fixed;
  top: 0; left: 0;
  height: 3px;
  background: linear-gradient(
    90deg,
    var(--secondary) 0%,
    color-mix(in oklab, var(--secondary) 40%, transparent) 100%
  );
  z-index: 50;
  transition: width 60ms linear;
  pointer-events: none;
}

/* Back link --------------------------------------------------- */
/* .reader-back is global — see styles/editorial.css. */
.reader-back { margin-bottom: 40px; }

.reader-loading {
  padding: 96px 0;
  text-align: center;
  font-family: var(--font-serif);
  font-style: italic;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}

/* Masthead ---------------------------------------------------- */
.reader-masthead {
  padding-bottom: 40px;
  margin-bottom: 56px;
  border-bottom: 1px solid var(--foreground);
}
.reader-meta-row {
  display: flex;
  align-items: baseline;
  gap: 20px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}
.reader-cat {
  font-size: 0.78rem;
  letter-spacing: 0.16em;
  color: var(--secondary);
  font-weight: 600;
}
.reader-sep {
  width: 24px;
  height: 1px;
  background: color-mix(in oklab, var(--foreground) 15%, transparent);
}
.reader-date {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.9rem;
  color: color-mix(in oklab, var(--foreground) 70%, transparent);
}
.reader-readtime {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.62rem;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
}

.reader-title {
  font-family: var(--font-serif);
  font-weight: 500;
  font-size: clamp(2rem, 3.2vw + 0.6rem, 3.3rem);
  line-height: 1.4;
  letter-spacing: 0.005em;
  color: var(--foreground);
  margin: 0 0 28px;
  max-width: 24em;
  word-break: auto-phrase;
}

.reader-toolbar {
  display: flex;
  align-items: center;
  gap: 28px;
  padding-top: 20px;
  border-top: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
  flex-wrap: wrap;
}
.reader-tool {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-sans);
  font-size: 0.72rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  padding: 8px 0;
  border: none;
  background: none;
  cursor: pointer;
  border-bottom: 1px solid transparent;
  transition: color 160ms ease, border-color 160ms ease;
}
.reader-tool:hover { color: var(--primary); border-bottom-color: var(--secondary); }
.reader-tool.is-active {
  color: var(--primary);
  border-bottom-color: var(--primary);
  font-weight: 500;
}
.reader-tool svg { width: 14px; height: 14px; }

/* Article body ------------------------------------------------ */
.article-body {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0;
  position: relative;
}

.reader-grid {
  max-width: 44em;
  position: relative;
}

.paragraph-wrap {
  position: relative;
}

.paragraph {
  position: relative;
  padding: 10px 0 10px 24px;
  margin-left: -24px;
  border-left: 2px solid transparent;
  transition: border-color 240ms ease;
}
.paragraph-wrap:hover .paragraph,
.paragraph-wrap.is-active .paragraph {
  border-left-color: var(--secondary);
}
.paragraph.is-playing {
  border-left-color: var(--primary);
}
.paragraph p {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 1.22rem;
  line-height: 1.85;
  letter-spacing: 0.02em;
  color: var(--foreground);
  word-break: auto-phrase;
}
.paragraph-num {
  position: absolute;
  left: -54px;
  top: 14px;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.8rem;
  color: color-mix(in oklab, var(--foreground) 35%, transparent);
  font-variant-numeric: tabular-nums;
}
@media (max-width: 720px) {
  .paragraph-num { position: static; display: block; margin-bottom: 6px; }
  .paragraph { padding-left: 16px; margin-left: -16px; }
}

/* Margin affordances — absolutely positioned in the right gutter, so
   they don't reserve any vertical space between paragraphs. Only the
   currently-active paragraph's actions are surfaced.

   Notes on clickability: the margin-actions sit 28px outside the wrap's
   bounding box, so traversing the gap momentarily fires mouseleave on
   the wrap before mouseenter lands on the actions. To keep the buttons
   reliably clickable we (a) keep pointer-events: auto even when hidden,
   and (b) delay the fade-out by 150ms so a rapid traverse back to the
   actions never leaves them in an un-clickable visual state. */
.margin-actions {
  position: absolute;
  top: 0;
  left: calc(100% + 28px);
  width: 130px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-left: 14px;
  border-left: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
  opacity: 0;
  transform: translateX(-6px);
  transition: opacity 220ms ease 150ms, transform 220ms ease 150ms;
  pointer-events: auto;
}
.paragraph-wrap.is-active .margin-actions {
  opacity: 1;
  transform: translateX(0);
  transition-delay: 0ms;
}
.margin-action {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-sans);
  font-size: 0.68rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  background: none;
  border: none;
  padding: 4px 0;
  cursor: pointer;
  text-align: left;
  transition: color 160ms ease;
}
.margin-action:hover { color: var(--primary); }
.margin-action.is-on { color: var(--secondary); font-weight: 500; }
.margin-action svg { width: 12px; height: 12px; opacity: 0.7; flex-shrink: 0; }

/* On narrow viewports where a right-gutter is impractical, drop the
   margin actions inline underneath the paragraph. */
@media (max-width: 960px) {
  .margin-actions {
    position: static;
    width: auto;
    padding: 10px 0 0;
    border-left: none;
    flex-direction: row;
    gap: 18px;
    opacity: 1;
    transform: none;
    pointer-events: auto;
  }
}

/* Translation — hanging margin note, italic serif at ~80%. --- */
.translation {
  margin-top: 14px;
  padding: 14px 0 14px 20px;
  border-left: 1px solid var(--secondary);
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.95rem;
  line-height: 1.8;
  color: color-mix(in oklab, var(--foreground) 72%, transparent);
  max-width: 40em;
  animation: tn-in 340ms ease both;
}
.translation .tn-eyebrow {
  display: block;
  font-family: var(--font-sans);
  font-style: normal;
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.6rem;
  color: var(--secondary);
  margin-bottom: 6px;
}
.translation-loading { opacity: 0.6; font-style: italic; }
@keyframes tn-in {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* End of article --------------------------------------------- */
.article-end {
  margin-top: 72px;
  padding-top: 40px;
  border-top: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}
.end-note {
  font-family: var(--font-serif);
  font-style: italic;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  font-size: 0.95rem;
  max-width: 30em;
  margin: 0;
}
.hanko-seal {
  width: 72px; height: 72px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--destructive);
  color: var(--destructive);
  font-family: var(--font-serif);
  font-weight: 600;
  border-radius: 3px;
  transform: rotate(-4deg);
  flex-shrink: 0;
}
.hanko-seal span {
  /* Explicit serif — matches the .kanji fix in the list view: the
     [lang="ja"] global rule would otherwise pick Noto Sans JP. */
  font-family: var(--font-serif);
  font-weight: 600;
  font-size: 1.6rem;
  line-height: 1;
}

/* Next article ----------------------------------------------- */
.next-article {
  margin-top: 56px;
  padding: 28px 32px;
  background: var(--surface-container-low);
  border-radius: 6px;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 28px;
  cursor: pointer;
  width: 100%;
  text-align: left;
  border: none;
  font-family: inherit;
  color: inherit;
  transition: background 200ms ease;
}
.next-article:hover { background: var(--surface-container); }
.next-article-body { min-width: 0; }
.next-article-eyebrow {
  display: block;
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.62rem;
  color: var(--secondary);
  margin-bottom: 6px;
}
.next-article-title {
  font-family: var(--font-serif);
  font-size: 1.1rem;
  line-height: 1.5;
  color: var(--foreground);
  margin: 0;
  font-weight: 500;
  max-width: 34em;
  word-break: auto-phrase;
}
.next-article-arrow {
  font-family: var(--font-serif);
  font-size: 1.4rem;
  color: var(--primary);
  font-style: italic;
}
</style>
