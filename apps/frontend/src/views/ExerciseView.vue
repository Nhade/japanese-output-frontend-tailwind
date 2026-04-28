<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue';
import type { ComponentPublicInstance } from 'vue';
import MarkdownIt from 'markdown-it';
import { useI18n } from 'vue-i18n';

import LoadingSpinner from '@/components/LoadingSpinner.vue';
import HankoSeal from '@/components/exercise/HankoSeal.vue';
import MarginNote from '@/components/exercise/MarginNote.vue';
import SegmentedToggle from '@/components/exercise/SegmentedToggle.vue';
import BlankSlot from '@/components/exercise/BlankSlot.vue';
import ChoiceFootnote from '@/components/exercise/ChoiceFootnote.vue';

import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

import { useAuthStore } from '@/stores/auth';
import { useToastStore } from '@/stores/toast';
import { apiUrl } from '../lib/api';

interface Exercise {
  exercise_id: string;
  question_sentence: string;
  hint_chinese: string;
  correct_answer?: string;
  part_of_speech?: string;
  jlpt_level?: number | null;
  choices?: string[];
}

interface Feedback {
  is_correct: boolean;
  correct_answer: string;
  log_id: string;
  focus_diff?: Record<string, unknown>;
  feedback?: string;
  score?: number;
  error_type?: string;
  retry_count?: number;
}

const { t } = useI18n();

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
});

// The blank marker the backend embeds in `question_sentence` for fill-in
// prompts (see tools/backfill_exercises.py and apps/backend/video_service.py).
// In feedback states we replace the marker with a BlankSlot showing the
// user's answer / the correct answer; the marker itself reads as the blank
// in the initial state, so no extra underline decoration is needed.
const BLANK_MARKER = '[＿＿＿]';

const exercise = ref<Exercise | null>(null);
const feedback = ref<Feedback | null>(null);
const detailedFeedback = ref<string | null>(null);
const showDetailModal = ref(false);
const detailedError = ref<string | null>(null);
const isLoading = ref(true);
const isLoadingDetailed = ref(false);
const auth = useAuthStore();
const toastStore = useToastStore();
const userAnswer = ref('');
const showHint = ref(false);
// Shadcn-vue's Button is a Vue component; a template ref on it resolves to
// the component instance (not the raw DOM node). We reach the underlying
// element through `$el` via the small helper below.
const nextQuestionButton = ref<ComponentPublicInstance | null>(null);
const answerInput = ref<HTMLInputElement | null>(null);
const exerciseMode = ref<'typing' | 'mcq'>('typing');
const selectedChoice = ref<string | null>(null);
const choices = ref<string[]>([]);
const isExplaining = ref(false);
// Drives the full-spread page-leaf flip overlay on Next. A ~520ms timeout
// covers the swap, giving the eye a single "leaf turning" moment instead of
// a hard-cut between exercises.
const turning = ref(false);

function focusComponent(ref: ComponentPublicInstance | null): void {
  const el = ref?.$el as HTMLElement | undefined;
  el?.focus?.();
}

const promptParts = computed<string[]>(() => {
  if (!exercise.value) return [];
  return exercise.value.question_sentence.split(BLANK_MARKER);
});

const hasBlank = computed(() => promptParts.value.length > 1);

const blankState = computed<'initial' | 'correct' | 'incorrect'>(() => {
  if (!feedback.value) return 'initial';
  return feedback.value.is_correct ? 'correct' : 'incorrect';
});

// Adaptive prompt sizing — long Japanese sentences wrap to many lines at the
// editorial default font-size, pushing content below the fold. We scale the
// prompt down (and tighten line-height) past a few length tiers so the whole
// spread fits a typical laptop viewport without scrolling.
const promptLengthClass = computed<'lg' | 'md' | 'sm' | 'xs'>(() => {
  if (!exercise.value) return 'lg';
  // Strip the blank marker so its width isn't counted.
  const visible = exercise.value.question_sentence.split(BLANK_MARKER).join('');
  const n = [...visible].length;
  if (n <= 25) return 'lg';
  if (n <= 45) return 'md';
  if (n <= 75) return 'sm';
  return 'xs';
});

