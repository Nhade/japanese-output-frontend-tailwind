<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useToastStore } from '../stores/toast';

interface Video {
  video_id: string;
  title: string;
  channel_name?: string;
  category?: string;
  thumbnail_url?: string;
  duration_seconds?: number;
  publish_date?: string;
}

const { t, locale } = useI18n();
const router = useRouter();
const toast = useToastStore();

const API = import.meta.env.VITE_API_BASE_URL;

const videos = ref<Video[]>([]);
const loading = ref(true);
const filterCategory = ref('');
const importUrl = ref('');
const isImporting = ref(false);
const importError = ref('');

function intlLocale(): string {
  if (locale.value === 'ja') return 'ja-JP';
  if (locale.value === 'zh-tw') return 'zh-Hant';
  return 'en-US';
}

const todayDate = computed(() => {
  return new Intl.DateTimeFormat(intlLocale(), {
    weekday: 'long', month: 'long', day: 'numeric',
  }).format(new Date());
});

const categories = computed<string[]>(() => {
  const set = new Set<string>();
  videos.value.forEach(v => {
    if (v.category) set.add(v.category);
  });
  return Array.from(set);
});

const filtered = computed<Video[]>(() => {
  if (!filterCategory.value) return videos.value;
  return videos.value.filter(v => v.category === filterCategory.value);
});

const featured = computed<Video | null>(() => {
  // Only show the featured slot when not filtered — matches the mock's
  // "Vol. 12 · Listening Dossier" front-page convention.
  if (filterCategory.value) return null;
  return videos.value[0] ?? null;
});

const rest = computed<Video[]>(() => {
  const list = filtered.value;
  if (featured.value && !filterCategory.value) {
    return list.filter(v => v.video_id !== featured.value!.video_id);
  }
  return list;
});

function formatDuration(seconds?: number): string {
  if (!seconds && seconds !== 0) return '';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function formatRelativeDate(iso?: string): string {
  if (!iso) return '';
  const then = new Date(iso);
  const now = new Date();
  const days = Math.floor((now.getTime() - then.getTime()) / 86400000);
  if (days <= 0) return t('video.today');
  if (days === 1) return t('video.yesterday');
  if (days < 7) return t('video.days_ago', { n: days });
  if (days < 30) return t('video.weeks_ago', { n: Math.floor(days / 7) });
  return t('video.months_ago', { n: Math.floor(days / 30) });
}

async function fetchVideos() {
  loading.value = true;
  try {
    const params = new URLSearchParams();
    if (filterCategory.value) params.append('category', filterCategory.value);
    const query = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API}/api/videos${query}`);
    videos.value = await res.json();
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

function selectCategory(c: string) {
  if (filterCategory.value === c) return;
  filterCategory.value = c;
  fetchVideos();
}

async function handleImport() {
  const url = importUrl.value.trim();
  if (!url) return;
  isImporting.value = true;
  importError.value = '';
  try {
    const res = await fetch(`${API}/api/videos/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (!res.ok) {
      importError.value = data.error || 'Import failed';
      return;
    }
    toast.trigger(
      data.already_exists ? 'Video already imported' : 'Video imported successfully!',
      'success',
    );
    importUrl.value = '';
    router.push(`/videos/${data.video_id}`);
  } catch (e) {
    importError.value = 'Network error. Please try again.';
  } finally {
    isImporting.value = false;
  }
}

function openVideo(v: Video) {
  router.push(`/videos/${v.video_id}`);
}

onMounted(() => {
  fetchVideos();
});
</script>

