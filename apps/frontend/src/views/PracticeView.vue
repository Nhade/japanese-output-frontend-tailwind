<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import {
  LESSON_IDS,
  VOCAB_DISABLED_LESSONS,
  buildMeaningMCQ,
  fillBlankAnswerVariants,
  isFillBlankCorrect,
  isVocabSectionDrilled,
  kanaifyAnswer,
  loadFillBlanks,
  loadGrammarPoints,
  loadVocab,
  normalizeAnswer,
  shuffle,
  splitUserAnswers,
  type FillBlankItem,
  type GrammarPoint,
  type LessonId,
  type VocabChoiceQuestion,
  type VocabItem,
} from '@/lib/practice';

const { t } = useI18n();

type Mode = 'fill_blank' | 'vocab_meaning' | 'vocab_reading';

interface MistakeRecord {
  id: string;
  mode: Mode;
  prompt: string;
  userAnswer: string;
  correctAnswer: string;
  hint?: string;
  fullSentence?: string;
}

const lesson = ref<LessonId>('L35');
const mode = ref<Mode>('fill_blank');

const fillBlanks = ref<FillBlankItem[]>([]);
const vocab = ref<VocabItem[]>([]);
// Pool of vocab from every shipped lesson — used for kanaification in
// fill-blank checks, since each lesson's CSV only carries newly introduced
// words (e.g. 短い is taught earlier than L35 but appears as a cue here).
const allVocab = ref<VocabItem[]>([]);
const grammarPoints = ref<GrammarPoint[]>([]);

const isLoading = ref(false);
const loadError = ref('');

// --- session state --------------------------------------------------------
const queue = ref<number[]>([]);  // indices into the active dataset
const cursor = ref(0);
const score = ref({ correct: 0, total: 0 });
const userInput = ref('');
const selectedChoice = ref<number | null>(null);
const feedback = ref<'idle' | 'correct' | 'incorrect'>('idle');
const mistakes = ref<MistakeRecord[]>([]);
const showMistakes = ref(false);
// vocab-reading: hide kanji until user clicks "Show kanji" or submits.
const revealKanji = ref(false);

// MCQ question for vocab_meaning is regenerated as the cursor advances.
const mcq = ref<VocabChoiceQuestion | null>(null);

const lessonOptions = computed(() => LESSON_IDS.map(id => ({ id, label: id })));
const vocabAllowed = computed(() => !VOCAB_DISABLED_LESSONS.has(lesson.value));

// Mode list adapts when the active lesson disables vocab.
const modeOptions = computed<{ id: Mode; key: string; disabled: boolean }[]>(() => [
  { id: 'fill_blank', key: 'mode_fill_blank', disabled: false },
  { id: 'vocab_meaning', key: 'mode_vocab_meaning', disabled: !vocabAllowed.value },
  { id: 'vocab_reading', key: 'mode_vocab_reading', disabled: !vocabAllowed.value },
]);

const grammarById = computed<Record<string, GrammarPoint>>(() => {
  const out: Record<string, GrammarPoint> = {};
  for (const g of grammarPoints.value) out[g.grammar_point_id] = g;
  return out;
});

const total = computed(() => queue.value.length);
const currentIndex = computed(() => queue.value[cursor.value] ?? -1);
const sessionDone = computed(() => total.value > 0 && cursor.value >= total.value);

const currentFillBlank = computed<FillBlankItem | null>(() => {
  if (mode.value !== 'fill_blank') return null;
  const i = currentIndex.value;
  return i >= 0 ? fillBlanks.value[i] : null;
});

const currentVocab = computed<VocabItem | null>(() => {
  if (mode.value === 'fill_blank') return null;
  const i = currentIndex.value;
  return i >= 0 ? vocab.value[i] : null;
});

// --- loading --------------------------------------------------------------
async function loadLesson(id: LessonId) {
  isLoading.value = true;
  loadError.value = '';
  try {
    // Always load vocab — even when the lesson disables vocab quizzes, the
    // fill-blank checker uses it to accept kana-only readings (e.g.
    // しょうたいされた as a stand-in for 招待された).
    const [fb, vc, gp] = await Promise.all([
      loadFillBlanks(id),
      loadVocab(id),
      loadGrammarPoints(id),
    ]);
    fillBlanks.value = fb;
    vocab.value = vc;
    grammarPoints.value = gp;
    startSession();
  } catch (e) {
    loadError.value = t('practice.load_error');
    console.error('practice load error', e);
  } finally {
    isLoading.value = false;
  }
}

// --- session control ------------------------------------------------------
function startSession() {
  cursor.value = 0;
  score.value = { correct: 0, total: 0 };
  feedback.value = 'idle';
  userInput.value = '';
  selectedChoice.value = null;
  mistakes.value = [];
  showMistakes.value = false;

  if (mode.value === 'fill_blank') {
    queue.value = shuffle(fillBlanks.value.map((_, i) => i));
  } else {
    // Filter out補充 rows missing a column, plus vocab from non-drilled sections
    // (読み物語彙 / 会話語彙 — these are reference glossaries, not active vocab).
    const usable = vocab.value
      .map((v, i) => ({ v, i }))
      .filter(({ v }) =>
        v.japanese && v.kana && v.chinese_meaning && isVocabSectionDrilled(v.source_section),
      )
      .map(({ i }) => i);
    queue.value = shuffle(usable);
  }
  prepareCurrent();
}