async function fetchNewExercise() {
  isLoading.value = true;
  feedback.value = null;
  detailedFeedback.value = null;
  showDetailModal.value = false;
  detailedError.value = null;
  exercise.value = null;
  userAnswer.value = '';
  selectedChoice.value = null;
  choices.value = [];
  showHint.value = false;

  try {
    const url = `${apiUrl('/api/exercise/random')}`
      + (exerciseMode.value === 'mcq' ? '?mode=mcq' : '');
    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) throw new Error('Network response was not ok');
    const data = await response.json();
    exercise.value = data;
    if (data.choices) choices.value = data.choices;
  } catch (error) {
    console.error('Failed to fetch exercise:', error);
  } finally {
    isLoading.value = false;
    await nextTick();
    if (exerciseMode.value === 'typing') answerInput.value?.focus?.();
  }
}

function switchMode(mode: string) {
  if (mode !== 'typing' && mode !== 'mcq') return;
  if (exerciseMode.value === mode) return;
  exerciseMode.value = mode;
  fetchNewExercise();
}

async function handleAnswerSubmit() {
  if (!exercise.value) return;
  if (exerciseMode.value === 'mcq') {
    if (!selectedChoice.value) return;
    userAnswer.value = selectedChoice.value;
  } else {
    if (!userAnswer.value.trim()) return;
  }

  try {
    const response = await fetch(`${apiUrl('/api/exercise/submit')}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        exercise_id: exercise.value.exercise_id,
        user_answer: userAnswer.value.trim(),
        user_id: auth.user_id,
      }),
    });
    if (!response.ok) throw new Error('Submission failed');

    const result = await response.json();
    feedback.value = result;

    if (result.focus_diff && result.focus_diff.updated) {
      const diff = result.focus_diff;
      const rawTag = diff.tag ? diff.tag.trim() : '';
      const tag = rawTag ? t(`pos.${rawTag.toLowerCase()}`, rawTag) : '';

      let msg = '';
      if (diff.rotated) {
        const rawNewTag = diff.new_tag ? diff.new_tag.trim() : '';
        const newTag = rawNewTag ? t(`pos.${rawNewTag.toLowerCase()}`, rawNewTag) : '';
        msg = t('exercise.focus_toast_completed', { tag: newTag });
        toastStore.trigger(msg, 'success');
      } else {
        msg = t('exercise.focus_toast_progress', {
          tag: tag,
          progress: diff.progress,
          target: diff.target,
        });
        toastStore.trigger(msg, 'info');
      }
    }

    await nextTick();
    focusComponent(nextQuestionButton.value);

    if (result.log_id && !result.is_correct) {
      const currentExerciseId = exercise.value.exercise_id;
      isExplaining.value = true;
      try {
        const explainResponse = await fetch(`${apiUrl('/api/exercise/explain')}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ log_id: result.log_id }),
        });

        if (!explainResponse.ok) {
          // Surface the failure instead of silently swallowing it.
          const text = await explainResponse.text().catch(() => '');
          console.error('AI explain endpoint failed:', explainResponse.status, text);
          if (exercise.value && exercise.value.exercise_id === currentExerciseId) {
            feedback.value = {
              ...(feedback.value as Feedback),
              feedback: text || t('exercise.network_error'),
            };
          }
        } else {
          const explanation = await explainResponse.json();
          // Diagnostic: log raw shape so missing/renamed keys are obvious.
          console.debug('[explain] response:', explanation);
          if (exercise.value && exercise.value.exercise_id === currentExerciseId) {
            // Explicitly pick feedback so an unexpected response shape
            // (e.g. nested under `result`) can't leave us empty silently.
            const brief =
              explanation?.feedback
              ?? explanation?.result?.feedback
              ?? explanation?.reasoning
              ?? '';

            feedback.value = {
              ...(feedback.value as Feedback),
              ...explanation,
              feedback: brief,
            };

            if (brief && typeof brief === 'string' && brief.includes('Safety violation')) {
              toastStore.trigger(t('chat.safety_violation'), 'error');
            }
          }
        }
      } catch (err) {
        console.error('AI explanation failed:', err);
        if (exercise.value && exercise.value.exercise_id === currentExerciseId) {
          feedback.value = {
            ...(feedback.value as Feedback),
            feedback: t('exercise.network_error'),
          };
        }
      } finally {
        if (exercise.value && exercise.value.exercise_id === currentExerciseId) {
          isExplaining.value = false;
        }
      }
    }
  } catch (error) {
    console.error('Failed to submit answer:', error);
  }
}

async function revealHint() {
  showHint.value = true;
  await nextTick();
  answerInput.value?.focus?.();
}