<template>
  <main class="videos-shell text-foreground">
    <div class="list-page">
      <!-- Masthead — drops the decorative "聴" kanji (no brand anchor,
           unlike "栞" on News) and lets the serif wordmark carry the
           editorial weight on its own. -->
      <header class="masthead">
        <h1 class="masthead-title">{{ $t('nav.videos') }}</h1>
        <div class="masthead-meta">
          <span class="issue">
            {{ $t('video.dispatches_count', { n: videos.length }) }}
          </span>
          <span class="date">{{ todayDate }}</span>
        </div>
      </header>
      <div class="masthead-rule" aria-hidden="true" />

      <!-- Import row ---------------------------------------------- -->
      <div class="vid-import">
        <div class="vid-import-label">{{ $t('video.submit_dispatch') }}</div>
        <div class="vid-import-row">
          <span class="vid-import-prefix">https://</span>
          <input
            v-model="importUrl"
            type="url"
            class="vid-import-input"
            placeholder="youtube.com/watch?v=…"
            :disabled="isImporting"
            @keydown.enter="handleImport"
          />
          <button
            class="vid-import-btn"
            :disabled="isImporting || !importUrl.trim()"
            @click="handleImport"
          >
            <span v-if="isImporting">{{ $t('video.importing') }}</span>
            <span v-else>{{ $t('video.file_it') }}</span>
          </button>
        </div>
        <p v-if="importError" class="vid-import-error">{{ importError }}</p>
        <p v-else class="vid-import-hint">{{ $t('video.paste_hint') }}</p>
      </div>

      <!-- Filter bar (only if categories exist) ------------------- -->
      <div v-if="categories.length" class="filter-bar">
        <div class="filter-group">
          <span class="filter-label">{{ $t('video.programme') }}</span>
          <div class="chip-row">
            <button
              class="chip"
              :class="{ 'is-active': !filterCategory }"
              @click="selectCategory('')"
            >
              {{ $t('video.filter_all') }}
            </button>
            <button
              v-for="c in categories"
              :key="c"
              class="chip"
              :class="{ 'is-active': filterCategory === c }"
              @click="selectCategory(c)"
            >
              {{ c }}
            </button>
          </div>
        </div>
      </div>

      <!-- Loading ------------------------------------------------- -->
      <div v-if="loading" class="empty-state">
        {{ $t('video.loading') }}
      </div>

      <template v-else>
        <!-- Featured ------------------------------------------- -->
        <section v-if="featured" class="vid-featured">
          <button class="vid-featured-cover" type="button" @click="openVideo(featured)">
            <div class="thumb thumb-lg">
              <img
                v-if="featured.thumbnail_url"
                :src="featured.thumbnail_url"
                :alt="featured.title"
                loading="lazy"
              />
              <div v-else class="thumb-placeholder" aria-hidden="true">▶</div>
              <span v-if="featured.duration_seconds" class="thumb-dur">
                {{ formatDuration(featured.duration_seconds) }}
              </span>
            </div>
          </button>
          <div class="vid-featured-body">
            <div class="lead-eyebrow">
              <span class="lead-lead">{{ $t('video.on_air_featured') }}</span>
              <span class="lead-rule" />
              <span v-if="featured.category" class="lead-category" lang="ja">
                {{ featured.category }}
              </span>
            </div>
            <h2 class="lead-headline" lang="ja" @click="openVideo(featured)">
              {{ featured.title }}
            </h2>
            <div class="lead-meta-row">
              <span v-if="featured.channel_name" class="lead-date">
                {{ featured.channel_name }}
              </span>
              <span v-if="featured.duration_seconds" class="lead-meta-dot" />
              <span v-if="featured.duration_seconds">
                {{ formatDuration(featured.duration_seconds) }}
              </span>
              <span v-if="featured.publish_date" class="lead-meta-dot" />
              <span v-if="featured.publish_date">
                {{ formatRelativeDate(featured.publish_date) }}
              </span>
            </div>
            <div class="vid-featured-cta">
              <button class="vid-cta-primary" @click="openVideo(featured)">
                {{ $t('video.open_dossier') }}
              </button>
            </div>
          </div>
        </section>

        <!-- Schedule ------------------------------------------- -->
        <template v-if="rest.length">
          <div class="section-title-row">
            <h3 class="section-title">{{ $t('video.in_rotation') }}</h3>
            <span class="section-count">
              {{ $t('video.entries_count', { n: rest.length }) }}
            </span>
          </div>
          <ul class="vid-schedule">
            <li
              v-for="(v, i) in rest"
              :key="v.video_id"
              class="vid-schedule-row"
              tabindex="0"
              @click="openVideo(v)"
              @keydown.enter="openVideo(v)"
            >
              <span class="vid-sched-num">{{ String(i + 1).padStart(2, '0') }}</span>
              <div class="vid-sched-cover">
                <div class="thumb">
                  <img
                    v-if="v.thumbnail_url"
                    :src="v.thumbnail_url"
                    :alt="v.title"
                    loading="lazy"
                  />
                  <div v-else class="thumb-placeholder" aria-hidden="true">▶</div>
                </div>
              </div>
              <div class="vid-sched-body">
                <div class="vid-sched-meta">
                  <span v-if="v.category" class="vid-sched-cat" lang="ja">{{ v.category }}</span>
                  <span v-if="v.category && v.publish_date" class="vid-sched-sep" />
                  <span v-if="v.publish_date" class="vid-sched-date">
                    {{ formatRelativeDate(v.publish_date) }}
                  </span>
                </div>
                <h4 class="vid-sched-title" lang="ja">{{ v.title }}</h4>
                <div v-if="v.channel_name" class="vid-sched-sub">{{ v.channel_name }}</div>
              </div>
              <div class="vid-sched-right">
                <div v-if="v.duration_seconds" class="vid-sched-dur">
                  {{ formatDuration(v.duration_seconds) }}
                </div>
              </div>
            </li>
          </ul>
        </template>

        <!-- Empty ----------------------------------------------- -->
        <div v-if="filtered.length === 0" class="empty-state">
          {{ $t('video.no_videos') }}
        </div>
      </template>
    </div>
  </main>
