<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import HankoSeal from '@/components/exercise/HankoSeal.vue';
import ChoiceFootnote from '@/components/exercise/ChoiceFootnote.vue';
import {
  EXAM_SECTIONS,
  loadExamBank,
  questionOrigin,
  segmentPrompt,
  shuffle,
  type ExamQuestion,
  type ExamSection,
} from '@/lib/examBank';

const { t } = useI18n();

interface MistakeRecord {
  id: string;
  prompt: string;
  userAnswer: string;
  correctAnswer: string;
  grammar: string;
  explanation: string;
  source: string;
}

// --- data -----------------------------------------------------------------
const all = ref<ExamQuestion[]>([]);
const isLoading = ref(true);
const loadError = ref('');

const section = ref<ExamSection | 'all'>('all');

// Whether to mix in the AI-generated extra-practice set. Off = verified
// textbook questions only (the real exam scope). Persisted across visits.
const INCLUDE_GEN_KEY = 'shiori.exam.include_generated';
function readIncludeGen(): boolean {
  try {
    return localStorage.getItem(INCLUDE_GEN_KEY) === '1';
  } catch {
    return false;
  }
}
const includeGenerated = ref<boolean>(readIncludeGen());

// --- session state --------------------------------------------------------
const queue = ref<number[]>([]); // indices into `pool`
const cursor = ref(0);
const score = ref({ correct: 0, total: 0 });
// One selected option index (or null) per blank of the current question.
const selections = ref<(number | null)[]>([]);
const feedback = ref<'idle' | 'correct' | 'incorrect'>('idle');
const mistakes = ref<MistakeRecord[]>([]);
const showMistakes = ref(false);

// Pool respects both filters: the generated toggle, then section.
const bySource = computed<ExamQuestion[]>(() =>
  includeGenerated.value ? all.value : all.value.filter(q => questionOrigin(q) === 'textbook'),
);
const pool = computed<ExamQuestion[]>(() =>
  section.value === 'all' ? bySource.value : bySource.value.filter(q => q.section === section.value),
);

const generatedCount = computed(() => all.value.filter(q => questionOrigin(q) === 'generated').length);

// Section chips: All + each present section (counted within the active source).
const sectionChips = computed(() => {
  const base = bySource.value;
  const chips: { value: ExamSection | 'all'; label: string; count: number }[] = [
    { value: 'all', label: t('exam.section_all'), count: base.length },
  ];
  for (const s of EXAM_SECTIONS) {
    const items = base.filter(q => q.section === s);
    if (items.length === 0) continue;
    chips.push({ value: s, label: `${s} · ${items[0].section_label}`, count: items.length });
  }
  return chips;
});

const total = computed(() => queue.value.length);
const currentIndex = computed(() => queue.value[cursor.value] ?? -1);
const current = computed<ExamQuestion | null>(() => {
  const i = currentIndex.value;
  return i >= 0 ? pool.value[i] ?? null : null;
});
const sessionDone = computed(() => total.value > 0 && cursor.value >= total.value);

const segments = computed(() => (current.value ? segmentPrompt(current.value) : []));
const allSelected = computed(
  () => selections.value.length > 0 && selections.value.every(s => s !== null),
);

const accuracy = computed(() =>
  score.value.total === 0 ? 0 : Math.round((score.value.correct / score.value.total) * 100),
);

const currentIsGenerated = computed(
  () => !!current.value && questionOrigin(current.value) === 'generated',
);

// Provenance line shown after answering — drops the page for generated items
// (they have no textbook page).
const sourceMeta = computed(() => {
  const q = current.value;
  if (!q) return '';
  const parts = [q.section_label, q.block, q.source];
  if (q.page) parts.push(`p.${q.page}`);
  return parts.join(' · ');
});

// --- loading --------------------------------------------------------------
onMounted(async () => {
  window.addEventListener('keydown', onWindowKeydown);
  try {
    all.value = await loadExamBank();
    startSession();
  } catch (e) {
    loadError.value = t('exam.load_error');
    console.error('exam bank load error', e);
  } finally {
    isLoading.value = false;
  }
});

