<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useI18n } from 'vue-i18n';
import MarkdownIt from 'markdown-it';

import { useAuthStore } from '../stores/auth';

interface Mistake {
  log_id: string;
  question_sentence: string;
  user_answer: string;
  correct_answer: string;
  feedback?: string | null;
  score?: number | null;
  error_type?: string | null;
}

const BLANK_MARKER = '[＿＿＿]';

const { t } = useI18n();
const auth = useAuthStore();

const md = new MarkdownIt({ html: true, linkify: true, typographer: true });

const mistakes = ref<Mistake[]>([]);
const isLoading = ref(true);
const error = ref('');

const filterType = ref<string>('all');

const dailyReview = ref('');
const isAgentWorking = ref(false);
const agentStatus = ref('');
const showReviewDialog = ref(false);

const filtered = computed<Mistake[]>(() =>
  filterType.value === 'all'
    ? mistakes.value
    : mistakes.value.filter(m => (m.error_type || 'other') === filterType.value),
);

const typesPresent = computed<string[]>(() => {
  const s = new Set<string>();
  mistakes.value.forEach(m => {
    if (m.error_type) s.add(m.error_type);
  });
  return Array.from(s);
});

function localizedErrorType(id?: string | null): string {
  if (!id) return '';
  return t(`error_type.${id}`, id);
}

function splitSentence(sentence: string): { before: string; after: string; hasBlank: boolean } {
  const idx = sentence.indexOf(BLANK_MARKER);
  if (idx === -1) return { before: sentence, after: '', hasBlank: false };
  return {
    before: sentence.slice(0, idx),
    after: sentence.slice(idx + BLANK_MARKER.length),
    hasBlank: true,
  };
}

// -------- Daily review ---------------------------------------
let stepInterval: ReturnType<typeof setInterval> | null = null;

function simulateAgentThinking() {
  const steps = [
    t('mistakes.analyse_step_1'),
    t('mistakes.analyse_step_2'),
    t('mistakes.analyse_step_3'),
    t('mistakes.analyse_step_4'),
  ];
  let i = 0;
  agentStatus.value = steps[0];
  stepInterval = setInterval(() => {
    i = (i + 1) % steps.length;
    if (!isAgentWorking.value) {
      if (stepInterval) clearInterval(stepInterval);
      return;
    }
    agentStatus.value = steps[i];
  }, 1800);
}

async function generateReview() {
  if (!auth.user_id || isAgentWorking.value) return;
  isAgentWorking.value = true;
  dailyReview.value = '';
  simulateAgentThinking();
  try {
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/agent/daily_review/${auth.user_id}`);
    const data = await res.json();
    if (res.ok) {
      dailyReview.value = data.review;
      showReviewDialog.value = true;
    } else {
      console.error('Agent error:', data.error);
    }
  } catch (e) {
    console.error(e);
  } finally {
    isAgentWorking.value = false;
    agentStatus.value = '';
    if (stepInterval) { clearInterval(stepInterval); stepInterval = null; }
  }
}

function openReview() {
  if (dailyReview.value) showReviewDialog.value = true;
}

function reviewCardHeadline(): string {
  if (isAgentWorking.value) return agentStatus.value || t('mistakes.analyzing');
  if (dailyReview.value) return t('mistakes.review_ready');
  return t('mistakes.generate_review');
}

function reviewCardSub(): string {
  if (isAgentWorking.value) return t('mistakes.review_analysing_sub');
  if (dailyReview.value) return t('mistakes.review_ready_sub');
  return t('mistakes.review_default_sub');
}

function onReviewCardClick() {
  if (isAgentWorking.value) return;
  if (dailyReview.value) openReview();
  else generateReview();
}

function selectType(id: string) {
  if (filterType.value === id) return;
  filterType.value = id;
}

function clearFilter() { filterType.value = 'all'; }

function handleDialogKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && showReviewDialog.value) showReviewDialog.value = false;
}

// -------- Lifecycle ----------------------------------------------
onMounted(async () => {
  window.addEventListener('keydown', handleDialogKeydown);
  if (!auth.user_id) {
    error.value = t('mistakes.login_required');
    isLoading.value = false;
    return;
  }
  try {
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/mistakes/${auth.user_id}`);
    if (res.ok) {
      mistakes.value = await res.json();
    } else {
      const data = await res.json();
      error.value = data.error || t('mistakes.load_error');
    }
  } catch (err) {
    error.value = t('mistakes.load_error');
  } finally {
    isLoading.value = false;
  }
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleDialogKeydown);
  if (stepInterval) clearInterval(stepInterval);
});
</script>