function prepareCurrent() {
  if (sessionDone.value) {
    mcq.value = null;
    return;
  }
  if (mode.value === 'vocab_meaning' && currentVocab.value) {
    mcq.value = buildMeaningMCQ(currentVocab.value, vocab.value);
  } else {
    mcq.value = null;
  }
  feedback.value = 'idle';
  userInput.value = '';
  selectedChoice.value = null;
  revealKanji.value = false;
}

function next() {
  if (feedback.value === 'idle') return;
  cursor.value++;
  prepareCurrent();
}

function recordMistake(rec: Omit<MistakeRecord, 'id'>) {
  mistakes.value.push({ ...rec, id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}` });
}

// --- check answer ---------------------------------------------------------
function checkFillBlank() {
  const item = currentFillBlank.value;
  if (!item || feedback.value !== 'idle') return;
  const ok = isFillBlankCorrect(userInput.value, item, allVocab.value);
  feedback.value = ok ? 'correct' : 'incorrect';
  score.value.total++;
  if (ok) score.value.correct++;
  else {
    recordMistake({
      mode: 'fill_blank',
      prompt: item.prompt,
      userAnswer: userInput.value || '—',
      correctAnswer: item.answer,
      hint: grammarById.value[item.grammar_point_id]?.grammar_point ?? item.target_form,
      fullSentence: item.full_answer_sentence,
    });
  }
}

function checkMeaning(idx: number) {
  if (feedback.value !== 'idle' || !mcq.value) return;
  selectedChoice.value = idx;
  const ok = idx === mcq.value.correctIndex;
  feedback.value = ok ? 'correct' : 'incorrect';
  score.value.total++;
  if (ok) score.value.correct++;
  else {
    const v = mcq.value.item;
    recordMistake({
      mode: 'vocab_meaning',
      prompt: `${v.japanese}（${v.kana}）`,
      userAnswer: mcq.value.choices[idx],
      correctAnswer: v.chinese_meaning,
      hint: v.word_type,
    });
  }
}

function checkReading() {
  const item = currentVocab.value;
  if (!item || feedback.value !== 'idle') return;
  const ok = normalizeAnswer(userInput.value) === normalizeAnswer(item.kana);
  feedback.value = ok ? 'correct' : 'incorrect';
  score.value.total++;
  if (ok) score.value.correct++;
  else {
    recordMistake({
      mode: 'vocab_reading',
      prompt: `${item.japanese} — ${item.chinese_meaning}`,
      userAnswer: userInput.value || '—',
      correctAnswer: item.kana,
      hint: item.word_type,
    });
  }
}

function onSubmit() {
  if (mode.value === 'fill_blank') checkFillBlank();
  else if (mode.value === 'vocab_reading') checkReading();
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    e.preventDefault();
    if (feedback.value === 'idle') onSubmit();
    else next();
  }
}

// Window-level Enter handler so the user can advance after submission even
// when the input is disabled (and after MCQ clicks where focus may be on a
// disabled choice button). The input's own keydown listener fires first and
// calls preventDefault — we honour that to avoid double-firing.
function onWindowKeydown(e: KeyboardEvent) {
  if (e.key !== 'Enter') return;
  if (e.defaultPrevented) return;
  // Let buttons (Next, Start again, etc.) handle their own Enter activation,
  // otherwise pressing Enter on a focused Next button would advance twice.
  const tag = (e.target as HTMLElement | null)?.tagName;
  if (tag === 'BUTTON' || tag === 'A') return;
  if (sessionDone.value) {
    e.preventDefault();
    startSession();
    return;
  }
  if (feedback.value !== 'idle') {
    e.preventDefault();
    next();
  }
}

// --- pretty-printing ------------------------------------------------------
// Fill-blank prompts contain `（cue→＿＿）` markers. Render the marker as a
// styled blank slot inline with the surrounding Japanese.
// A prompt segment is either flowing text or one of N blanks; `blankIndex`
// is the running 0-based position among blanks, used to pull the right user
// token / correct variant when rendering feedback.
interface PromptSegment { kind: 'text' | 'blank'; text: string; blankIndex?: number }

const promptSegments = computed<PromptSegment[]>(() => {
  const item = currentFillBlank.value;
  if (!item) return [];
  const re = /（([^）]*?→[^）]*?)）/g;
  const out: PromptSegment[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let blankIndex = 0;
  while ((m = re.exec(item.prompt)) !== null) {
    if (m.index > last) out.push({ kind: 'text', text: item.prompt.slice(last, m.index) });
    // The CSV uses `cue→＿＿／＿＿` for two-blank prompts. Split on `／` so we
    // get one rendered blank per actual blank slot, not one wide cue.
    const inside = m[1];
    const arrowSplit = inside.split('→');
    const cue = arrowSplit[0];
    const blanks = (arrowSplit[1] ?? '＿＿').split('／');
    blanks.forEach((_, i) => {
      out.push({ kind: 'blank', text: i === 0 ? `${cue}→＿＿` : '＿＿', blankIndex });
      blankIndex++;
    });
    last = m.index + m[0].length;
  }
  if (last < item.prompt.length) out.push({ kind: 'text', text: item.prompt.slice(last) });
  return out;
});

// Per-blank text shown after submission (correct → user's i-th token, incorrect → expected i-th variant).
const userTokens = computed<string[]>(() => splitUserAnswers(userInput.value));

function blankAnswerText(blankIndex: number): string {
  if (feedback.value === 'correct') {
    return userTokens.value[blankIndex] ?? userInput.value;
  }
  return correctVariants.value[blankIndex] ?? correctVariants.value[0] ?? '';
}

const correctVariants = computed<string[]>(() => {
  const item = currentFillBlank.value;
  if (!item) return [];
  return fillBlankAnswerVariants(item.answer);
});

// Kana reading for each correct variant, when one can be derived from the
// cue's vocab entry. Empty strings keep the array aligned with `correctVariants`.
const correctVariantReadings = computed<string[]>(() => {
  const item = currentFillBlank.value;
  if (!item) return [];
  return correctVariants.value.map(v => kanaifyAnswer(v, item.cue, allVocab.value) ?? '');
});

const expectedAnswerCount = computed(() => correctVariants.value.length);

const fillBlankFormatHint = computed<string>(() => {
  const n = expectedAnswerCount.value;
  if (n <= 1) return t('practice.format_hint_single');
  return t('practice.format_hint_multi', { n });
});

const fillBlankPlaceholder = computed<string>(() => {
  return expectedAnswerCount.value > 1
    ? t('practice.type_multi', { n: expectedAnswerCount.value })
    : t('practice.type_here');
});

const grammarLabel = computed<string | null>(() => {
  const item = currentFillBlank.value;
  if (!item) return null;
  const gp = grammarById.value[item.grammar_point_id];
  return gp?.grammar_point ?? item.target_form ?? null;
});

const grammarRule = computed<string | null>(() => {
  const item = currentFillBlank.value;
  if (!item) return null;
  return grammarById.value[item.grammar_point_id]?.rule_summary ?? null;
});

// Per-mode metadata revealed after submission. Lives in script (not template)
// so each row's empty-checking stays out of the markup.
interface MetaRow { label: string; value: string; lang?: 'ja' }

const metaRows = computed<MetaRow[]>(() => {
  if (feedback.value === 'idle') return [];
  if (mode.value === 'fill_blank' && currentFillBlank.value) {
    const it = currentFillBlank.value;
    const gp = grammarById.value[it.grammar_point_id];
    const rows: MetaRow[] = [];
    const readings = correctVariantReadings.value.filter(Boolean);
    if (readings.length > 0) {
      rows.push({ label: t('practice.meta_reading'), value: readings.join(' / '), lang: 'ja' });
    }
    if (it.cue) {
      const cue = it.cue_form ? `${it.cue}（${it.cue_form}）` : it.cue;
      rows.push({ label: t('practice.meta_cue'), value: cue, lang: 'ja' });
    }
    if (it.target_form) rows.push({ label: t('practice.meta_target_form'), value: it.target_form, lang: 'ja' });
    if (gp?.grammar_point) rows.push({ label: t('practice.meta_grammar'), value: gp.grammar_point, lang: 'ja' });
    if (gp?.rule_summary) rows.push({ label: t('practice.meta_rule'), value: gp.rule_summary, lang: 'ja' });
    if (gp?.usage_note) rows.push({ label: t('practice.meta_example'), value: gp.usage_note, lang: 'ja' });
    if (it.notes) rows.push({ label: t('practice.meta_notes'), value: it.notes, lang: 'ja' });
    if (it.source_locator) rows.push({ label: t('practice.meta_source'), value: it.source_locator });
    if (it.source_page) rows.push({ label: t('practice.meta_page'), value: `p.${it.source_page}` });
    return rows;
  }
  if (currentVocab.value) {
    const v = currentVocab.value;
    const rows: MetaRow[] = [];
    // For vocab_reading the kanji is the "answer" itself — show it explicitly.
    if (mode.value === 'vocab_reading' && v.japanese) {
      rows.push({ label: t('practice.meta_japanese'), value: v.japanese, lang: 'ja' });
    }
    if (v.word_type) rows.push({ label: t('practice.meta_word_type'), value: v.word_type, lang: 'ja' });
    if (v.usage_note) rows.push({ label: t('practice.meta_usage'), value: v.usage_note, lang: 'ja' });
    if (v.source_section) rows.push({ label: t('practice.meta_section'), value: v.source_section, lang: 'ja' });
    if (v.source_locator) rows.push({ label: t('practice.meta_source'), value: v.source_locator });
    return rows;
  }
  return [];
});

// --- watchers -------------------------------------------------------------
watch(lesson, async (id) => {
  if (!vocabAllowed.value && mode.value !== 'fill_blank') {
    mode.value = 'fill_blank';
  }
  await loadLesson(id);
});

watch(mode, () => {
  startSession();
});

onMounted(async () => {
  window.addEventListener('keydown', onWindowKeydown);
  // Build the cross-lesson vocab pool eagerly. Cheap (≈ 5 small CSVs) and
  // means the fill-blank check can resolve cues whose vocab lives in another
  // lesson's CSV (e.g. 短いです in L35 → 短い is in an earlier textbook lesson
  // not shipped here, but most cross-lesson cues do find a match).
  const pools = await Promise.all(LESSON_IDS.map(id => loadVocab(id).catch(() => [])));
  allVocab.value = pools.flat();
  await loadLesson(lesson.value);
});

onUnmounted(() => {
  window.removeEventListener('keydown', onWindowKeydown);
});

function localizedMode(id: Mode): string {
  return t(`practice.${id === 'fill_blank' ? 'mode_fill_blank' : id === 'vocab_meaning' ? 'mode_vocab_meaning' : 'mode_vocab_reading'}`);
}

const accuracy = computed(() => {
  if (score.value.total === 0) return 0;
  return Math.round((score.value.correct / score.value.total) * 100);
});
</script>

<template>
  <main class="practice-shell ei-shell-bg text-foreground">
    <div class="practice-page">
      <!-- Header ---------------------------------------------- -->
      <header class="practice-header">
        <div>
          <div class="eyebrow eyebrow-kohaku">{{ $t('practice.eyebrow') }}</div>
          <h1 class="practice-h1">{{ $t('practice.heading') }}</h1>
          <p class="practice-sub">{{ $t('practice.subtitle') }}</p>
        </div>
        <div v-if="!isLoading && total > 0" class="practice-stats">
          <div class="pstat">
            <span class="pstat-n">{{ score.correct }}/{{ score.total }}</span>
            <span class="pstat-label">{{ $t('practice.score_label') }}</span>
          </div>
          <div class="pstat">
            <span class="pstat-n">{{ accuracy }}%</span>
            <span class="pstat-label">{{ $t('practice.accuracy_label') }}</span>
          </div>
        </div>
      </header>

      <!-- Pickers --------------------------------------------- -->
      <div class="filter-bar practice-filter-bar">
        <div class="filter-group">
          <span class="filter-label">{{ $t('practice.lesson_label') }}</span>
          <div class="chip-row">
            <button
              v-for="o in lessonOptions"
              :key="o.id"
              type="button"
              class="chip"
              :class="{ 'is-active': lesson === o.id }"
              @click="lesson = o.id"
            >
              {{ o.label }}
            </button>
          </div>
        </div>
        <div class="filter-group">
          <span class="filter-label">{{ $t('practice.mode_label') }}</span>
          <div class="chip-row">
            <button
              v-for="o in modeOptions"
              :key="o.id"
              type="button"
              class="chip"
              :class="{ 'is-active': mode === o.id, 'is-disabled': o.disabled }"
              :disabled="o.disabled"
              :title="o.disabled ? $t('practice.vocab_unavailable') : undefined"
              @click="!o.disabled && (mode = o.id)"
            >
              {{ $t(`practice.${o.key}`) }}
            </button>
          </div>
        </div>
      </div>

      <!-- Loading / error ------------------------------------- -->
      <div v-if="isLoading" class="empty-state">{{ $t('common.loading') }}</div>
      <div v-else-if="loadError" class="empty-state">{{ loadError }}</div>

      <!-- Session done banner --------------------------------- -->
      <section v-else-if="sessionDone" class="practice-done">
        <div class="practice-done-eyebrow eyebrow eyebrow-indigo">
          {{ $t('practice.session_complete') }}
        </div>
        <h2 class="practice-done-h">
          {{ $t('practice.session_score', { correct: score.correct, total: score.total }) }}
        </h2>
        <p class="practice-done-sub">
          {{ $t('practice.session_accuracy', { pct: accuracy }) }}
        </p>
        <div class="practice-done-actions">
          <button class="practice-btn practice-btn-primary" type="button" @click="startSession">
            {{ $t('practice.start_again') }}
          </button>
          <button
            v-if="mistakes.length > 0"
            class="practice-btn"
            type="button"
            @click="showMistakes = !showMistakes"
          >
            {{ showMistakes ? $t('practice.hide_mistakes') : $t('practice.review_mistakes', { n: mistakes.length }) }}
          </button>
        </div>
      </section>

      <!-- Active question ------------------------------------- -->
      <section v-else-if="total > 0" class="practice-card">
        <div class="practice-card-meta">
          <span class="eyebrow eyebrow-kohaku">{{ localizedMode(mode) }}</span>
          <span class="practice-progress">
            {{ $t('practice.progress', { i: cursor + 1, n: total }) }}
          </span>
        </div>

        <!-- Fill blank ------------------------------------- -->
        <template v-if="mode === 'fill_blank' && currentFillBlank">
          <p class="practice-prompt" lang="ja">
            <template v-for="(seg, i) in promptSegments" :key="i">
              <span v-if="seg.kind === 'text'">{{ seg.text }}</span>
              <span
                v-else
                class="practice-blank"
                :class="{
                  'is-correct': feedback === 'correct',
                  'is-incorrect': feedback === 'incorrect',
                }"
              >
                <template v-if="feedback === 'idle'">
                  <span class="practice-blank-cue">{{ seg.text }}</span>
                </template>
                <template v-else>
                  <span class="practice-blank-answer" lang="ja">
                    {{ blankAnswerText(seg.blankIndex ?? 0) }}
                  </span>
                </template>
              </span>
            </template>
          </p>
          <div v-if="grammarLabel" class="practice-grammar">
            <span class="eyebrow eyebrow-sm">{{ $t('practice.grammar_label') }}</span>
            <span class="practice-grammar-name" lang="ja">{{ grammarLabel }}</span>
            <span v-if="grammarRule" class="practice-grammar-rule" lang="ja">{{ grammarRule }}</span>
          </div>

          <p class="practice-answer-hint">
            <span class="eyebrow eyebrow-sm">{{ $t('practice.how_to_answer') }}</span>
            <span class="practice-answer-hint-text">{{ fillBlankFormatHint }}</span>
          </p>

          <div class="practice-input-row">
            <input
              v-model="userInput"
              type="text"
              class="practice-input"
              :placeholder="fillBlankPlaceholder"
              :disabled="feedback !== 'idle'"
              lang="ja"
              autocomplete="off"
              spellcheck="false"
              @keydown="onKeydown"
            />
            <button
              v-if="feedback === 'idle'"
              type="button"
              class="practice-btn practice-btn-primary"
              :disabled="!userInput.trim()"
              @click="onSubmit"
            >
              {{ $t('practice.check') }}
            </button>
            <button
              v-else
              type="button"
              class="practice-btn practice-btn-primary"
              @click="next"
            >
              {{ cursor + 1 >= total ? $t('practice.finish') : $t('practice.next') }}
            </button>
          </div>

          <div
            v-if="feedback !== 'idle'"
            class="practice-feedback"
            :class="`is-${feedback}`"
          >
            <div class="practice-feedback-head">
              <span class="eyebrow eyebrow-sm">
                {{ feedback === 'correct' ? $t('practice.correct') : $t('practice.incorrect') }}
              </span>
              <span v-if="feedback === 'incorrect'" class="practice-feedback-answer" lang="ja">
                {{ correctVariants.join(' / ') }}
              </span>
            </div>
            <p v-if="currentFillBlank.full_answer_sentence" class="practice-feedback-sentence" lang="ja">
              {{ currentFillBlank.full_answer_sentence }}
            </p>
            <dl v-if="metaRows.length" class="practice-meta">
              <template v-for="row in metaRows" :key="row.label">
                <dt class="practice-meta-label">{{ row.label }}</dt>
                <dd class="practice-meta-value" :lang="row.lang">{{ row.value }}</dd>
              </template>
            </dl>
          </div>
        </template>

        <!-- Vocab meaning MCQ ------------------------------ -->
        <template v-else-if="mode === 'vocab_meaning' && currentVocab && mcq">
          <div class="practice-vocab-headword">
            <p class="practice-japanese" lang="ja">{{ currentVocab.japanese }}</p>
            <p class="practice-kana" lang="ja">{{ currentVocab.kana }}</p>
            <p class="practice-wordtype">{{ currentVocab.word_type }}</p>
          </div>

          <div class="practice-choices">
            <button
              v-for="(c, i) in mcq.choices"
              :key="i"
              type="button"
              class="practice-choice"
              :class="{
                'is-selected': selectedChoice === i,
                'is-correct': feedback !== 'idle' && i === mcq.correctIndex,
                'is-wrong': feedback === 'incorrect' && selectedChoice === i,
              }"
              :disabled="feedback !== 'idle'"
              @click="checkMeaning(i)"
            >
              <span class="practice-choice-letter">{{ String.fromCharCode(65 + i) }}</span>
              <span class="practice-choice-text">{{ c }}</span>
            </button>
          </div>

          <div
            v-if="feedback !== 'idle'"
            class="practice-feedback"
            :class="`is-${feedback}`"
          >
            <div class="practice-feedback-head">
              <span class="eyebrow eyebrow-sm">
                {{ feedback === 'correct' ? $t('practice.correct') : $t('practice.incorrect') }}
              </span>
              <span class="practice-feedback-answer">
                {{ currentVocab.chinese_meaning }}
              </span>
            </div>
            <dl v-if="metaRows.length" class="practice-meta">
              <template v-for="row in metaRows" :key="row.label">
                <dt class="practice-meta-label">{{ row.label }}</dt>
                <dd class="practice-meta-value" :lang="row.lang">{{ row.value }}</dd>
              </template>
            </dl>
            <button
              type="button"
              class="practice-btn practice-btn-primary practice-feedback-next"
              @click="next"
            >
              {{ cursor + 1 >= total ? $t('practice.finish') : $t('practice.next') }}
            </button>
          </div>
        </template>

        <!-- Vocab reading typing --------------------------- -->
        <template v-else-if="mode === 'vocab_reading' && currentVocab">
          <div class="practice-vocab-headword">
            <p class="practice-meaning">{{ currentVocab.chinese_meaning }}</p>
            <p class="practice-wordtype">{{ currentVocab.word_type }}</p>

            <!-- Kanji hint: hidden by default, revealed on tap or submission -->
            <div class="practice-hint-row">
              <button
                v-if="!revealKanji && feedback === 'idle'"
                type="button"
                class="practice-hint-btn"
                @click="revealKanji = true"
              >
                {{ $t('practice.show_kanji') }}
              </button>
              <p
                v-else
                class="practice-japanese practice-japanese-sm"
                lang="ja"
              >{{ currentVocab.japanese }}</p>
            </div>
          </div>

          <p class="practice-answer-hint">
            <span class="eyebrow eyebrow-sm">{{ $t('practice.how_to_answer') }}</span>
            <span class="practice-answer-hint-text">{{ $t('practice.format_hint_reading') }}</span>
          </p>

          <div class="practice-input-row">
            <input
              v-model="userInput"
              type="text"
              class="practice-input"
              :placeholder="$t('practice.type_kana')"
              :disabled="feedback !== 'idle'"
              lang="ja"
              autocomplete="off"
              spellcheck="false"
              @keydown="onKeydown"
            />
            <button
              v-if="feedback === 'idle'"
              type="button"
              class="practice-btn practice-btn-primary"
              :disabled="!userInput.trim()"
              @click="onSubmit"
            >
              {{ $t('practice.check') }}
            </button>
            <button
              v-else
              type="button"
              class="practice-btn practice-btn-primary"
              @click="next"
            >
              {{ cursor + 1 >= total ? $t('practice.finish') : $t('practice.next') }}
            </button>
          </div>

          <div
            v-if="feedback !== 'idle'"
            class="practice-feedback"
            :class="`is-${feedback}`"
          >
            <div class="practice-feedback-head">
              <span class="eyebrow eyebrow-sm">
                {{ feedback === 'correct' ? $t('practice.correct') : $t('practice.incorrect') }}
              </span>
              <span class="practice-feedback-answer" lang="ja">{{ currentVocab.kana }}</span>
            </div>
            <dl v-if="metaRows.length" class="practice-meta">
              <template v-for="row in metaRows" :key="row.label">
                <dt class="practice-meta-label">{{ row.label }}</dt>
                <dd class="practice-meta-value" :lang="row.lang">{{ row.value }}</dd>
              </template>
            </dl>
          </div>
        </template>
      </section>

      <!-- Mistakes drawer (toggle) ----------------------------- -->
      <section
        v-if="!isLoading && mistakes.length > 0"
        class="practice-mistakes"
      >
        <div class="section-title-row practice-section-row">
          <h3 class="section-title">{{ $t('practice.mistakes_title') }}</h3>
          <button
            type="button"
            class="filter-clear"
            @click="showMistakes = !showMistakes"
          >
            {{ showMistakes ? $t('practice.hide') : $t('practice.show', { n: mistakes.length }) }}
          </button>
        </div>
        <ol v-if="showMistakes" class="practice-mistake-list">
          <li v-for="(m, i) in mistakes" :key="m.id" class="practice-mistake">
            <span class="practice-mistake-num">{{ String(i + 1).padStart(2, '0') }}</span>
            <div class="practice-mistake-body">
              <p class="practice-mistake-prompt" lang="ja">{{ m.prompt }}</p>
              <p class="practice-mistake-line">
                <span class="eyebrow eyebrow-sm">{{ $t('practice.your_answer') }}</span>
                <span class="practice-strike" lang="ja">{{ m.userAnswer }}</span>
              </p>
              <p class="practice-mistake-line">
                <span class="eyebrow eyebrow-sm eyebrow-kohaku">{{ $t('practice.correction') }}</span>
                <span class="practice-correct" lang="ja">{{ m.correctAnswer }}</span>
              </p>
              <p
                v-if="m.fullSentence"
                class="practice-mistake-full"
                lang="ja"
              >{{ m.fullSentence }}</p>
              <p v-if="m.hint" class="practice-mistake-hint" lang="ja">{{ m.hint }}</p>
            </div>
          </li>
        </ol>
      </section>
    </div>
  </main>
</template>

<style scoped>
.practice-shell {
  min-height: calc(100vh - var(--app-chrome-h));
  padding: 56px 32px 80px;
}
.practice-page {
  max-width: 880px;
  margin: 0 auto;
}

/* Header ------------------------------------------------------ */
.practice-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
  margin-bottom: 28px;
}
.practice-h1 {
  font-family: var(--font-serif);
  font-size: 2.2rem;
  margin: 6px 0 4px;
  color: var(--foreground);
  font-weight: 500;
}
.practice-sub {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.95rem;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  margin: 0;
  max-width: 540px;
}
.practice-stats {
  display: flex;
  gap: 32px;
}
.pstat { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
.pstat-n {
  font-family: var(--font-serif);
  font-size: 1.5rem;
  color: var(--foreground);
}
.pstat-label {
  font-family: var(--font-sans);
  font-size: 0.62rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}

/* Filter bar override (less padding) -------------------------- */
.practice-filter-bar {
  padding: 10px 0 18px;
  margin-bottom: 28px;
  gap: 28px;
}
.chip.is-disabled {
  color: color-mix(in oklab, var(--foreground) 25%, transparent);
  cursor: not-allowed;
}

/* Card -------------------------------------------------------- */
.practice-card {
  background: var(--surface-container-lowest, var(--background));
  border: 1px solid color-mix(in oklab, var(--foreground) 8%, transparent);
  border-radius: 4px;
  padding: 32px;
}
.practice-card-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 18px;
}
.practice-progress {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
}

.practice-prompt {
  font-family: var(--font-serif);
  font-size: 1.5rem;
  line-height: 1.65;
  color: var(--foreground);
  margin: 8px 0 18px;
}
.practice-blank {
  display: inline-block;
  min-width: 5ch;
  padding: 2px 10px;
  margin: 0 2px;
  border-bottom: 2px solid color-mix(in oklab, var(--secondary) 70%, transparent);
  background: color-mix(in oklab, var(--secondary) 8%, transparent);
  border-radius: 2px;
  text-align: center;
}
.practice-blank.is-correct {
  border-bottom-color: var(--primary);
  background: color-mix(in oklab, var(--primary) 10%, transparent);
}
.practice-blank.is-incorrect {
  border-bottom-color: var(--destructive);
  background: color-mix(in oklab, var(--destructive) 10%, transparent);
}
.practice-blank-cue {
  font-style: italic;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  font-size: 0.95em;
}
.practice-blank-answer {
  font-weight: 500;
  color: var(--foreground);
}

.practice-grammar {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 7%, transparent);
}
.practice-grammar-name {
  font-family: var(--font-serif);
  font-size: 0.95rem;
  color: var(--foreground);
}
.practice-grammar-rule {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.85rem;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  flex-basis: 100%;
}

/* Vocab card body --------------------------------------------- */
.practice-vocab-headword {
  text-align: center;
  padding: 24px 0 28px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 7%, transparent);
  margin-bottom: 24px;
}
.practice-japanese {
  font-family: var(--font-serif);
  font-size: 2.4rem;
  margin: 0 0 6px;
  color: var(--foreground);
}
.practice-japanese-sm {
  font-size: 1.4rem;
  margin: 0;
}
.practice-meaning {
  font-family: var(--font-serif);
  font-size: 1.85rem;
  margin: 0 0 8px;
  color: var(--foreground);
}
.practice-kana {
  font-family: var(--font-serif);
  font-size: 1.05rem;
  color: color-mix(in oklab, var(--foreground) 65%, transparent);
  margin: 0 0 6px;
}
.practice-wordtype {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
  margin: 0;
}
.practice-hint-row {
  margin-top: 14px;
  min-height: 32px;
  display: flex;
  justify-content: center;
}
.practice-hint-btn {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px 0;
  border-bottom: 1px dashed color-mix(in oklab, var(--secondary) 60%, transparent);
  transition: color 160ms ease, border-color 160ms ease;
}
.practice-hint-btn:hover {
  color: var(--secondary);
  border-bottom-color: var(--secondary);
}

.practice-choices {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}
@media (min-width: 640px) {
  .practice-choices { grid-template-columns: 1fr 1fr; }
}
.practice-choice {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border: 1px solid color-mix(in oklab, var(--foreground) 12%, transparent);
  background: var(--background);
  text-align: left;
  cursor: pointer;
  border-radius: 3px;
  transition: border-color 160ms ease, background 160ms ease;
  font-family: var(--font-serif);
  font-size: 1rem;
  color: var(--foreground);
}
.practice-choice:hover:not(:disabled) {
  border-color: color-mix(in oklab, var(--secondary) 60%, transparent);
}
.practice-choice-letter {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.18em;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  width: 14px;
  flex-shrink: 0;
}
.practice-choice.is-selected { border-color: var(--primary); }
.practice-choice.is-correct {
  border-color: var(--primary);
  background: color-mix(in oklab, var(--primary) 8%, transparent);
}
.practice-choice.is-wrong {
  border-color: var(--destructive);
  background: color-mix(in oklab, var(--destructive) 8%, transparent);
}

/* Answer-format hint ------------------------------------------ */
.practice-answer-hint {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
  margin: 0 0 10px;
  padding: 0;
}
.practice-answer-hint-text {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.9rem;
  color: color-mix(in oklab, var(--foreground) 65%, transparent);
}

/* Input row --------------------------------------------------- */
.practice-input-row {
  display: flex;
  gap: 12px;
  align-items: stretch;
  margin-top: 4px;
}
.practice-input {
  flex: 1 1 auto;
  font-family: var(--font-serif);
  font-size: 1.1rem;
  padding: 10px 14px;
  border: 1px solid color-mix(in oklab, var(--foreground) 18%, transparent);
  background: var(--background);
  color: var(--foreground);
  border-radius: 2px;
  outline: none;
  transition: border-color 160ms ease;
}
.practice-input:focus {
  border-color: var(--primary);
}
.practice-input:disabled {
  background: color-mix(in oklab, var(--foreground) 4%, transparent);
}

.practice-btn {
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
.practice-btn:hover:not(:disabled) {
  border-color: var(--primary);
  color: var(--primary);
}
.practice-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.practice-btn-primary {
  background: var(--primary);
  border-color: var(--primary);
  color: var(--primary-foreground, #fff);
}
.practice-btn-primary:hover:not(:disabled) {
  background: color-mix(in oklab, var(--primary) 88%, black);
  color: var(--primary-foreground, #fff);
  border-color: color-mix(in oklab, var(--primary) 88%, black);
}

/* Feedback panel --------------------------------------------- */
.practice-feedback {
  margin-top: 22px;
  padding: 16px 18px;
  border-left: 3px solid color-mix(in oklab, var(--primary) 70%, transparent);
  background: color-mix(in oklab, var(--primary) 4%, transparent);
}
.practice-feedback.is-incorrect {
  border-left-color: var(--destructive);
  background: color-mix(in oklab, var(--destructive) 5%, transparent);
}
.practice-feedback-head {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
}
.practice-feedback-answer {
  font-family: var(--font-serif);
  font-size: 1.05rem;
  color: var(--foreground);
}
.practice-feedback-sentence {
  margin: 8px 0 0;
  font-family: var(--font-serif);
  font-size: 1rem;
  line-height: 1.6;
  color: color-mix(in oklab, var(--foreground) 80%, transparent);
}
.practice-feedback-next {
  margin-top: 14px;
}

.practice-meta {
  margin: 14px 0 0;
  padding: 12px 0 0;
  border-top: 1px solid color-mix(in oklab, var(--foreground) 7%, transparent);
  display: grid;
  grid-template-columns: max-content 1fr;
  column-gap: 18px;
  row-gap: 6px;
}
.practice-meta-label {
  font-family: var(--font-sans);
  font-size: 0.62rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
  margin: 0;
  align-self: baseline;
  padding-top: 2px;
}
.practice-meta-value {
  font-family: var(--font-serif);
  font-size: 0.95rem;
  line-height: 1.5;
  color: color-mix(in oklab, var(--foreground) 85%, transparent);
  margin: 0;
}

/* Done banner ------------------------------------------------ */
.practice-done {
  text-align: center;
  padding: 64px 24px;
  border: 1px solid color-mix(in oklab, var(--foreground) 8%, transparent);
  border-radius: 4px;
  background: var(--surface-container-lowest, var(--background));
}
.practice-done-eyebrow { margin-bottom: 12px; }
.practice-done-h {
  font-family: var(--font-serif);
  font-size: 1.8rem;
  margin: 0 0 6px;
  color: var(--foreground);
  font-weight: 500;
}
.practice-done-sub {
  font-family: var(--font-serif);
  font-style: italic;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  margin: 0 0 22px;
}
.practice-done-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

/* Mistakes ---------------------------------------------------- */
.practice-mistakes { margin-top: 56px; }
.practice-section-row { margin-bottom: 18px; }
.practice-mistake-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.practice-mistake {
  display: grid;
  grid-template-columns: 36px 1fr;
  gap: 14px;
  padding: 16px 18px;
  border: 1px solid color-mix(in oklab, var(--foreground) 7%, transparent);
  border-radius: 3px;
  background: var(--background);
}
.practice-mistake-num {
  font-family: var(--font-serif);
  font-style: italic;
  color: color-mix(in oklab, var(--foreground) 45%, transparent);
}
.practice-mistake-body { display: flex; flex-direction: column; gap: 6px; }
.practice-mistake-prompt {
  font-family: var(--font-serif);
  font-size: 1.02rem;
  margin: 0 0 4px;
  color: var(--foreground);
}
.practice-mistake-line {
  display: flex;
  gap: 10px;
  align-items: baseline;
  margin: 0;
}
.practice-strike {
  font-family: var(--font-serif);
  text-decoration: line-through;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
}
.practice-correct {
  font-family: var(--font-serif);
  color: var(--foreground);
  font-weight: 500;
}
.practice-mistake-full {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.92rem;
  color: color-mix(in oklab, var(--foreground) 65%, transparent);
  margin: 4px 0 0;
}
.practice-mistake-hint {
  font-family: var(--font-sans);
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
  margin: 2px 0 0;
}
</style>