onUnmounted(() => window.removeEventListener('keydown', onWindowKeydown));

watch(section, () => startSession());
watch(includeGenerated, (v) => {
  try {
    localStorage.setItem(INCLUDE_GEN_KEY, v ? '1' : '0');
  } catch {
    /* storage unavailable — non-fatal */
  }
  startSession();
});

// --- session control ------------------------------------------------------
function startSession() {
  cursor.value = 0;
  score.value = { correct: 0, total: 0 };
  mistakes.value = [];
  showMistakes.value = false;
  queue.value = shuffle(pool.value.map((_, i) => i));
  prepareCurrent();
}

function prepareCurrent() {
  feedback.value = 'idle';
  const q = current.value;
  selections.value = q ? q.blanks.map(() => null) : [];
}

function selectOption(blankIdx: number, optIdx: number) {
  if (feedback.value !== 'idle') return;
  // Replace the array so Vue tracks the change.
  const next = selections.value.slice();
  next[blankIdx] = optIdx;
  selections.value = next;
}

function check() {
  const q = current.value;
  if (!q || feedback.value !== 'idle' || !allSelected.value) return;
  const ok = q.blanks.every((b, i) => selections.value[i] === b.correct);
  feedback.value = ok ? 'correct' : 'incorrect';
  score.value.total++;
  if (ok) {
    score.value.correct++;
  } else {
    mistakes.value.push({
      id: q.id,
      prompt: q.prompt,
      userAnswer: q.blanks
        .map((b, i) => {
          const sel = selections.value[i];
          const label = q.kind === 'multi' ? b.label : '';
          return `${label}${sel != null ? b.options[sel] : '—'}`;
        })
        .join(' '),
      correctAnswer: q.answer_display,
      grammar: q.grammar_point,
      explanation: q.explanation_zh,
      source: `${q.source} · p.${q.page}`,
    });
  }
}

function next() {
  if (feedback.value === 'idle') return;
  cursor.value++;
  prepareCurrent();
}

// --- per-blank display after submission -----------------------------------
function blankFill(blankIndex: number): string {
  const q = current.value;
  if (!q) return '';
  const b = q.blanks[blankIndex];
  return b ? b.options[b.correct] : '';
}
function blankIsCorrect(blankIndex: number): boolean {
  const q = current.value;
  if (!q) return false;
  return selections.value[blankIndex] === q.blanks[blankIndex]?.correct;
}

// Post-submit result for an option: marks the correct row and the row the
// user wrongly picked. Null while answering (the selection styling is its own
// signal then).
function optionResult(blankIdx: number, optIdx: number): 'correct' | 'incorrect' | null {
  const q = current.value;
  if (!q || feedback.value === 'idle') return null;
  if (optIdx === q.blanks[blankIdx].correct) return 'correct';
  if (selections.value[blankIdx] === optIdx) return 'incorrect';
  return null;
}

// --- keyboard -------------------------------------------------------------
function onWindowKeydown(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement | null)?.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA') return;

  if (e.key === 'Enter') {
    if (sessionDone.value) {
      e.preventDefault();
      startSession();
    } else if (feedback.value === 'idle') {
      if (allSelected.value) {
        e.preventDefault();
        check();
      }
    } else {
      e.preventDefault();
      next();
    }
    return;
  }

  // Digit keys pick an option for the next unfilled blank (single/multi/classify).
  if (feedback.value === 'idle' && /^[1-9]$/.test(e.key)) {
    const q = current.value;
    if (!q) return;
    const targetBlank = selections.value.findIndex(s => s === null);
    const blankIdx = targetBlank === -1 ? 0 : targetBlank;
    const optIdx = Number(e.key) - 1;
    if (optIdx < q.blanks[blankIdx].options.length) {
      e.preventDefault();
      selectOption(blankIdx, optIdx);
    }
  }
}
</script>