<template>
  <main class="practice-shell text-foreground">
    <div class="practice-page">
      <!-- Quiet desk header --------------------------------- -->
      <header class="practice-header">
        <div class="practice-header-top">
          <div>
            <div class="practice-eyebrow">{{ $t('mistakes.eyebrow') }}</div>
            <h1 class="practice-h1">{{ $t('mistakes.heading') }}</h1>
          </div>
          <div v-if="!isLoading && mistakes.length > 0" class="practice-stats">
            <div class="pstat">
              <span class="pstat-n">{{ mistakes.length }}</span>
              <span class="pstat-label">{{ $t('mistakes.total_mistakes') }}</span>
            </div>
          </div>
        </div>
      </header>

      <!-- Daily review card --------------------------------- -->
      <button
        v-if="!isLoading && mistakes.length > 0"
        type="button"
        class="review-card"
        :class="{ 'is-ready': !!dailyReview, 'is-working': isAgentWorking }"
        :disabled="isAgentWorking"
        @click="onReviewCardClick"
      >
        <div class="review-card-body">
          <div class="review-card-title">{{ reviewCardHeadline() }}</div>
          <div class="review-card-sub">{{ reviewCardSub() }}</div>
        </div>
        <div class="review-card-cta" aria-hidden="true">
          <span v-if="isAgentWorking" class="review-dots">
            <span /><span /><span />
          </span>
          <svg
            v-else
            width="16" height="12" viewBox="0 0 16 12" fill="none"
          >
            <path
              d="M1 6h13m0 0L10 1m4 5l-4 5"
              stroke="currentColor"
              stroke-width="1.25"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </div>
      </button>

      <!-- Filter bar ---------------------------------------- -->
      <div v-if="!isLoading && typesPresent.length > 1" class="filter-bar practice-filter-bar">
        <div class="filter-group">
          <span class="filter-label">{{ $t('mistakes.type_filter') }}</span>
          <div class="chip-row">
            <button
              class="chip"
              :class="{ 'is-active': filterType === 'all' }"
              type="button"
              @click="selectType('all')"
            >
              {{ $t('mistakes.filter_all') }}
            </button>
            <button
              v-for="id in typesPresent"
              :key="id"
              class="chip"
              :class="{ 'is-active': filterType === id }"
              type="button"
              @click="selectType(id)"
            >
              {{ localizedErrorType(id) }}
            </button>
          </div>
        </div>
        <button
          v-if="filterType !== 'all'"
          class="filter-clear"
          type="button"
          @click="clearFilter"
        >
          {{ $t('mistakes.clear') }}
        </button>
      </div>

      <!-- Entries section ----------------------------------- -->
      <div
        v-if="!isLoading && mistakes.length > 0"
        class="section-title-row practice-section-row"
      >
        <h3 class="section-title">
          {{ $t('mistakes.entries') }}
          <span
            v-if="filtered.length !== mistakes.length"
            class="section-count"
          >
            {{ $t('mistakes.entries_of_total', { n: filtered.length, total: mistakes.length }) }}
          </span>
        </h3>
      </div>

      <!-- Loading / error / empty --------------------------- -->
      <div v-if="isLoading" class="practice-empty">
        <span class="empty-text">{{ $t('common.loading') }}</span>
      </div>
      <div v-else-if="error" class="practice-empty">
        <span class="empty-text">{{ error }}</span>
      </div>
      <div v-else-if="mistakes.length === 0" class="practice-empty">
        <span class="empty-text">{{ $t('mistakes.no_mistakes') }}</span>
      </div>
      <div v-else-if="filtered.length === 0" class="practice-empty">
        <span class="empty-text">{{ $t('mistakes.empty_filter') }}</span>
      </div>

      <!-- Spread entries ------------------------------------ -->
      <div v-else class="errata-list">
        <article
          v-for="(m, i) in filtered"
          :key="m.log_id"
          class="errata-entry"
        >
          <span class="errata-num">{{ String(i + 1).padStart(2, '0') }}</span>

          <div v-if="m.error_type" class="errata-head">
            <span class="errata-type-en">{{ localizedErrorType(m.error_type) }}</span>
          </div>

          <div class="errata-body">
            <p class="errata-sentence" lang="ja">
              <template v-if="splitSentence(m.question_sentence).hasBlank">
                {{ splitSentence(m.question_sentence).before }}<span
                  class="errata-strike"
                  :aria-label="`Incorrect: ${m.user_answer}`"
                >{{ m.user_answer }}</span>{{ splitSentence(m.question_sentence).after }}
              </template>
              <template v-else>{{ m.question_sentence }}</template>
            </p>

            <aside class="errata-correction" :aria-label="$t('mistakes.correction')">
              <span class="correction-rule" aria-hidden="true" />
              <span class="correction-eyebrow">{{ $t('mistakes.correction') }}</span>
              <span class="correction-word" lang="ja">{{ m.correct_answer }}</span>
            </aside>
          </div>

          <div v-if="m.feedback" class="errata-note">
            <div class="note-meta">
              <span class="eyebrow-sm eyebrow-kohaku">{{ $t('mistakes.tutors_note') }}</span>
              <span v-if="m.score != null" class="score-pair">
                <span class="score-label">{{ $t('mistakes.score') }}</span>
                <span class="score-val">{{ m.score }}</span>
              </span>
            </div>
            <p class="note-text">{{ m.feedback }}</p>
          </div>
        </article>
      </div>
    </div>

    <!-- Daily review dialog --------------------------------- -->
    <transition name="review-fade">
      <div
        v-if="showReviewDialog"
        class="review-overlay"
        role="dialog"
        aria-modal="true"
        :aria-label="$t('mistakes.daily_review')"
        @click="showReviewDialog = false"
      >
        <div class="review-scroll" @click.stop>
          <button
            type="button"
            class="review-close"
            :aria-label="$t('mistakes.close')"
            @click="showReviewDialog = false"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
              <path d="M4 4 L12 12 M12 4 L4 12" />
            </svg>
          </button>
          <div class="eyebrow-sm eyebrow-kohaku review-eyebrow">
            {{ $t('mistakes.daily_review') }}
          </div>
          <h2 class="review-heading">{{ $t('mistakes.on_recent_practice') }}</h2>
          <div class="review-prose prose-shiori" v-html="md.render(dailyReview)" />
        </div>
      </div>
    </transition>
  </main>
