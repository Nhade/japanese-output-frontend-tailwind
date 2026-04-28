<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { useAuthStore } from '../stores/auth'
import { useGrammarStore } from '../stores/grammar'
import { useToastStore } from '../stores/toast'

const { t, locale } = useI18n()
const route = useRoute()
const authStore = useAuthStore()
const grammar = useGrammarStore()
const toast = useToastStore()

const rangeId = computed<string>(() => String(route.params.rangeId))
const userId = computed<string>(() => String(authStore.user_id || ''))

const response = ref('')
const submitting = ref(false)

const exercise = computed(() => grammar.currentExercise)
const result = computed(() => grammar.lastResult)

async function loadNext() {
  response.value = ''
  await grammar.fetchNextExercise(userId.value, rangeId.value, locale.value)
  if (grammar.error) {
    toast.trigger(grammar.error, 'error')
  }
}

async function submit() {
  if (!exercise.value || !response.value.trim()) return
  submitting.value = true
  try {
    await grammar.submitResponse({
      userId: userId.value,
      exerciseId: exercise.value.exercise_id,
      response: response.value.trim(),
      locale: locale.value,
    })
  } catch (e: any) {
    toast.trigger(e?.message || t('grammar.submit_error'), 'error')
  } finally {
    submitting.value = false
  }
}

function scoreColor(score: number): string {
  if (score >= 0.8) return 'positive'
  if (score >= 0.5) return 'neutral'
  return 'negative'
}

function difficultyDots(d: number): string {
  return '●'.repeat(Math.max(0, Math.min(5, d))) + '○'.repeat(Math.max(0, 5 - d))
}

onMounted(loadNext)
</script>

<template>
  <main class="grammar-page">
    <header class="page-header">
      <p class="eyebrow">
        <router-link to="/grammar" class="back-link">← {{ t('grammar.back_to_library') }}</router-link>
      </p>
      <h1>{{ t('grammar.practice_title') }}</h1>
    </header>

    <!-- Loading state -->
    <section v-if="grammar.loading && !exercise" class="card">
      <p class="muted">{{ t('common.loading') }}</p>
    </section>

    <!-- Error state -->
    <section v-else-if="grammar.error && !exercise" class="card">
      <p class="muted">{{ grammar.error }}</p>
      <button class="btn-secondary" @click="loadNext">{{ t('grammar.retry') }}</button>
    </section>

    <!-- Exercise -->
    <section v-else-if="exercise" class="card exercise-card">
      <div class="exercise-meta">
        <span class="pattern-pill">{{ exercise.target_pattern_name }}</span>
        <span class="difficulty" :title="t('grammar.difficulty')">
          {{ difficultyDots(exercise.difficulty) }}
        </span>
        <span v-if="exercise.source === 'fallback_canonical'" class="muted small">
          {{ t('grammar.fallback_note') }}
        </span>
      </div>

      <p class="prompt">{{ exercise.prompt }}</p>

      <textarea
        v-model="response"
        class="answer"
        :placeholder="t('grammar.answer_placeholder')"
        :disabled="submitting || !!result"
        rows="3"
        lang="ja"
      ></textarea>

      <div class="actions">
        <button
          v-if="!result"
          type="button"
          class="btn-primary"
          :disabled="!response.trim() || submitting"
          @click="submit"
        >
          {{ submitting ? t('grammar.submitting') : t('grammar.submit') }}
        </button>
        <button
          v-else
          type="button"
          class="btn-primary"
          :disabled="grammar.loading"
          @click="loadNext"
        >
          {{ t('grammar.next_exercise') }}
        </button>
      </div>

      <!-- Feedback -->
      <div v-if="result" class="feedback" :class="scoreColor(result.score)">
        <div class="feedback-head">
          <span class="score-pill">
            {{ Math.round(result.score * 100) }}
          </span>
          <span class="muted small">
            <strong v-if="result.used_pattern">{{ t('grammar.pattern_used') }}</strong>
            <strong v-else>{{ t('grammar.pattern_missing') }}</strong>
          </span>
          <span v-if="result.detector.matched.length" class="muted small">
            · {{ t('grammar.detector_matched') }}: {{ result.detector.matched.join(', ') }}
          </span>
        </div>
        <p class="feedback-text">{{ result.feedback_text }}</p>
        <div v-if="result.issues.length > 0" class="issues">
          <span v-for="issue in result.issues" :key="issue" class="issue-chip">
            {{ issue }}
          </span>
        </div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.grammar-page {
  max-width: 720px;
  margin: 96px auto 64px;
  padding: 0 24px;
  display: grid;
  gap: 32px;
}