<template>
  <main class="exam-shell ei-shell-bg text-foreground">
    <div class="exam-page">
      <!-- Header ---------------------------------------------- -->
      <header class="exam-header">
        <div>
          <div class="eyebrow eyebrow-kohaku">{{ $t('exam.eyebrow') }}</div>
          <h1 class="exam-h1">{{ $t('exam.heading') }}</h1>
          <p class="exam-sub">{{ $t('exam.subtitle') }}</p>
        </div>
        <div v-if="!isLoading && total > 0" class="exam-stats">
          <div class="pstat">
            <span class="pstat-n">{{ score.correct }}/{{ score.total }}</span>
            <span class="pstat-label">{{ $t('exam.score_label') }}</span>
          </div>
          <div class="pstat">
            <span class="pstat-n">{{ accuracy }}%</span>
            <span class="pstat-label">{{ $t('exam.accuracy_label') }}</span>
          </div>
        </div>
      </header>

      <!-- Section filter -------------------------------------- -->
      <div class="filter-bar exam-filter-bar">
        <div class="filter-group">
          <span class="filter-label">{{ $t('exam.section_label') }}</span>
          <div class="chip-row">
            <button
              v-for="c in sectionChips"
              :key="c.value"
              type="button"
              class="chip"
              :class="{ 'is-active': section === c.value }"
              @click="section = c.value"
            >
              {{ c.label }}<span class="chip-count">{{ c.count }}</span>
            </button>
          </div>
        </div>
        <div class="filter-group exam-toggle-group">
          <button
            type="button"
            role="switch"
            class="gen-switch"
            :class="{ 'is-on': includeGenerated }"
            :aria-checked="includeGenerated"
            @click="includeGenerated = !includeGenerated"
          >
            <span class="gen-switch-track" aria-hidden="true"><span class="gen-switch-thumb" /></span>
            <span class="gen-switch-text">
              {{ $t('exam.include_generated') }}
              <span class="gen-switch-count">+{{ generatedCount }}</span>
            </span>
          </button>
        </div>
      </div>

      <!-- Loading / error ------------------------------------- -->
      <div v-if="isLoading" class="empty-state">{{ $t('common.loading') }}</div>
      <div v-else-if="loadError" class="empty-state">{{ loadError }}</div>

      <!-- Session done ---------------------------------------- -->
      <section v-else-if="sessionDone" class="exam-done">
        <div class="exam-done-eyebrow eyebrow eyebrow-indigo">{{ $t('exam.session_complete') }}</div>
        <h2 class="exam-done-h">
          {{ $t('exam.session_score', { correct: score.correct, total: score.total }) }}
        </h2>
        <p class="exam-done-sub">{{ $t('exam.session_accuracy', { pct: accuracy }) }}</p>
        <div class="exam-done-actions">
          <button class="exam-btn exam-btn-primary" type="button" @click="startSession">
            {{ $t('exam.start_again') }}
          </button>
          <button
            v-if="mistakes.length > 0"
            class="exam-btn"
            type="button"
            @click="showMistakes = !showMistakes"
          >
            {{ showMistakes ? $t('exam.hide_mistakes') : $t('exam.review_mistakes', { n: mistakes.length }) }}
          </button>
        </div>
      </section>

      <!-- Active question ------------------------------------- -->
      <section v-else-if="current" class="exam-card">
        <div class="exam-card-meta">
          <!-- The grammar category (section_label · block) is withheld while
               answering — it would hint the answer — and revealed in the
               feedback panel after submitting. -->
          <span class="exam-card-meta-left">
            <span class="eyebrow eyebrow-sm">{{ $t('exam.question_eyebrow') }}</span>
            <span v-if="currentIsGenerated" class="exam-gen-badge">{{ $t('exam.generated_badge') }}</span>
          </span>
          <span class="exam-progress">{{ $t('exam.progress', { i: cursor + 1, n: total }) }}</span>
        </div>

        <!-- Prompt with inline blanks -->
        <p class="exam-prompt" lang="ja">
          <template v-for="(seg, i) in segments" :key="i">
            <span v-if="seg.kind === 'text'">{{ seg.text }}</span>
            <span
              v-else
              class="exam-blank"
              :class="{
                'is-correct': feedback === 'correct' || (feedback === 'incorrect' && blankIsCorrect(seg.blankIndex ?? 0)),
                'is-incorrect': feedback === 'incorrect' && !blankIsCorrect(seg.blankIndex ?? 0),
              }"
            >
              <template v-if="feedback === 'idle'">
                <span class="exam-blank-cue">{{ seg.text || '　' }}</span>
              </template>
              <template v-else>
                <span class="exam-blank-fill" lang="ja">{{ blankFill(seg.blankIndex ?? 0) }}</span>
              </template>
            </span>
          </template>
        </p>

        <!-- Classification phrasing (no inline blank) -->
        <p v-if="current.kind === 'classify'" class="exam-classify-q">
          {{ $t('exam.classify_prompt') }}
        </p>

        <!-- Option groups (one per blank) -->
        <div class="exam-groups">
          <div
            v-for="(blank, bi) in current.blanks"
            :key="bi"
            class="exam-group"
          >
            <span v-if="blank.label" class="exam-group-label">{{ blank.label }}</span>
            <ol class="exam-footnotes">
              <ChoiceFootnote
                v-for="(opt, oi) in blank.options"
                :key="oi"
                :choice="opt"
                :index="oi"
                :selected="feedback === 'idle' && selections[bi] === oi"
                :selected-label="$t('exam.selected')"
                :result="optionResult(bi, oi)"
                :result-label="$t('exam.answer_tag')"
                :disabled="feedback !== 'idle'"
                @select="selectOption(bi, oi)"
              />
            </ol>
          </div>
        </div>

        <!-- Action row -->
        <div class="exam-action-row">
          <button
            v-if="feedback === 'idle'"
            type="button"
            class="exam-btn exam-btn-primary"
            :disabled="!allSelected"
            @click="check"
          >
            {{ $t('exam.check') }}
          </button>
          <button
            v-else
            type="button"
            class="exam-btn exam-btn-primary"
            @click="next"
          >
            {{ cursor + 1 >= total ? $t('exam.finish') : $t('exam.next') }}
          </button>
          <span class="exam-kbd-hint">
            <kbd>1–{{ Math.max(...current.blanks.map(b => b.options.length)) }}</kbd> {{ $t('exam.kbd_pick') }}
            <span class="exam-kbd-sep">·</span>
            <kbd>Enter</kbd> {{ feedback === 'idle' ? $t('exam.check') : $t('exam.next') }}
          </span>
        </div>

        <!-- Feedback -->
        <div v-if="feedback !== 'idle'" class="exam-feedback" :class="`is-${feedback}`">
          <div class="exam-feedback-head">
            <span class="eyebrow eyebrow-sm" :class="feedback === 'correct' ? 'eyebrow-indigo' : 'eyebrow-kohaku'">
              {{ feedback === 'correct' ? $t('exam.correct') : $t('exam.incorrect') }}
            </span>
            <span class="exam-feedback-answer" lang="ja">{{ current.answer_display }}</span>
            <HankoSeal
              v-if="feedback === 'correct'"
              label="正解"
              :aria-label="$t('exam.correct')"
              :rotation="-5"
              :size="60"
              class="exam-hanko"
            />
          </div>

          <div class="exam-meta">
            <div class="exam-meta-row">
              <span class="eyebrow eyebrow-sm">{{ $t('exam.grammar_label') }}</span>
              <span class="exam-meta-grammar" lang="ja">{{ current.grammar_point }}</span>
            </div>
            <p class="exam-explanation" lang="zh-Hant">{{ current.explanation_zh }}</p>
            <div class="exam-source">{{ sourceMeta }}</div>
          </div>
        </div>
      </section>

      <!-- Mistakes drawer ------------------------------------- -->
      <section v-if="!isLoading && mistakes.length > 0" class="exam-mistakes">
        <div class="section-title-row exam-section-row">
          <h3 class="section-title">{{ $t('exam.mistakes_title') }}</h3>
          <button type="button" class="filter-clear" @click="showMistakes = !showMistakes">
            {{ showMistakes ? $t('exam.hide') : $t('exam.show', { n: mistakes.length }) }}
          </button>
        </div>
        <ol v-if="showMistakes" class="exam-mistake-list">
          <li v-for="(m, i) in mistakes" :key="`${m.id}-${i}`" class="exam-mistake">
            <span class="exam-mistake-num">{{ String(i + 1).padStart(2, '0') }}</span>
            <div class="exam-mistake-body">
              <p class="exam-mistake-prompt" lang="ja">{{ m.prompt }}</p>
              <p class="exam-mistake-line">
                <span class="eyebrow eyebrow-sm">{{ $t('exam.your_answer') }}</span>
                <span class="exam-strike" lang="ja">{{ m.userAnswer }}</span>
              </p>
              <p class="exam-mistake-line">
                <span class="eyebrow eyebrow-sm eyebrow-kohaku">{{ $t('exam.correction') }}</span>
                <span class="exam-correct" lang="ja">{{ m.correctAnswer }}</span>
              </p>
              <p class="exam-mistake-expl" lang="zh-Hant">{{ m.explanation }}</p>
              <p class="exam-mistake-foot" lang="ja">{{ m.grammar }} · {{ m.source }}</p>
            </div>
          </li>
        </ol>
      </section>
    </div>
  </main>
