<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';

interface TranscriptSegment { start: number; text: string }

interface VideoInfo {
  title?: string;
  channel_name?: string;
  category?: string;
  duration_seconds?: number;
  external_id?: string;
}

interface ClozeExercise {
  exercise_id: string;
  full_sentence: string;
  question_sentence: string;
  correct_answer: string;
  hint_chinese?: string;
  context_timestamp?: number;
  userAnswer: string;
  submitting: boolean;
  submitted: boolean;
  isCorrect: boolean;
  showHint: boolean;
}

interface CompQuestion {
  question: string;
  choices: string[];
  correct_index: number;
  explanation?: string;
  selectedIndex: number | null;
  answered: boolean;
  isCorrect: boolean;
  checking: boolean;
  feedback: string;
}

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const API = import.meta.env.VITE_API_BASE_URL;
const videoId = route.params.id as string;

const loading = ref(true);
const video = ref<{ info: VideoInfo } | null>(null);
const transcript = ref<TranscriptSegment[]>([]);
const exercises = ref<ClozeExercise[]>([]);
const comprehensionQuestions = ref<CompQuestion[]>([]);
const isGenerating = ref(false);
const currentTime = ref(0);
const tab = ref<'cloze' | 'comp'>('cloze');

let player: any = null;
let timeInterval: ReturnType<typeof setInterval> | null = null;

function formatT(seconds?: number): string {
  if (seconds == null) return '0:00';
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${String(rem).padStart(2, '0')}`;
}

function isActiveSegment(start: number, index: number): boolean {
  const nextStart = index + 1 < transcript.value.length
    ? transcript.value[index + 1].start
    : Number.POSITIVE_INFINITY;
  return currentTime.value >= start && currentTime.value < nextStart;
}

const durationSeconds = computed(() => video.value?.info.duration_seconds || 0);
const progressPct = computed(() => {
  if (!durationSeconds.value) return 0;
  return Math.min(100, (currentTime.value / durationSeconds.value) * 100);
});

// --------------------------------------------------------------
//  Player
// --------------------------------------------------------------
function seekTo(seconds: number) {
  if (player?.seekTo) {
    player.seekTo(seconds, true);
  }
}

function initPlayer() {
  if (!video.value?.info.external_id) return;
  if (!(window as any).YT) {
    const tag = document.createElement('script');
    tag.src = 'https://www.youtube.com/iframe_api';
    document.head.appendChild(tag);
    ;(window as any).onYouTubeIframeAPIReady = () => createPlayer();
  } else {
    createPlayer();
  }
}

function createPlayer() {
  player = new (window as any).YT.Player('yt-player', {
    videoId: video.value!.info.external_id,
    width: '100%',
    height: '100%',
    playerVars: { rel: 0, modestbranding: 1, cc_load_policy: 0 },
    events: {
      onReady: () => {
        timeInterval = setInterval(() => {
          if (player?.getCurrentTime) currentTime.value = player.getCurrentTime();
        }, 500);
      },
    },
  });
}

// --------------------------------------------------------------
//  Data fetching
// --------------------------------------------------------------
async function fetchVideo() {
  try {
    const res = await fetch(`${API}/api/videos/${videoId}`);
    if (!res.ok) return;
    const data = await res.json();
    // Normalise to { info, transcript } regardless of server shape.
    const info: VideoInfo = data.info ?? data;
    video.value = { info };
    transcript.value = data.transcript || [];
  } catch (e) {
    console.error(e);
  }
}

async function fetchExercises() {
  try {
    const res = await fetch(`${API}/api/videos/${videoId}/exercises`);
    if (!res.ok) return;
    const data = await res.json();
    exercises.value = (data || []).map((ex: any) => ({
      ...ex,
      userAnswer: '',
      submitting: false,
      submitted: false,
      isCorrect: false,
      showHint: false,
    })) as ClozeExercise[];
  } catch (e) {
    console.error(e);
  }
}

// --------------------------------------------------------------
//  Cloze
// --------------------------------------------------------------
async function submitCloze(ex: ClozeExercise) {
  if (!ex.userAnswer?.trim() || ex.submitting) return;
  ex.submitting = true;
  try {
    const res = await fetch(`${API}/api/videos/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        exercise_id: ex.exercise_id,
        video_id: videoId,
        user_answer: ex.userAnswer.trim(),
        user_id: authStore.user_id,
      }),
    });
    const data = await res.json();
    ex.submitted = true;
    ex.isCorrect = !!data.is_correct;
  } catch (e) {
    console.error(e);
  } finally {
    ex.submitting = false;
  }
}