</template>

<style scoped>
/* Shell + warm tokens --------------------------------------- */
.practice-shell {
  min-height: calc(100vh - 4rem);
  background-image: linear-gradient(
    180deg,
    var(--background) 0%,
    var(--surface-container-low) 100%
  );
  --ink-soft: color-mix(in oklab, var(--foreground) 62%, transparent);
  --ink-faint: color-mix(in oklab, var(--foreground) 38%, transparent);
  --rule: color-mix(in oklab, var(--foreground) 12%, transparent);
  --rule-soft: color-mix(in oklab, var(--foreground) 8%, transparent);
  --paper: var(--surface-container-lowest);
  --paper-warm: var(--surface-container-low);
}
.practice-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 56px 48px 96px;
  width: 100%;
}
@media (max-width: 720px) { .practice-page { padding: 32px 20px 72px; } }

/* Header ----------------------------------------------------- */
.practice-header { padding: 0 0 28px; }
.practice-header-top {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 32px;
  flex-wrap: wrap;
}
.practice-eyebrow {
  font-family: var(--font-sans);
  font-size: 0.68rem;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--secondary);
  font-weight: 500;
  margin-bottom: 10px;
}
.practice-h1 {
  font-family: var(--font-serif);
  font-size: clamp(1.8rem, 2vw + 0.9rem, 2.4rem);
  line-height: 1.2;
  font-weight: 500;
  margin: 0;
  color: var(--foreground);
  letter-spacing: -0.005em;
}
.practice-stats {
  display: flex;
  align-items: baseline;
  gap: 24px;
}
.pstat {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}
.pstat-n {
  font-family: var(--font-serif);
  font-size: 2rem;
  color: var(--primary);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.pstat-label {
  font-family: var(--font-sans);
  font-size: 0.62rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-soft);
}