</template>

<style scoped>
.exam-shell {
  min-height: calc(100vh - var(--app-chrome-h));
  padding: 40px 32px 80px;
}
.exam-page {
  max-width: 880px;
  margin: 0 auto;
}

/* Header ------------------------------------------------------ */
.exam-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}
.exam-h1 {
  font-family: var(--font-serif);
  font-size: 2.2rem;
  margin: 6px 0 4px;
  color: var(--foreground);
  font-weight: 500;
}
.exam-sub {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.95rem;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  margin: 0;
  max-width: 560px;
}
.exam-stats { display: flex; gap: 32px; }
.pstat { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
.pstat-n { font-family: var(--font-serif); font-size: 1.5rem; color: var(--foreground); }
.pstat-label {
  font-family: var(--font-sans);
  font-size: 0.62rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}

/* Filter bar -------------------------------------------------- */
.exam-filter-bar { padding: 10px 0 18px; margin-bottom: 28px; }
.chip-count {
  font-size: 0.62rem;
  margin-left: 6px;
  color: color-mix(in oklab, var(--foreground) 40%, transparent);
  font-variant-numeric: tabular-nums;
}

/* "Include AI practice" toggle ------------------------------- */
.exam-toggle-group { align-self: center; }
.gen-switch {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  background: none;
  border: none;
  padding: 4px 0;
  cursor: pointer;
  font-family: var(--font-sans);
}
.gen-switch-track {
  position: relative;
  display: inline-block;
  width: 34px;
  height: 18px;
  border-radius: 999px;
  background: color-mix(in oklab, var(--foreground) 18%, transparent);
  transition: background 180ms ease;
  flex-shrink: 0;
}
.gen-switch-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--surface-container-lowest, #fff);
  box-shadow: 0 1px 2px color-mix(in oklab, var(--foreground) 25%, transparent);
  transition: transform 180ms ease;
}
.gen-switch.is-on .gen-switch-track { background: var(--secondary); }
.gen-switch.is-on .gen-switch-thumb { transform: translateX(16px); }
.gen-switch:focus-visible { outline: 2px solid var(--ring); outline-offset: 3px; border-radius: 4px; }
.gen-switch-text {
  font-size: 0.78rem;
  letter-spacing: 0.01em;
  color: color-mix(in oklab, var(--foreground) 65%, transparent);
  transition: color 180ms ease;
}
.gen-switch.is-on .gen-switch-text { color: var(--foreground); }
.gen-switch-count {
  font-size: 0.62rem;
  margin-left: 4px;
  color: color-mix(in oklab, var(--foreground) 42%, transparent);
  font-variant-numeric: tabular-nums;
}