</template>

<style scoped>
.videos-shell {
  min-height: calc(100vh - 4rem);
  background-image: linear-gradient(
    180deg,
    var(--background) 0%,
    var(--surface-container-low) 100%
  );
}
.list-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 56px 48px 96px;
  width: 100%;
}
@media (max-width: 720px) { .list-page { padding: 32px 20px 72px; } }

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
.masthead-lede { min-width: 0; }
.masthead-eyebrow { margin-bottom: 14px; }
.masthead-title {
  font-family: var(--font-serif);
  font-size: clamp(2.4rem, 4.6vw + 0.5rem, 3.8rem);
  line-height: 0.95;
  margin: 0;
  letter-spacing: -0.01em;
  font-weight: 500;
}
.masthead-title .kanji {
  font-family: var(--font-serif);
  color: var(--primary);
  margin-right: 0.2em;
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
  margin-bottom: 32px;
}
@media (max-width: 620px) {
  .masthead { grid-template-columns: 1fr; align-items: start; }
  .masthead-meta { align-items: flex-start; }
}

/* Editorial helpers (shared with news list) ----------------- */
.eyebrow {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.68rem;
  font-weight: 500;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}
.eyebrow-kohaku { color: var(--secondary); }

/* Import row -------------------------------------------------- */
.vid-import {
  padding: 22px 0 26px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
  margin-bottom: 4px;
}
.vid-import-label {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.62rem;
  color: var(--secondary);
  font-weight: 500;
  margin-bottom: 10px;
}
.vid-import-row {
  display: flex;
  align-items: baseline;
  /* No flex gap — the prefix must read flush with the URL, like one
     continuous address. Button keeps its own margin below. */
  border-bottom: 1px solid var(--input);
  padding-bottom: 6px;
}
.vid-import-prefix {
  font-family: var(--font-sans);
  color: color-mix(in oklab, var(--foreground) 45%, transparent);
  font-size: 0.95rem;
}
.vid-import-input {
  flex: 1;
  border: none;
  background: transparent;
  font-family: var(--font-sans);
  font-size: 0.95rem;
  color: var(--foreground);
  outline: none;
  padding: 4px 0;
}
.vid-import-input::placeholder {
  color: color-mix(in oklab, var(--foreground) 38%, transparent);
}
.vid-import-input:disabled { opacity: 0.5; }
.vid-import-btn {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--primary);
  background: none;
  border: none;
  padding: 6px 0;
  margin-left: 16px;
  cursor: pointer;
  border-bottom: 1px solid transparent;
  transition: border-color 180ms ease, opacity 180ms ease;
  white-space: nowrap;
}
.vid-import-btn:hover:not(:disabled) { border-bottom-color: var(--secondary); }
.vid-import-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.vid-import-hint,
.vid-import-error {
  margin: 10px 0 0;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.82rem;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}
.vid-import-error { color: var(--tertiary); font-style: normal; }

/* Filter bar (reuses news list language) -------------------- */
.filter-bar {
  display: flex;
  align-items: baseline;
  gap: 40px;
  flex-wrap: wrap;
  padding: 18px 0 24px;
  margin-top: 16px;
  margin-bottom: 24px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
}
.filter-group {
  display: flex;
  align-items: baseline;
  gap: 14px;
}
.filter-label {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.62rem;
  font-weight: 500;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
}
.chip-row { display: flex; gap: 4px; flex-wrap: wrap; }
.chip {
  font-family: var(--font-sans);
  font-size: 0.78rem;
  padding: 6px 12px;
  color: color-mix(in oklab, var(--foreground) 65%, transparent);
  background: transparent;
  border: none;
  cursor: pointer;
  border-bottom: 1px solid transparent;
  transition: color 160ms ease, border-color 160ms ease;
  letter-spacing: 0.01em;
}
.chip:hover { color: var(--foreground); }
.chip.is-active {
  color: var(--primary);
  border-bottom-color: var(--secondary);
  font-weight: 500;
}