.page-header { display: grid; gap: 8px; }
.eyebrow { margin: 0; }
.back-link {
  font-family: var(--font-sans);
  font-size: 0.72rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  text-decoration: none;
}
.back-link:hover { color: var(--foreground); }
.page-header h1 {
  font-family: var(--font-serif);
  font-size: 2rem;
  margin: 0;
}

.card {
  background: var(--card);
  border: 1px solid color-mix(in oklab, var(--foreground) 10%, transparent);
  border-radius: 12px;
  padding: 28px;
  display: grid;
  gap: 16px;
}
.muted { color: color-mix(in oklab, var(--foreground) 60%, transparent); margin: 0; }
.muted.small { font-size: 0.85rem; }

.exercise-meta {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.pattern-pill {
  font-family: var(--font-serif);
  font-size: 1.1rem;
  padding: 4px 12px;
  background: color-mix(in oklab, var(--secondary) 18%, transparent);
  border-radius: 999px;
  color: var(--foreground);
}
.difficulty {
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
}

.prompt {
  font-family: var(--font-serif);
  font-size: 1.15rem;
  line-height: 1.6;
  margin: 8px 0;
  white-space: pre-wrap;
}

.answer {
  font-family: var(--font-serif);
  font-size: 1.1rem;
  padding: 14px;
  background: var(--background);
  border: 1px solid color-mix(in oklab, var(--foreground) 14%, transparent);
  border-radius: 8px;
  color: var(--foreground);
  resize: vertical;
  min-height: 80px;
}
.answer:focus { outline: none; border-color: var(--secondary); }
.answer:disabled { opacity: 0.7; }

.actions { display: flex; gap: 12px; }

.btn-primary, .btn-secondary {
  font-family: var(--font-sans);
  font-size: 0.78rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  padding: 10px 18px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
}
.btn-primary {
  background: var(--primary);
  color: var(--primary-foreground);
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary {
  background: transparent;
  color: var(--foreground);
  border-color: color-mix(in oklab, var(--foreground) 22%, transparent);
}

.feedback {
  margin-top: 8px;
  padding: 16px;
  border-radius: 8px;
  border-left: 3px solid color-mix(in oklab, var(--foreground) 22%, transparent);
  background: color-mix(in oklab, var(--foreground) 4%, transparent);
  display: grid;
  gap: 10px;
}
.feedback.positive { border-left-color: oklch(0.62 0.13 145); }
.feedback.neutral  { border-left-color: var(--secondary); }
.feedback.negative { border-left-color: oklch(0.55 0.15 28); }

.feedback-head {
  display: flex;
  gap: 12px;
  align-items: baseline;
  flex-wrap: wrap;
}
.score-pill {
  font-family: var(--font-serif);
  font-size: 1.25rem;
  font-weight: 600;
  padding: 2px 12px;
  background: var(--card);
  border: 1px solid color-mix(in oklab, var(--foreground) 16%, transparent);
  border-radius: 999px;
}

.feedback-text {
  font-family: var(--font-serif);
  font-size: 0.98rem;
  line-height: 1.6;
  margin: 0;
}

.issues { display: flex; flex-wrap: wrap; gap: 6px; }
.issue-chip {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 3px 10px;
  border-radius: 999px;
  background: color-mix(in oklab, var(--foreground) 8%, transparent);
  color: color-mix(in oklab, var(--foreground) 80%, transparent);
}
</style>