/* Card -------------------------------------------------------- */
.exam-card {
  background: var(--surface-container-lowest, var(--background));
  border: 1px solid color-mix(in oklab, var(--foreground) 8%, transparent);
  border-radius: 4px;
  padding: 32px;
}
.exam-card-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}
.exam-card-meta-left {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}
.exam-gen-badge {
  font-family: var(--font-sans);
  font-size: 0.6rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--secondary);
  padding: 2px 8px;
  border: 1px solid color-mix(in oklab, var(--secondary) 45%, transparent);
  border-radius: 999px;
  white-space: nowrap;
}
.exam-progress {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
  white-space: nowrap;
}

/* Prompt ------------------------------------------------------ */
.exam-prompt {
  font-family: var(--font-serif);
  font-size: 1.5rem;
  line-height: 1.85;
  color: var(--foreground);
  margin: 8px 0 6px;
}
.exam-blank {
  display: inline-block;
  min-width: 4ch;
  padding: 0 10px;
  margin: 0 2px;
  text-align: center;
  border-bottom: 2px solid color-mix(in oklab, var(--secondary) 70%, transparent);
  background: color-mix(in oklab, var(--secondary) 8%, transparent);
  border-radius: 2px;
}
.exam-blank.is-correct {
  border-bottom-color: var(--primary);
  background: color-mix(in oklab, var(--primary) 10%, transparent);
}
.exam-blank.is-incorrect {
  border-bottom-color: var(--destructive);
  background: color-mix(in oklab, var(--destructive) 10%, transparent);
}
.exam-blank-cue {
  font-style: normal;
  font-size: 0.92em;
  color: color-mix(in oklab, var(--secondary) 90%, var(--foreground));
}
.exam-blank-fill { font-weight: 500; color: var(--foreground); }