/* Thumbnail frame (real YouTube thumb, editorial framing) --- */
.thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 3px;
  overflow: hidden;
  background: var(--surface-container-high);
}
.thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.thumb-placeholder {
  position: absolute; inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-serif);
  font-size: 2rem;
  color: color-mix(in oklab, var(--foreground) 45%, transparent);
}
.thumb-dur {
  position: absolute;
  right: 10px;
  bottom: 10px;
  font-family: var(--font-sans);
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  padding: 4px 8px;
  background: color-mix(in oklab, #000 60%, transparent);
  color: rgba(255,255,255,0.95);
  border-radius: 2px;
  font-variant-numeric: tabular-nums;
}
.thumb-lg { aspect-ratio: 16 / 10; }

/* Featured video --------------------------------------------- */
.vid-featured {
  display: grid;
  grid-template-columns: 6fr 6fr;
  gap: 56px;
  padding: 32px 0 48px;
  margin-bottom: 32px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
  align-items: center;
}
@media (max-width: 900px) {
  .vid-featured { grid-template-columns: 1fr; gap: 28px; }
}
.vid-featured-cover {
  cursor: pointer;
  transition: transform 260ms ease;
  background: none;
  border: none;
  padding: 0;
  font-family: inherit;
  color: inherit;
}
.vid-featured-cover:hover { transform: translateY(-2px); }

.vid-featured-body { display: flex; flex-direction: column; gap: 18px; }

.lead-eyebrow {
  display: flex;
  align-items: baseline;
  gap: 14px;
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
  font-size: clamp(1.6rem, 2.2vw + 0.5rem, 2.4rem);
  line-height: 1.35;
  letter-spacing: 0.005em;
  margin: 0;
  color: var(--foreground);
  word-break: auto-phrase;
  cursor: pointer;
  transition: color 180ms ease;
}
.lead-headline:hover { color: var(--primary); }
.lead-meta-row {
  display: flex;
  gap: 14px;
  align-items: center;
  font-family: var(--font-sans);
  font-size: 0.78rem;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  flex-wrap: wrap;
}
.lead-date { font-family: var(--font-serif); font-style: italic; }
.lead-meta-dot {
  width: 3px; height: 3px; border-radius: 50%;
  background: var(--secondary);
}
.vid-featured-cta {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-top: 4px;
}
.vid-cta-primary {
  font-family: var(--font-sans);
  font-size: 0.72rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--background);
  background: var(--primary);
  border: none;
  padding: 12px 22px;
  border-radius: 2px;
  cursor: pointer;
  font-weight: 500;
  transition: background 180ms ease;
}
.vid-cta-primary:hover { background: var(--primary-container); }

/* Section title row ----------------------------------------- */
.section-title-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 14px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
}
.section-title {
  font-family: var(--font-serif);
  font-size: 1.3rem;
  color: var(--foreground);
  margin: 0;
  font-weight: 500;
}
.section-count {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
}

/* Rotation list --------------------------------------------- */
.vid-schedule {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
}
.vid-schedule-row {
  display: grid;
  grid-template-columns: 56px 220px 1fr auto;
  gap: 28px;
  align-items: center;
  padding: 22px 0;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
  cursor: pointer;
  transition: padding-left 220ms ease;
}
.vid-schedule-row:hover { padding-left: 6px; }
.vid-schedule-row:hover .vid-sched-title { color: var(--primary); }
.vid-schedule-row:focus-visible {
  outline: none;
  padding-left: 6px;
}
.vid-schedule-row:focus-visible .vid-sched-title { color: var(--primary); }
.vid-schedule-row:last-child { border-bottom: none; }
.vid-sched-num {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 1.1rem;
  color: color-mix(in oklab, var(--foreground) 40%, transparent);
  font-variant-numeric: tabular-nums;
}
.vid-sched-cover .thumb {
  aspect-ratio: 16 / 9;
}
.vid-sched-body { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.vid-sched-meta {
  display: flex;
  gap: 12px;
  align-items: baseline;
  font-family: var(--font-sans);
  font-size: 0.7rem;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
  flex-wrap: wrap;
}
.vid-sched-cat { color: var(--secondary); font-weight: 500; }
.vid-sched-sep {
  width: 12px;
  height: 1px;
  background: color-mix(in oklab, var(--foreground) 15%, transparent);
  display: inline-block;
}
.vid-sched-date { font-family: var(--font-serif); font-style: italic; }
.vid-sched-title {
  font-family: var(--font-serif);
  font-size: 1.08rem;
  line-height: 1.5;
  margin: 0;
  font-weight: 500;
  color: var(--foreground);
  transition: color 180ms ease;
  word-break: auto-phrase;
}
.vid-sched-sub {
  font-family: var(--font-sans);
  font-size: 0.78rem;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}
.vid-sched-right { text-align: right; }
.vid-sched-dur {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.9rem;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  font-variant-numeric: tabular-nums;
}
@media (max-width: 720px) {
  .vid-schedule-row {
    grid-template-columns: 40px 140px 1fr;
    gap: 14px;
  }
  .vid-sched-right { display: none; }
}

/* Empty ------------------------------------------------------ */
.empty-state {
  padding: 72px 0;
  text-align: center;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 1.05rem;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}
</style>