/* Daily review card ----------------------------------------- */
.review-card {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 24px;
  width: 100%;
  padding: 22px 26px;
  background: var(--paper);
  border: 1px solid var(--rule);
  border-radius: 2px;
  position: relative;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  color: inherit;
  margin-bottom: 40px;
  transition: background 180ms ease, transform 180ms ease;
}
.review-card::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: var(--primary);
}
.review-card:hover:not(:disabled) {
  background: var(--paper-warm);
  transform: translateY(-1px);
}
.review-card:disabled { cursor: wait; opacity: 0.85; }
.review-card.is-ready::before { background: var(--secondary); }
.review-card-body { min-width: 0; }
.review-card-title {
  font-family: var(--font-serif);
  font-size: 1.12rem;
  color: var(--foreground);
  font-weight: 500;
  margin-bottom: 4px;
}
.review-card-sub {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.92rem;
  color: var(--ink-soft);
  line-height: 1.55;
}
.review-card-cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px; height: 36px;
  border-radius: 50%;
  background: var(--foreground);
  color: var(--background);
  transition: transform 220ms ease;
  flex-shrink: 0;
}
.review-card:hover:not(:disabled) .review-card-cta { transform: translateX(3px); }
.review-dots {
  display: inline-flex;
  gap: 3px;
}
.review-dots span {
  width: 4px; height: 4px;
  background: currentColor;
  border-radius: 50%;
  animation: review-dot 1.2s ease-in-out infinite;
}
.review-dots span:nth-child(2) { animation-delay: 0.2s; }
.review-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes review-dot {
  0%, 80%, 100% { opacity: 0.3; }
  40% { opacity: 1; }
}

/* Filter bar ------------------------------------------------- */
.filter-bar {
  display: flex;
  align-items: baseline;
  gap: 40px;
  flex-wrap: wrap;
  padding: 0 0 22px;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--rule-soft);
}
.practice-filter-bar { padding-top: 0; margin-bottom: 28px; }
.filter-group { display: flex; align-items: baseline; gap: 14px; }
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
}
.chip:hover { color: var(--foreground); }
.chip.is-active {
  color: var(--primary);
  border-bottom-color: var(--secondary);
  font-weight: 500;
}
.filter-clear {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin-left: auto;
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px 0;
}
.filter-clear:hover { color: var(--secondary); }

/* Section title row ---------------------------------------- */
.section-title-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 0;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--rule);
}
.practice-section-row { margin-top: 12px; }
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
  margin-left: 14px;
}

/* Spread entries ------------------------------------------- */
.errata-list {
  display: flex;
  flex-direction: column;
}
.errata-entry {
  position: relative;
  padding: 28px 0 30px 42px;
  border-bottom: 1px solid var(--rule-soft);
}
.errata-entry:last-child { border-bottom: none; }
.errata-num {
  position: absolute;
  left: 0;
  top: 34px;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.95rem;
  color: var(--ink-faint);
  font-variant-numeric: tabular-nums;
}
.errata-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
  font-family: var(--font-sans);
  font-size: 0.72rem;
}
.errata-type-en {
  font-size: 0.62rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-soft);
}
.errata-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 40px;
  align-items: start;
}
@media (max-width: 780px) {
  .errata-body { grid-template-columns: 1fr; gap: 20px; }
}
.errata-sentence {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 1.25rem;
  line-height: 1.95;
  letter-spacing: 0.02em;
  color: var(--foreground);
  word-break: auto-phrase;
}
.errata-strike {
  position: relative;
  font-family: var(--font-serif);
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  text-decoration: line-through;
  text-decoration-color: var(--secondary);
  text-decoration-thickness: 2px;
  padding: 0 1px;
}
.errata-correction {
  position: relative;
  padding-left: 22px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 10px;
}
.correction-rule {
  position: absolute;
  left: 0; top: 14px; bottom: 10px;
  width: 2px;
  background: var(--secondary);
}
.correction-eyebrow {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.62rem;
  color: var(--secondary);
  font-weight: 500;
}
.correction-word {
  font-family: var(--font-serif);
  font-size: 1.55rem;
  line-height: 1.3;
  color: var(--primary);
  font-weight: 500;
  font-style: italic;
  letter-spacing: 0.02em;
  word-break: auto-phrase;
}