.exam-classify-q {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 1.02rem;
  color: color-mix(in oklab, var(--foreground) 70%, transparent);
  margin: 6px 0 0;
}

/* Option groups — reuses ChoiceFootnote (the exercise-view choice row) so the
   selection + result highlight matches that view exactly. */
.exam-groups {
  margin-top: 26px;
  display: flex;
  flex-direction: column;
  gap: 26px;
}
.exam-group {
  position: relative;
  padding-left: 22px;   /* room for ChoiceFootnote's proofreader margin dot */
}
.exam-group-label {
  display: inline-block;
  font-family: var(--font-serif);
  font-size: 1.15rem;
  color: var(--secondary);
  margin-bottom: 6px;
}
.exam-footnotes {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* Action row -------------------------------------------------- */
.exam-action-row {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
  margin-top: 28px;
}
.exam-kbd-hint {
  font-family: var(--font-sans);
  font-size: 0.72rem;
  color: color-mix(in oklab, var(--foreground) 45%, transparent);
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
.exam-kbd-hint kbd {
  font-family: var(--font-sans);
  font-size: 0.68rem;
  padding: 1px 6px;
  border: 1px solid color-mix(in oklab, var(--foreground) 22%, transparent);
  border-radius: 4px;
  background: var(--surface-container-low);
}
.exam-kbd-sep { color: color-mix(in oklab, var(--foreground) 25%, transparent); }

.exam-btn {
  font-family: var(--font-sans);
  font-size: 0.74rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  padding: 10px 22px;
  background: transparent;
  border: 1px solid color-mix(in oklab, var(--foreground) 25%, transparent);
  color: var(--foreground);
  cursor: pointer;
  border-radius: 2px;
  transition: background 160ms ease, color 160ms ease, border-color 160ms ease;
}
.exam-btn:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); }
.exam-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.exam-btn-primary {
  background: var(--primary);
  border-color: var(--primary);
  color: var(--primary-foreground, #fff);
}
.exam-btn-primary:hover:not(:disabled) {
  background: color-mix(in oklab, var(--primary) 88%, black);
  color: var(--primary-foreground, #fff);
  border-color: color-mix(in oklab, var(--primary) 88%, black);
}

/* Feedback ---------------------------------------------------- */
.exam-feedback {
  margin-top: 26px;
  padding: 18px 20px;
  border-left: 3px solid color-mix(in oklab, var(--primary) 70%, transparent);
  background: color-mix(in oklab, var(--primary) 4%, transparent);
}
.exam-feedback.is-incorrect {
  border-left-color: var(--destructive);
  background: color-mix(in oklab, var(--destructive) 5%, transparent);
}
.exam-feedback-head {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.exam-feedback-answer {
  font-family: var(--font-serif);
  font-size: 1.25rem;
  color: var(--foreground);
}
.exam-hanko { margin-left: auto; }

.exam-meta { margin-top: 14px; padding-top: 14px; border-top: 1px solid color-mix(in oklab, var(--foreground) 8%, transparent); }
.exam-meta-row { display: flex; align-items: baseline; gap: 12px; margin-bottom: 8px; }
.exam-meta-grammar { font-family: var(--font-serif); font-size: 0.98rem; color: var(--foreground); }
.exam-explanation {
  font-family: var(--font-serif);
  font-size: 1rem;
  line-height: 1.7;
  color: color-mix(in oklab, var(--foreground) 84%, transparent);
  margin: 0 0 10px;
}
.exam-source {
  font-family: var(--font-sans);
  font-size: 0.66rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 45%, transparent);
}

/* Done banner ------------------------------------------------ */
.exam-done {
  text-align: center;
  padding: 64px 24px;
  border: 1px solid color-mix(in oklab, var(--foreground) 8%, transparent);
  border-radius: 4px;
  background: var(--surface-container-lowest, var(--background));
}
.exam-done-eyebrow { margin-bottom: 12px; }
.exam-done-h { font-family: var(--font-serif); font-size: 1.8rem; margin: 0 0 6px; color: var(--foreground); font-weight: 500; }
.exam-done-sub { font-family: var(--font-serif); font-style: italic; color: color-mix(in oklab, var(--foreground) 60%, transparent); margin: 0 0 22px; }
.exam-done-actions { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }

/* Mistakes ---------------------------------------------------- */
.exam-mistakes { margin-top: 56px; }
.exam-section-row { margin-bottom: 18px; }
.exam-mistake-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 18px; }
.exam-mistake {
  display: grid;
  grid-template-columns: 36px 1fr;
  gap: 14px;
  padding: 16px 18px;
  border: 1px solid color-mix(in oklab, var(--foreground) 7%, transparent);
  border-radius: 3px;
  background: var(--background);
}
.exam-mistake-num { font-family: var(--font-serif); font-style: italic; color: color-mix(in oklab, var(--foreground) 45%, transparent); }
.exam-mistake-body { display: flex; flex-direction: column; gap: 6px; }
.exam-mistake-prompt { font-family: var(--font-serif); font-size: 1.02rem; margin: 0 0 4px; color: var(--foreground); }
.exam-mistake-line { display: flex; gap: 10px; align-items: baseline; margin: 0; }
.exam-strike { font-family: var(--font-serif); text-decoration: line-through; color: color-mix(in oklab, var(--foreground) 60%, transparent); }
.exam-correct { font-family: var(--font-serif); color: var(--foreground); font-weight: 500; }
.exam-mistake-expl {
  font-family: var(--font-serif);
  font-size: 0.92rem;
  line-height: 1.6;
  color: color-mix(in oklab, var(--foreground) 70%, transparent);
  margin: 4px 0 0;
}
.exam-mistake-foot {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  color: color-mix(in oklab, var(--foreground) 48%, transparent);
  margin: 2px 0 0;
}

@media (max-width: 560px) {
  .exam-shell { padding: 28px 18px 96px; }
  .exam-card { padding: 22px 18px; }
  .exam-prompt { font-size: 1.3rem; }
  .exam-group { padding-left: 18px; }
  .exam-footnotes :deep(.choice) { font-size: 1.3rem; }
}
</style>