function resetCloze(ex: ClozeExercise) {
  ex.userAnswer = '';
  ex.submitted = false;
  ex.isCorrect = false;
  ex.showHint = false;
}

// --------------------------------------------------------------
//  Comprehension
// --------------------------------------------------------------
async function generateComprehension() {
  isGenerating.value = true;
  try {
    const res = await fetch(`${API}/api/videos/${videoId}/comprehension`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ num_questions: 5 }),
    });
    const data = await res.json();
    comprehensionQuestions.value = (data.questions || []).map((q: any) => ({
      ...q,
      selectedIndex: null,
      answered: false,
      isCorrect: false,
      checking: false,
      feedback: '',
    })) as CompQuestion[];
  } catch (e) {
    console.error(e);
  } finally {
    isGenerating.value = false;
  }
}

function selectChoice(qi: number, ci: number) {
  const q = comprehensionQuestions.value[qi];
  if (!q.answered) q.selectedIndex = ci;
}

async function checkComprehension(qi: number) {
  const q = comprehensionQuestions.value[qi];
  if (q.selectedIndex == null) return;
  q.checking = true;
  try {
    const res = await fetch(`${API}/api/videos/comprehension/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: q.question,
        choices: q.choices,
        correct_index: q.correct_index,
        user_answer_index: q.selectedIndex,
        transcript_context: transcript.value.map(s => s.text).join(' ').slice(0, 500),
        user_id: authStore.user_id,
        video_id: videoId,
      }),
    });
    const data = await res.json();
    q.answered = true;
    q.isCorrect = !!data.is_correct;
    q.feedback = data.feedback || '';
  } catch (e) {
    console.error(e);
  } finally {
    q.checking = false;
  }
}

// --------------------------------------------------------------
//  Lifecycle
// --------------------------------------------------------------
function goBack() { router.push('/videos'); }

onMounted(async () => {
  await Promise.all([fetchVideo(), fetchExercises()]);
  loading.value = false;
  await nextTick();
  initPlayer();
});

onBeforeUnmount(() => {
  if (timeInterval) clearInterval(timeInterval);
  if (player?.destroy) player.destroy();
});
</script>

<template>
  <main class="study-shell ei-shell-bg text-foreground">
    <div class="vs-page">
      <button class="reader-back" type="button" @click="goBack">
        <span class="arrow">←</span>
        <span>{{ $t('video.back_to_index') }}</span>
      </button>

      <div v-if="loading" class="vs-loading">
        {{ $t('video.loading') }}
      </div>

      <div v-else-if="!video" class="vs-loading">
        {{ $t('video.no_videos') }}
      </div>

      <template v-else>
        <!-- Masthead ------------------------------------------- -->
        <header class="vs-masthead">
          <div class="vs-meta-row">
            <span v-if="video.info.category" class="reader-cat" lang="ja">
              {{ video.info.category }}
            </span>
            <span v-if="video.info.category && video.info.channel_name" class="reader-sep" />
            <span v-if="video.info.channel_name" class="reader-date">
              {{ video.info.channel_name }}
            </span>
            <span v-if="video.info.duration_seconds" class="reader-sep" />
            <span v-if="video.info.duration_seconds" class="reader-readtime">
              {{ formatT(video.info.duration_seconds) }}
            </span>
          </div>
          <h1 class="vs-title" lang="ja">{{ video.info.title }}</h1>
        </header>

        <!-- Libretto grid ------------------------------------- -->
        <div class="vs-libretto-grid">
          <!-- Transcript (scrolls) --------------------------- -->
          <div class="vs-libretto-script">
            <div class="vs-script-head">
              <span class="eyebrow-sm eyebrow-kohaku">{{ $t('video.transcript') }}</span>
              <span v-if="transcript.length" class="vs-script-sub">
                {{ $t('video.transcript_lines', { n: transcript.length }) }}
              </span>
            </div>
            <ol v-if="transcript.length" class="vs-transcript">
              <li
                v-for="(seg, i) in transcript"
                :key="i"
                class="vs-line"
                :class="{ 'is-active': isActiveSegment(seg.start, i) }"
                @click="seekTo(seg.start)"
              >
                <span class="vs-line-time">{{ formatT(seg.start) }}</span>
                <span class="vs-line-text" lang="ja">{{ seg.text }}</span>
              </li>
            </ol>
            <p v-else class="vs-no-transcript">
              {{ $t('video.no_transcript') }}
            </p>
          </div>

          <!-- Sticky dock: player + exercises ---------------- -->
          <aside class="vs-libretto-side">
            <div class="vs-dock">
              <div class="yt-wrap">
                <div id="yt-player" class="yt-iframe" />
              </div>
              <div class="vs-dock-meta">
                <div class="vs-sticky-pos">
                  <span>{{ formatT(currentTime) }}</span>
                  <span class="vs-sticky-sep">/</span>
                  <span>{{ formatT(durationSeconds) }}</span>
                </div>
                <div class="vs-sticky-bar" aria-hidden="true">
                  <div class="vs-sticky-bar-fill" :style="{ width: `${progressPct}%` }" />
                </div>
              </div>

              <div class="vs-deck">
                <div class="vs-tabs-tight">
                  <button
                    type="button"
                    class="vs-tab"
                    :class="{ 'is-active': tab === 'cloze' }"
                    @click="tab = 'cloze'"
                  >
                    <span class="vs-tab-num">§1</span>
                    <span class="vs-tab-label">{{ $t('video.cloze') }}</span>
                    <span class="vs-tab-count">{{ exercises.length }}</span>
                  </button>
                  <button
                    type="button"
                    class="vs-tab"
                    :class="{ 'is-active': tab === 'comp' }"
                    @click="tab = 'comp'"
                  >
                    <span class="vs-tab-num">§2</span>
                    <span class="vs-tab-label">{{ $t('video.comprehension_tab') }}</span>
                    <span class="vs-tab-count">{{ comprehensionQuestions.length }}</span>
                  </button>
                </div>

                <!-- Cloze body --------------------------- -->
                <div v-if="tab === 'cloze'" class="vs-tab-body">
                  <p v-if="exercises.length === 0" class="vs-empty">
                    {{ $t('video.no_exercises') }}
                  </p>
                  <ol v-else class="vs-cloze">
                    <li
                      v-for="(ex, i) in exercises"
                      :key="ex.exercise_id"
                      class="vs-cloze-item"
                    >
                      <div class="vs-cloze-head">
                        <span class="vs-q-num">Q{{ i + 1 }}.</span>
                        <span class="vs-cloze-prompt" lang="ja">
                          {{ ex.question_sentence }}
                        </span>
                        <button
                          v-if="ex.context_timestamp != null"
                          class="vs-cloze-ts"
                          type="button"
                          :title="$t('video.jump_to_moment')"
                          @click="seekTo(ex.context_timestamp!)"
                        >
                          {{ $t('video.at_timestamp', { t: formatT(ex.context_timestamp) }) }}
                        </button>
                      </div>

                      <template v-if="!ex.submitted">
                        <div class="vs-cloze-row">
                          <input
                            v-model="ex.userAnswer"
                            class="vs-cloze-input"
                            lang="ja"
                            :placeholder="$t('video.answer_placeholder')"
                            @keydown.enter="submitCloze(ex)"
                          />
                          <button
                            v-if="ex.hint_chinese"
                            type="button"
                            class="vs-cloze-hint-btn"
                            @click="ex.showHint = !ex.showHint"
                          >
                            {{ ex.showHint ? $t('video.hide_hint') : $t('video.hint') }}
                          </button>
                          <button
                            type="button"
                            class="vs-check"
                            :disabled="!ex.userAnswer?.trim() || ex.submitting"
                            @click="submitCloze(ex)"
                          >
                            {{ $t('video.check') }}
                          </button>
                        </div>
                        <div v-if="ex.showHint && ex.hint_chinese" class="vs-cloze-hint">
                          <span class="vs-cloze-hint-label">{{ $t('video.hint') }}</span>
                          {{ ex.hint_chinese }}
                        </div>
                      </template>

                      <div
                        v-else
                        class="vs-verdict"
                        :class="{ 'is-ok': ex.isCorrect, 'is-nope': !ex.isCorrect }"
                      >
                        <div class="vs-verdict-head">
                          <span class="vs-verdict-mark">{{ ex.isCorrect ? '✓' : '×' }}</span>
                          <span class="vs-verdict-label">
                            <template v-if="ex.isCorrect">{{ $t('video.marked_correct') }}</template>
                            <template v-else>
                              {{ $t('video.you_wrote') }}
                              <span class="vs-verdict-user" lang="ja">{{ ex.userAnswer }}</span>
                            </template>
                          </span>
                        </div>
                        <div class="vs-verdict-answer">
                          <span class="vs-verdict-ans-label">{{ $t('video.answer') }}</span>
                          <span lang="ja">{{ ex.correct_answer }}</span>
                        </div>
                        <button
                          type="button"
                          class="vs-cloze-retry"
                          @click="resetCloze(ex)"
                        >
                          {{ $t('video.try_again') }}
                        </button>
                      </div>
                    </li>
                  </ol>
                </div>

                <!-- Comprehension body ------------------- -->
                <div v-if="tab === 'comp'" class="vs-tab-body">
                  <p class="vs-block-dek">{{ $t('video.comprehension_intro') }}</p>

                  <button
                    v-if="comprehensionQuestions.length === 0"
                    type="button"
                    class="vs-cta-generate"
                    :disabled="isGenerating"
                    @click="generateComprehension"
                  >
                    <template v-if="isGenerating">{{ $t('video.generating') }}</template>
                    <template v-else>{{ $t('video.generate_questions') }}</template>
                  </button>

                  <ol v-if="comprehensionQuestions.length" class="vs-quiz">
                    <li
                      v-for="(q, qi) in comprehensionQuestions"
                      :key="qi"
                      class="vs-q"
                    >
                      <div class="vs-q-head">
                        <span class="vs-q-num">Q{{ qi + 1 }}.</span>
                        <span class="vs-q-prompt" lang="ja">{{ q.question }}</span>
                      </div>
                      <ol class="vs-q-choices">
                        <li v-for="(choice, ci) in q.choices" :key="ci">
                          <button
                            type="button"
                            class="vs-choice"
                            :class="{
                              'is-selected': !q.answered && q.selectedIndex === ci,
                              'is-correct': q.answered && ci === q.correct_index,
                              'is-wrong': q.answered && ci === q.selectedIndex && !q.isCorrect,
                              'is-dim': q.answered && ci !== q.correct_index && ci !== q.selectedIndex,
                            }"
                            :disabled="q.answered"
                            @click="selectChoice(qi, ci)"
                          >
                            <span class="vs-choice-letter">{{ String.fromCharCode(65 + ci) }}</span>
                            <span class="vs-choice-text" lang="ja">{{ choice }}</span>
                          </button>
                        </li>
                      </ol>
                      <button
                        v-if="!q.answered && q.selectedIndex !== null"
                        type="button"
                        class="vs-check"
                        :disabled="q.checking"
                        @click="checkComprehension(qi)"
                      >
                        {{ $t('video.check') }}
                      </button>
                      <div
                        v-if="q.answered"
                        class="vs-verdict"
                        :class="{ 'is-ok': q.isCorrect, 'is-nope': !q.isCorrect }"
                      >
                        <div class="vs-verdict-head">
                          <span class="vs-verdict-mark">{{ q.isCorrect ? '✓' : '×' }}</span>
                          <span class="vs-verdict-label">
                            {{ q.isCorrect ? $t('video.marked_correct') : $t('video.marked_incorrect') }}
                          </span>
                        </div>
                        <p v-if="q.feedback" class="vs-verdict-note">{{ q.feedback }}</p>
                        <p v-else-if="q.explanation" class="vs-verdict-note" lang="ja">
                          {{ q.explanation }}
                        </p>
                      </div>
                    </li>
                  </ol>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </template>
    </div>
  </main>
</template>

<style scoped>
.study-shell {
  min-height: calc(100vh - var(--app-chrome-h));
  /* paper gradient comes from the global .ei-shell-bg utility */
}
.vs-page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 32px 48px 120px;
  width: 100%;
  position: relative;
}
@media (max-width: 720px) { .vs-page { padding: 24px 20px 96px; } }

/* Back + loading ---------------------------------------------- */
/* .reader-back is global — see styles/editorial.css. */
.reader-back { margin-bottom: 28px; }
.vs-loading {
  padding: 96px 0;
  text-align: center;
  font-family: var(--font-serif);
  font-style: italic;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}

/* Masthead ---------------------------------------------------- */
.vs-masthead {
  padding-bottom: 28px;
  margin-bottom: 32px;
  border-bottom: 1px solid var(--foreground);
}
.vs-meta-row {
  display: flex;
  align-items: baseline;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.reader-cat {
  font-size: 0.78rem;
  letter-spacing: 0.16em;
  color: var(--secondary);
  font-weight: 600;
}
.reader-sep {
  width: 20px;
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
.vs-title {
  font-family: var(--font-serif);
  font-weight: 500;
  font-size: clamp(1.8rem, 2.6vw + 0.4rem, 2.6rem);
  line-height: 1.35;
  margin: 0;
  max-width: 24em;
  word-break: auto-phrase;
}

/* Eyebrow helpers -------------------------------------------- */
/* .eyebrow-sm / .eyebrow-kohaku are global — see styles/editorial.css. */

/* Libretto grid ---------------------------------------------- */
.vs-libretto-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 48px;
  align-items: start;
}
@media (max-width: 1024px) {
  .vs-libretto-grid { grid-template-columns: 1fr; }
  .vs-dock { position: static !important; }
}

/* Transcript (scrolls) --------------------------------------- */
.vs-libretto-script {
  min-width: 0;
}
.vs-script-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 12px;
  margin-bottom: 10px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
}
.vs-script-sub {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.85rem;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}
.vs-transcript {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
}
.vs-line {
  display: grid;
  grid-template-columns: 60px 1fr;
  gap: 18px;
  padding: 12px 10px 12px 12px;
  cursor: pointer;
  border-left: 2px solid transparent;
  transition: background 160ms ease, border-color 160ms ease;
  align-items: baseline;
}
.vs-line:hover { background: var(--surface-container-low); }
.vs-line.is-active {
  background: var(--surface-container-low);
  border-left-color: var(--primary);
}
.vs-line.is-active .vs-line-text { color: var(--primary); }
.vs-line-time {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.82rem;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
  font-variant-numeric: tabular-nums;
}
.vs-line-text {
  font-family: var(--font-serif);
  font-size: 1.1rem;
  line-height: 1.8;
  color: var(--foreground);
  word-break: auto-phrase;
  transition: color 180ms ease;
}
.vs-no-transcript {
  padding: 32px 12px;
  font-family: var(--font-serif);
  font-style: italic;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}

/* Player dock ------------------------------------------------ */
.vs-libretto-side { min-width: 0; }
.vs-dock {
  position: sticky;
  top: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.yt-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 3px;
  overflow: hidden;
  background: #000;
  box-shadow: 0 12px 32px color-mix(in oklab, var(--foreground) 12%, transparent);
}
.yt-iframe {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border: 0;
}
:deep(#yt-player iframe) {
  width: 100% !important;
  height: 100% !important;
}
.vs-dock-meta {
  padding: 6px 2px 10px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
}
.vs-sticky-pos {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-family: var(--font-serif);
  color: color-mix(in oklab, var(--foreground) 65%, transparent);
  font-size: 0.88rem;
  margin-bottom: 8px;
  font-variant-numeric: tabular-nums;
}
.vs-sticky-sep { color: color-mix(in oklab, var(--foreground) 40%, transparent); font-style: italic; }
.vs-sticky-bar {
  height: 2px;
  background: color-mix(in oklab, var(--foreground) 9%, transparent);
  overflow: hidden;
}
.vs-sticky-bar-fill {
  height: 100%;
  background: var(--secondary);
  transition: width 240ms ease;
}

/* Exercise deck --------------------------------------------- */
.vs-deck { display: flex; flex-direction: column; gap: 6px; }

.vs-tabs-tight {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: var(--surface-container-low);
  border-radius: 3px;
  margin-bottom: 6px;
}
.vs-tabs-tight .vs-tab {
  flex: 1;
  display: inline-flex;
  align-items: baseline;
  justify-content: center;
  gap: 8px;
  padding: 10px 12px;
  border: none;
  background: transparent;
  border-radius: 2px;
  cursor: pointer;
  font-family: var(--font-serif);
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  transition: background 180ms ease, color 180ms ease;
}
.vs-tabs-tight .vs-tab:hover { color: var(--foreground); }
.vs-tabs-tight .vs-tab.is-active {
  background: var(--background);
  color: var(--foreground);
  box-shadow: 0 1px 2px color-mix(in oklab, var(--foreground) 6%, transparent);
}
.vs-tab-num {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.85rem;
  color: var(--secondary);
}
.vs-tabs-tight .vs-tab.is-active .vs-tab-num { color: var(--primary); }
.vs-tab-label {
  font-size: 0.92rem;
  font-weight: 500;
}
.vs-tab-count {
  font-family: var(--font-sans);
  font-size: 0.62rem;
  letter-spacing: 0.12em;
  color: color-mix(in oklab, var(--foreground) 45%, transparent);
}
.vs-tab-body { padding: 8px 2px 4px; }

.vs-empty,
.vs-block-dek {
  margin: 0 0 14px;
  font-family: var(--font-serif);
  font-style: italic;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  font-size: 0.92rem;
  line-height: 1.6;
}

/* Cloze ----------------------------------------------------- */
.vs-cloze {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.vs-cloze-item {
  padding-bottom: 20px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
}
.vs-cloze-item:last-child { border-bottom: none; padding-bottom: 0; }
.vs-cloze-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.vs-q-num {
  font-family: var(--font-serif);
  font-style: italic;
  color: var(--secondary);
  font-size: 0.95rem;
}
.vs-cloze-prompt {
  flex: 1;
  min-width: 0;
  font-family: var(--font-serif);
  font-size: 1.05rem;
  line-height: 1.65;
  color: var(--foreground);
  word-break: auto-phrase;
}
.vs-cloze-ts {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.78rem;
  color: var(--secondary);
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  border-bottom: 1px dotted var(--secondary);
}
.vs-cloze-ts:hover { color: var(--primary); border-bottom-color: var(--primary); }
.vs-cloze-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 10px;
  align-items: center;
}
.vs-cloze-input {
  font-family: var(--font-serif);
  font-size: 1rem;
  padding: 10px 12px;
  background: var(--background);
  border: 1px solid var(--input);
  border-radius: 3px;
  color: var(--foreground);
  outline: none;
  transition: border-color 180ms ease;
}
.vs-cloze-input:focus { border-color: var(--primary); }
.vs-cloze-hint-btn {
  font-family: var(--font-sans);
  font-size: 0.62rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  background: none;
  border: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
  padding: 8px 12px;
  border-radius: 3px;
  cursor: pointer;
  transition: color 160ms ease, border-color 160ms ease;
}
.vs-cloze-hint-btn:hover { color: var(--secondary); border-color: var(--secondary); }

.vs-check {
  font-family: var(--font-sans);
  font-size: 0.72rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--primary);
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px 0;
  border-bottom: 1px solid var(--secondary);
  transition: color 180ms ease, opacity 180ms ease;
}
.vs-check:disabled { opacity: 0.4; cursor: not-allowed; }

.vs-cloze-hint {
  margin-top: 10px;
  padding: 10px 14px;
  background: var(--surface-container-low);
  border-left: 2px solid var(--secondary);
  border-radius: 0 3px 3px 0;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.92rem;
  color: color-mix(in oklab, var(--foreground) 75%, transparent);
}
.vs-cloze-hint-label {
  font-family: var(--font-sans);
  font-style: normal;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  font-size: 0.6rem;
  color: var(--secondary);
  margin-right: 8px;
  font-weight: 500;
}

.vs-cloze-retry {
  margin-top: 10px;
  font-family: var(--font-sans);
  font-size: 0.62rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  background: none;
  border: none;
  padding: 4px 0;
  cursor: pointer;
  border-bottom: 1px dotted color-mix(in oklab, var(--foreground) 15%, transparent);
}
.vs-cloze-retry:hover { color: var(--primary); border-bottom-color: var(--primary); }

/* Verdict --------------------------------------------------- */
.vs-verdict {
  margin-top: 14px;
  padding: 14px 16px;
  border-radius: 3px;
  background: var(--surface-container-low);
  border-left: 2px solid var(--primary);
}
.vs-verdict.is-nope { border-left-color: var(--tertiary); }
.vs-verdict-head {
  display: flex;
  gap: 10px;
  align-items: baseline;
  margin-bottom: 6px;
}
.vs-verdict-mark {
  font-family: var(--font-serif);
  font-size: 1.15rem;
  color: var(--primary);
}
.vs-verdict.is-nope .vs-verdict-mark { color: var(--tertiary); }
.vs-verdict-label {
  font-family: var(--font-sans);
  font-size: 0.62rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
}
.vs-verdict-user {
  font-family: var(--font-serif);
  font-style: italic;
  color: var(--tertiary);
  text-transform: none;
  letter-spacing: 0.01em;
  text-decoration: line-through;
  text-decoration-thickness: 1px;
}
.vs-verdict-answer {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding-top: 8px;
  margin-top: 8px;
  border-top: 1px dotted color-mix(in oklab, var(--foreground) 9%, transparent);
  font-family: var(--font-serif);
  font-size: 1rem;
  color: var(--foreground);
}
.vs-verdict-ans-label {
  font-family: var(--font-sans);
  font-size: 0.6rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--secondary);
  font-weight: 500;
}
.vs-verdict-note {
  margin: 8px 0 0;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.9rem;
  line-height: 1.65;
  color: color-mix(in oklab, var(--foreground) 75%, transparent);
}

/* Comprehension CTA + quiz ---------------------------------- */
.vs-cta-generate {
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
  transition: background 180ms ease, opacity 180ms ease;
}
.vs-cta-generate:hover:not(:disabled) { background: var(--primary-container); }
.vs-cta-generate:disabled { opacity: 0.5; cursor: not-allowed; }

.vs-quiz {
  list-style: none;
  padding: 0;
  margin: 14px 0 0;
  display: flex;
  flex-direction: column;
  gap: 28px;
}
.vs-q {
  padding: 0 0 22px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
}
.vs-q:last-child { border-bottom: none; }
.vs-q-head {
  display: flex;
  gap: 12px;
  align-items: baseline;
  margin-bottom: 16px;
}
.vs-q-prompt {
  font-family: var(--font-serif);
  font-size: 1.05rem;
  line-height: 1.6;
  color: var(--foreground);
  word-break: auto-phrase;
}
.vs-q-choices {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.vs-choice {
  width: 100%;
  display: grid;
  grid-template-columns: 28px 1fr;
  align-items: baseline;
  gap: 14px;
  text-align: left;
  padding: 12px 14px;
  background: transparent;
  border: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
  border-radius: 3px;
  cursor: pointer;
  font-family: var(--font-serif);
  color: var(--foreground);
  transition: background 160ms ease, border-color 160ms ease;
}
.vs-choice:hover:not(:disabled) { background: var(--surface-container-low); }
.vs-choice:disabled { cursor: default; }
.vs-choice-letter {
  font-family: var(--font-serif);
  font-style: italic;
  color: var(--secondary);
  font-size: 0.95rem;
}
.vs-choice-text { font-size: 1rem; line-height: 1.5; }
.vs-choice.is-selected { border-color: var(--primary); background: var(--surface-container-low); }
.vs-choice.is-correct {
  border-color: var(--primary);
  background: color-mix(in oklab, var(--primary) 6%, transparent);
}
.vs-choice.is-correct .vs-choice-letter { color: var(--primary); }
.vs-choice.is-wrong {
  border-color: var(--tertiary);
  background: color-mix(in oklab, var(--tertiary) 5%, transparent);
}
.vs-choice.is-wrong .vs-choice-letter { color: var(--tertiary); }
.vs-choice.is-dim { opacity: 0.5; }
</style>