async function fetchDetailedFeedback() {
  if (!feedback.value || !feedback.value.log_id) return;

  isLoadingDetailed.value = true;
  detailedError.value = null;
  try {
    const response = await fetch(`${apiUrl('/api/exercise/explain-detailed')}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ log_id: feedback.value.log_id }),
    });

    if (response.ok) {
      const data = await response.json();
      if (data.detailed_feedback && data.detailed_feedback.includes('Safety violation')) {
        toastStore.trigger(t('chat.safety_violation'), 'error');
        return;
      }
      detailedFeedback.value = data.detailed_feedback;
      showDetailModal.value = true;
    } else {
      const err = await response.json();
      detailedError.value = err.error || 'Failed to fetch explanation';
    }
  } catch (error) {
    console.error('Failed to fetch detailed feedback:', error);
    detailedError.value = 'Network error or server unavailable.';
  } finally {
    isLoadingDetailed.value = false;
  }
}

function handleNext() {
  if (turning.value) return;
  // If the user has reduced motion enabled, skip the leaf-flip overlay and
  // load the next exercise immediately.
  const reduceMotion = typeof window !== 'undefined'
    && window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduceMotion) {
    fetchNewExercise();
    return;
  }
  turning.value = true;
  window.setTimeout(() => {
    turning.value = false;
    fetchNewExercise();
  }, 520);
}

function handleKeydown(event: KeyboardEvent) {
  if (event.altKey && event.key === 'h') {
    event.preventDefault();
    revealHint();
  }
}

onMounted(() => {
  fetchNewExercise();
  window.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
  <main class="exercise-shell ei-shell-bg relative text-foreground">
    <div class="mx-auto max-w-6xl px-6 md:px-12 pt-6 md:pt-8 pb-12 md:pb-16">
      <!-- Initial load -->
      <div v-if="isLoading" class="flex items-center justify-center py-32">
        <LoadingSpinner />
      </div>

      <template v-else-if="exercise">
        <!-- Header row — topic kanji + JLPT eyebrow + segmented toggle -->
        <header class="exercise-header">
          <div class="header-meta">
            <span v-if="exercise.part_of_speech" lang="ja" class="topic">
              {{ exercise.part_of_speech }}
            </span>
            <span v-if="exercise.jlpt_level" class="jlpt-eyebrow">
              N{{ exercise.jlpt_level }}
            </span>
          </div>
          <SegmentedToggle
            :model-value="exerciseMode"
            :options="[
              { value: 'typing', label: $t('exercise.mode_typing') },
              { value: 'mcq', label: $t('exercise.mode_mcq') },
            ]"
            @update:model-value="switchMode"
          />
        </header>

        <!-- Spread — verso (prompt) | gutter | recto (response) -->
        <article class="spread">
          <div class="gutter" aria-hidden="true" />

          <!-- Verso — prompt -->
          <section
            :key="'verso-' + exercise.exercise_id + '-' + blankState"
            class="verso anim-page-turn"
          >
            <div class="eyebrow verso-eyebrow">
              {{ feedback ? $t('exercise.eyebrow_your_reading') : $t('exercise.eyebrow_fill_blank') }}
            </div>

            <h1 lang="ja" class="prompt" :class="`prompt--${promptLengthClass}`">
              <template v-if="hasBlank">
                <template v-for="(chunk, i) in promptParts" :key="i"
                  >{{ chunk }}<BlankSlot
                    v-if="i < promptParts.length - 1"
                    :state="blankState"
                    :user-answer="userAnswer"
                    :correct-answer="feedback?.correct_answer ?? exercise.correct_answer ?? ''"
                /></template>
              </template>
              <template v-else>{{ exercise.question_sentence }}</template>
            </h1>

            <!-- Hint — left-bordered editorial block (only outside feedback) -->
            <transition name="rise">
              <div v-if="showHint && !feedback" class="hint-block">
                <div class="eyebrow-sm hint-label">{{ $t('exercise.eyebrow_hint') }}</div>
                <p lang="zh-Hant" class="hint-text">{{ exercise.hint_chinese }}</p>
              </div>
            </transition>

            <!-- Retry marker for incorrect state -->
            <div
              v-if="feedback && !feedback.is_correct && feedback.retry_count && feedback.retry_count > 0"
              class="retry-marker"
            >
              <span class="eyebrow-sm">{{ $t('exercise.retried') }} · {{ feedback.retry_count }}</span>
              <span class="retry-rule" aria-hidden="true" />
            </div>
          </section>

          <!-- Recto — response -->
          <section
            :key="'recto-' + exercise.exercise_id + '-' + blankState + '-' + exerciseMode"
            class="recto"
            :class="{ 'is-feedback': !!feedback }"
          >
            <!-- Typing initial -->
            <form
              v-if="!feedback && exerciseMode === 'typing'"
              class="recto-stack anim-page-turn"
              @submit.prevent="handleAnswerSubmit"
            >
              <div class="eyebrow recto-eyebrow">{{ $t('exercise.eyebrow_your_answer') }}</div>
              <input
                ref="answerInput"
                v-model="userAnswer"
                class="input-line"
                :placeholder="$t('exercise.type_here')"
                autocomplete="off"
                autofocus
                type="text"
              />
              <div class="action-row">
                <Button
                  type="submit"
                  variant="shiori"
                  size="auto"
                  :disabled="!userAnswer.trim()"
                >
                  {{ $t('exercise.check_answer') }}
                </Button>
                <Button
                  v-if="!showHint"
                  type="button"
                  variant="ghost-serif"
                  size="auto"
                  @click="revealHint"
                >
                  {{ $t('exercise.show_hint') }}
                </Button>
              </div>
              <div class="kbd-row">
                <span class="kbd-pair">
                  <kbd class="kbd">Enter</kbd>
                  <span>{{ $t('exercise.kbd_submit_hint') }}</span>
                </span>
                <span aria-hidden="true" class="kbd-sep">·</span>
                <span class="kbd-pair">
                  <kbd class="kbd">Alt</kbd>
                  <span aria-hidden="true">+</span>
                  <kbd class="kbd">H</kbd>
                  <span>{{ $t('exercise.kbd_hint_hint') }}</span>
                </span>
              </div>
            </form>

            <!-- MCQ initial -->
            <div
              v-else-if="!feedback && exerciseMode === 'mcq'"
              class="recto-stack anim-page-turn"
            >
              <div class="eyebrow recto-eyebrow">{{ $t('exercise.eyebrow_options') }}</div>
              <ol class="footnote-list">
                <ChoiceFootnote
                  v-for="(choice, index) in choices"
                  :key="choice"
                  :choice="choice"
                  :index="index"
                  :selected="selectedChoice === choice"
                  :selected-label="$t('exercise.eyebrow_selected')"
                  @select="selectedChoice = choice"
                />
              </ol>
              <div class="action-row mcq-action-row">
                <Button
                  type="button"
                  variant="shiori"
                  size="auto"
                  :disabled="!selectedChoice"
                  @click="handleAnswerSubmit"
                >
                  {{ $t('exercise.check_answer') }}
                </Button>
                <Button
                  v-if="!showHint"
                  type="button"
                  variant="ghost-serif"
                  size="auto"
                  @click="revealHint"
                >
                  {{ $t('exercise.show_hint') }}
                </Button>
              </div>
            </div>

            <!-- Correct -->
            <div v-else-if="feedback && feedback.is_correct" class="recto-stack anim-ink">
              <div class="eyebrow recto-eyebrow recto-eyebrow--primary">
                {{ $t('exercise.eyebrow_reading_confirmed') }}
              </div>
              <p lang="ja" class="recto-headline">
                「{{ feedback.correct_answer }}」
              </p>
              <p lang="zh-Hant" class="recto-gloss">完全正確。</p>

              <div class="recto-footer">
                <Button
                  ref="nextQuestionButton"
                  variant="shiori"
                  size="auto"
                  @click="handleNext"
                >
                  {{ $t('exercise.next_question') }}
                </Button>
                <HankoSeal
                  :label="'正解'"
                  :aria-label="$t('exercise.mastered')"
                  :rotation="-5"
                  :size="84"
                />
              </div>
            </div>

            <!-- Incorrect -->
            <div v-else-if="feedback && !feedback.is_correct" class="recto-stack anim-ink">
              <div class="eyebrow recto-eyebrow recto-eyebrow--secondary">
                {{ $t('exercise.eyebrow_revision') }}
              </div>
              <div class="correct-block">
                <p lang="ja" class="recto-headline recto-headline--primary">
                  {{ feedback.correct_answer }}
                </p>
                <p class="recto-undertag">{{ $t('exercise.correct_answer_label') }}</p>
              </div>

              <MarginNote v-if="feedback.feedback">
                {{ feedback.feedback }}
              </MarginNote>
              <div v-else-if="isExplaining" class="analyzing-row">
                <div class="analyzing-spinner"><LoadingSpinner /></div>
                <span>{{ $t('exercise.analyzing') }}</span>
              </div>
              <p v-else class="no-brief-note">{{ $t('exercise.no_brief_note') }}</p>

              <div class="recto-footer">
                <Button
                  ref="nextQuestionButton"
                  variant="shiori"
                  size="auto"
                  @click="handleNext"
                >
                  {{ $t('exercise.next_question') }}
                </Button>
                <Button
                  variant="ghost-serif"
                  size="auto"
                  :disabled="isLoadingDetailed"
                  @click="!detailedFeedback ? fetchDetailedFeedback() : (showDetailModal = true)"
                >
                  <span v-if="isLoadingDetailed">{{ $t('exercise.analyzing') }}</span>
                  <span v-else-if="detailedFeedback">{{ $t('exercise.view_detailed') }}</span>
                  <span v-else>{{ $t('exercise.explain_in_full') }}</span>
                </Button>
              </div>
              <p v-if="detailedError" class="detailed-error">{{ detailedError }}</p>
            </div>
          </section>

          <!-- Page-leaf flip overlay — a single warm paper sheet sweeps the
               spread right-to-left, no leading shadow band. -->
          <div v-if="turning" class="turn-sheet" aria-hidden="true" />
        </article>
      </template>

      <div v-else class="exercise-empty">
        <div class="eyebrow exercise-empty-eyebrow">{{ $t('exercise.eyebrow_fill_blank') }}</div>
        <h2 class="exercise-empty-title">{{ $t('exercise.error_title') }}</h2>
        <p class="exercise-empty-body">{{ $t('exercise.error_body') }}</p>
        <Button variant="shiori" size="auto" class="exercise-empty-cta" @click="fetchNewExercise">
          {{ $t('exercise.error_retry') }}
        </Button>
      </div>
    </div>

    <!-- Detailed AI explanation — glass-overlay Dialog (design doc §2 / §4) -->
    <Dialog :open="showDetailModal" @update:open="showDetailModal = $event">
      <DialogContent>
        <DialogHeader>
          <DialogTitle class="font-serif text-2xl md:text-3xl text-foreground tracking-tight">
            {{ $t('exercise.detailed_modal_title') }}
          </DialogTitle>
        </DialogHeader>
        <div v-if="detailedFeedback" class="prose-shiori max-w-none">
          <div v-html="md.render(detailedFeedback)"></div>
        </div>
      </DialogContent>
    </Dialog>
  </main>
</template>

<style scoped>
/* --------------------------------------------------------------------
   Page surface — same warm vertical gradient as the prior layout. The
   spread sits on top, anchored by the global app shell.
-------------------------------------------------------------------- */
.exercise-shell {
  min-height: calc(100vh - var(--app-chrome-h));
  /* paper gradient comes from the global .ei-shell-bg utility */
}

/* Empty / error state — paper-quiet, mirrors the Exercise editorial
   typography so a failed fetch still sits inside the spread language. */
.exercise-empty {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 14px;
  max-width: 520px;
  margin: 80px auto 0;
  padding: 0 8px;
}
.exercise-empty-eyebrow {
  color: color-mix(in oklab, var(--secondary) 85%, transparent);
}
.exercise-empty-title {
  font-family: var(--font-serif);
  font-size: clamp(1.8rem, 3vw, 2.4rem);
  letter-spacing: -0.005em;
  line-height: 1.18;
  color: var(--foreground);
  margin: 0;
}
.exercise-empty-body {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 1rem;
  line-height: 1.6;
  color: color-mix(in oklab, var(--foreground) 65%, transparent);
  margin: 0;
  max-width: 440px;
}
.exercise-empty-cta { margin-top: 10px; }

/* Header row -------------------------------------------------------- */
.exercise-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 18px;
  margin-bottom: 28px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 12%, transparent);
}
.header-meta {
  display: flex;
  align-items: baseline;
  gap: 16px;
  flex-wrap: wrap;
}
.topic {
  font-family: var(--font-serif);
  font-size: 1.4rem;
  color: var(--foreground);
  letter-spacing: 0.02em;
}
.jlpt-eyebrow {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.2em;
  font-size: 0.65rem;
  font-weight: 500;
  color: var(--secondary);
}

/* Spread ------------------------------------------------------------ */
.spread {
  position: relative;
  display: grid;
  grid-template-columns: 1fr;
  gap: 40px;
  align-items: start;
}
@media (min-width: 768px) {
  .spread {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    column-gap: 96px;
    row-gap: 0;
  }
  .verso { padding-right: 12px; }
  .recto { padding-left: 12px; }
}
.verso {
  position: relative;
  min-width: 0;
}
.recto {
  position: relative;
  min-width: 0;
  display: flex;
  flex-direction: column;
  /* Anchored to top of the spread row — when the verso prompt is long it
     should not stretch the recto's content; the gutter can grow with the
     verso, but the recto's own action / footer stays close to its content. */
}

/* Vertical gutter — kohaku gradient hairline between verso & recto.
   Mobile reuses it as a horizontal section divider above recto. */
.gutter {
  display: none;
}
@media (min-width: 768px) {
  .gutter {
    display: block;
    position: absolute;
    top: 8px;
    bottom: 8px;
    left: 50%;
    width: 1px;
    background: linear-gradient(
      180deg,
      transparent 0%,
      color-mix(in oklab, var(--secondary) 65%, transparent) 15%,
      color-mix(in oklab, var(--secondary) 65%, transparent) 85%,
      transparent 100%
    );
    pointer-events: none;
  }
}

/* Editorial helpers (mirrors exercise-view-tokens.css) ------------- */
.eyebrow {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.7rem;
  font-weight: 500;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}
.eyebrow-sm {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.2em;
  font-size: 0.62rem;
  font-weight: 500;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
}
.verso-eyebrow {
  margin-bottom: 20px;
}

/* Prompt — Shippori Mincho at editorial scale, with adaptive sizing for
   long sentences so the whole spread fits a typical laptop viewport.
   Default ("lg") is the editorial maximum; "xs" tier keeps prompts of
   80+ Japanese characters from pushing the recto below the fold.       */
.prompt {
  font-family: var(--font-serif);
  font-weight: 400;
  letter-spacing: 0.01em;
  color: var(--foreground);
  margin: 0;
  word-break: auto-phrase;
  overflow-wrap: break-word;
}
.prompt--lg {
  font-size: clamp(1.7rem, 2.1vw + 0.6rem, 2.5rem);
  line-height: 1.8;
  max-width: 20em;
}
.prompt--md {
  font-size: clamp(1.45rem, 1.6vw + 0.5rem, 2rem);
  line-height: 1.7;
  max-width: 22em;
}
.prompt--sm {
  font-size: clamp(1.2rem, 1.1vw + 0.45rem, 1.65rem);
  line-height: 1.6;
  max-width: 24em;
}
.prompt--xs {
  font-size: clamp(1.05rem, 0.7vw + 0.5rem, 1.4rem);
  line-height: 1.55;
  max-width: 28em;
}

/* Hint block — left kohaku rule + italic serif paragraph ----------- */
.hint-block {
  margin-top: 36px;
  padding-left: 22px;
  border-left: 1px solid color-mix(in oklab, var(--secondary) 55%, transparent);
  max-width: 32em;
}
.hint-label {
  color: var(--secondary);
  margin-bottom: 10px;
}
.hint-text {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 1.05rem;
  font-style: italic;
  color: color-mix(in oklab, var(--foreground) 82%, transparent);
  line-height: 1.7;
}

.retry-marker {
  margin-top: 40px;
  display: inline-flex;
  align-items: center;
  gap: 12px;
}
.retry-rule {
  display: inline-block;
  width: 40px;
  height: 1px;
  background: color-mix(in oklab, var(--foreground) 18%, transparent);
}

/* Recto stack ------------------------------------------------------- */
.recto-stack {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.recto-eyebrow {
  margin-bottom: 2px;
}
.recto-eyebrow--primary { color: var(--primary); }
.recto-eyebrow--secondary { color: var(--secondary); }

.recto-headline {
  margin: 0;
  font-family: var(--font-serif);
  font-size: clamp(1.6rem, 2vw + 0.3rem, 2.1rem);
  line-height: 1.4;
  color: var(--foreground);
}
.recto-headline--primary {
  color: var(--primary);
  font-size: clamp(2rem, 2.4vw + 0.6rem, 2.6rem);
  letter-spacing: 0.02em;
  line-height: 1.3;
}
.correct-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.recto-undertag {
  margin: 6px 0 0;
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}
.recto-gloss {
  margin: 0;
  font-family: var(--font-sans);
  font-size: 0.95rem;
  color: color-mix(in oklab, var(--foreground) 72%, transparent);
  line-height: 1.75;
  max-width: 32em;
}

.no-brief-note {
  margin: 0;
  font-family: var(--font-sans);
  font-style: italic;
  font-size: 0.95rem;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  line-height: 1.6;
}
.analyzing-row {
  display: flex;
  align-items: center;
  gap: 12px;
  font-family: var(--font-sans);
  font-style: italic;
  font-size: 0.95rem;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
}
.analyzing-spinner {
  transform: scale(0.75);
  transform-origin: left center;
}
.detailed-error {
  margin-top: 12px;
  font-family: var(--font-sans);
  font-size: 0.875rem;
  color: var(--destructive);
}

/* Action row + footer ---------------------------------------------- */
.action-row {
  display: flex;
  align-items: center;
  gap: 28px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.mcq-action-row { margin-top: 32px; }
.recto-footer {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
  margin-top: 24px;
}

/* Bottom-line input ------------------------------------------------- */
.input-line {
  width: 100%;
  background: transparent;
  border: 0;
  border-bottom: 1px solid var(--input);
  border-radius: 0;
  padding: 0.6rem 0;
  font-family: var(--font-serif);
  font-size: 1.6rem;
  color: var(--foreground);
  outline: none;
  transition: border-color 200ms ease;
}
.input-line::placeholder {
  color: color-mix(in oklab, var(--foreground) 35%, transparent);
  font-style: italic;
}
.input-line:focus {
  border-bottom: 2px solid var(--primary);
  padding-bottom: calc(0.6rem - 1px);
}

/* Footnote list ----------------------------------------------------- */
.footnote-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* Kbd row ----------------------------------------------------------- */
.kbd-row {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
  font-size: 0.78rem;
  font-family: var(--font-sans);
  margin-top: 18px;
}
.kbd-pair {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.kbd-sep { color: color-mix(in oklab, var(--foreground) 20%, transparent); }
.kbd {
  display: inline-flex;
  align-items: center;
  padding: 0.05rem 0.4rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface-container-low);
  font-family: var(--font-sans);
  font-size: 0.72rem;
  color: color-mix(in oklab, var(--foreground) 75%, transparent);
}

/* Page-leaf flip overlay (full spread) ----------------------------- */
@keyframes pageLeafSweep {
  0%   { transform: translateX(100%); opacity: 0; }
  8%   { opacity: 1; }
  92%  { opacity: 1; }
  100% { transform: translateX(-102%); opacity: 0; }
}
.turn-sheet {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    270deg,
    var(--surface-container-low) 0%,
    var(--surface-container) 50%,
    var(--surface-container-high) 100%
  );
  animation: pageLeafSweep 560ms cubic-bezier(.4,.1,.3,1) both;
  pointer-events: none;
  z-index: 30;
  transform-origin: right center;
}

/* Per-section reveal animations ------------------------------------ */
@keyframes page-turn-in {
  0%   { opacity: 0; transform: translateX(18px) rotateY(-6deg); transform-origin: left center; }
  100% { opacity: 1; transform: translateX(0) rotateY(0); }
}
@keyframes ink-wash-in {
  0%   { opacity: 0; filter: blur(3px); transform: translateY(4px); }
  100% { opacity: 1; filter: blur(0); transform: translateY(0); }
}
@keyframes rise-in {
  0%   { opacity: 0; transform: translateY(8px); }
  100% { opacity: 1; transform: translateY(0); }
}
.anim-page-turn { animation: page-turn-in 450ms ease both; }
.anim-ink { animation: ink-wash-in 520ms ease both; }

.rise-enter-active { animation: rise-in 380ms ease both; }
.rise-leave-active { transition: opacity 200ms ease, transform 200ms ease; }
.rise-leave-to { opacity: 0; transform: translateY(-4px); }

@media (prefers-reduced-motion: reduce) {
  .anim-page-turn,
  .anim-ink,
  .turn-sheet,
  .rise-enter-active,
  .rise-leave-active {
    animation: none !important;
    transition: none !important;
  }
}
</style>