.errata-note {
  margin-top: 24px;
  padding: 18px 22px;
  background: var(--paper-warm);
  border-radius: 4px;
  max-width: 44em;
}
.note-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
}
.score-pair {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
}
.score-label {
  font-family: var(--font-sans);
  font-size: 0.6rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-soft);
}
.score-val {
  font-family: var(--font-serif);
  font-size: 1.2rem;
  color: var(--primary);
  font-variant-numeric: tabular-nums;
}
.note-text {
  margin: 0;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.98rem;
  line-height: 1.75;
  color: color-mix(in oklab, var(--foreground) 78%, transparent);
  max-width: 42em;
}
@media (max-width: 640px) {
  .errata-sentence { font-size: 1.1rem; }
  .correction-word { font-size: 1.35rem; }
}

/* Empty ---------------------------------------------------- */
.practice-empty {
  padding: 72px 0;
  text-align: center;
}
.practice-empty .empty-text {
  font-family: var(--font-serif);
  font-style: italic;
  color: var(--ink-soft);
  font-size: 1.05rem;
}

/* Eyebrow helpers ------------------------------------------ */
.eyebrow-sm {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.62rem;
  font-weight: 500;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}
.eyebrow-kohaku { color: var(--secondary); }

/* Daily review dialog (glass overlay) ---------------------- */
.review-overlay {
  position: fixed;
  inset: 0;
  z-index: 60;
  background: color-mix(in oklab, var(--foreground) 32%, transparent);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 64px 24px;
  overflow-y: auto;
}
.review-scroll {
  position: relative;
  width: 100%;
  max-width: 620px;
  background: var(--paper);
  border: 1px solid var(--rule);
  border-radius: 6px;
  padding: 44px 52px 40px;
  box-shadow:
    0 32px 64px -24px color-mix(in oklab, var(--foreground) 22%, transparent),
    0 4px 12px -6px color-mix(in oklab, var(--foreground) 10%, transparent);
}
.review-close {
  position: absolute;
  top: 14px; right: 14px;
  width: 32px; height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: var(--ink-soft);
  cursor: pointer;
  border-radius: 4px;
  transition: color 160ms ease, background 160ms ease;
}
.review-close:hover { color: var(--foreground); background: var(--paper-warm); }
.review-close svg { width: 14px; height: 14px; }
.review-eyebrow { margin-bottom: 10px; }
.review-heading {
  font-family: var(--font-serif);
  font-size: 1.75rem;
  line-height: 1.3;
  margin: 0 0 20px;
  font-weight: 500;
  color: var(--foreground);
}
.review-prose {
  font-family: var(--font-serif);
  font-size: 1rem;
  line-height: 1.85;
}

@media (max-width: 600px) {
  .review-scroll { padding: 32px 24px 28px; }
  .review-heading { font-size: 1.4rem; }
}

.review-fade-enter-active,
.review-fade-leave-active {
  transition: opacity 220ms ease;
}
.review-fade-enter-active .review-scroll,
.review-fade-leave-active .review-scroll {
  transition: opacity 280ms cubic-bezier(0.16, 1, 0.3, 1),
              transform 280ms cubic-bezier(0.16, 1, 0.3, 1);
}
.review-fade-enter-from,
.review-fade-leave-to { opacity: 0; }
.review-fade-enter-from .review-scroll,
.review-fade-leave-to .review-scroll {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}
</style>
