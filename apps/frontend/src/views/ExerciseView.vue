<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue';
import LoadingSpinner from '../components/LoadingSpinner.vue';
import Modal from '../components/Modal.vue';
import { useAuthStore } from '../stores/auth';
import { useToastStore } from '../stores/toast';
import MarkdownIt from 'markdown-it';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true
});

// Reactive state for the view
const exercise = ref(null); // Holds the current exercise data
const feedback = ref(null); // Holds the feedback from the server after submission
const detailedFeedback = ref(null); // Holds the detailed explanation
const showDetailModal = ref(false);
const detailedError = ref(null);
const isLoading = ref(true); // Controls the loading spinner visibility
const isLoadingDetailed = ref(false); // Controls the detailed feedback spinner
const auth = useAuthStore();
const toastStore = useToastStore();
const userAnswer = ref('');
const showHint = ref(false);
const nextQuestionButton = ref(null);
const answerInput = ref(null);

// --- API Interaction ---

// Fetches a new random exercise from the backend
async function fetchNewExercise() {
  isLoading.value = true;
  feedback.value = null; // Reset feedback for the new question
  detailedFeedback.value = null; // Reset detailed feedback
  showDetailModal.value = false;
  detailedError.value = null;
  exercise.value = null; // Clear old exercise
  userAnswer.value = '';
  showHint.value = false;

  try {
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/exercise/random`, {
      headers: {
        'Content-Type': 'application/json',
      }
    });
    if (!response.ok) throw new Error('Network response was not ok');
    exercise.value = await response.json();
  } catch (error) {
    console.error('Failed to fetch exercise:', error);
  } finally {
    isLoading.value = false;
    await nextTick();
    answerInput.value?.focus();
  }
}

// Submits the user's answer to the backend
const isExplaining = ref(false); // New state for AI loading

async function handleAnswerSubmit() {
  if (!exercise.value || !userAnswer.value.trim()) return;

  try {
    // Step 1: Submit for immediate correctness check
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/exercise/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        exercise_id: exercise.value.exercise_id,
        user_answer: userAnswer.value.trim(),
        user_id: auth.user_id,
      }),
    });
    if (!response.ok) throw new Error('Submission failed');

    // Immediate feedback
    const result = await response.json();
    feedback.value = result;

    // Toast for Focus Progress
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
          target: diff.target
        });
        toastStore.trigger(msg, 'info');
      }
    }

    await nextTick();
    nextQuestionButton.value?.focus();

    // Step 2: If we have a log_id AND it's incorrect, fetch AI explanation (async)
    if (result.log_id && !result.is_correct) {

      // Capture the exercise ID to prevent race conditions
      const currentExerciseId = exercise.value.exercise_id;

      isExplaining.value = true;
      try {
        const explainResponse = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/exercise/explain`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ log_id: result.log_id }),
        });

        if (explainResponse.ok) {
          const explanation = await explainResponse.json();

          // Guard: Only update UI if the user is still on the same exercise
          if (exercise.value && exercise.value.exercise_id === currentExerciseId) {
            // Merge explanation into feedback object
            feedback.value = { ...feedback.value, ...explanation };

            // Check for safety violation
            if (explanation.feedback && explanation.feedback.includes("Safety violation")) {
              toastStore.trigger(t('chat.safety_violation'), 'error');
            }
          }
        }
      } catch (err) {
        console.error('AI explanation failed:', err);
      } finally {
        // Only turn off loading if we are still on the same exercise
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
  answerInput.value?.focus();
  answerInput.value?.focus();
}

async function fetchDetailedFeedback() {
  if (!feedback.value || !feedback.value.log_id) return;

  isLoadingDetailed.value = true;
  detailedError.value = null;
  try {
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/exercise/explain-detailed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ log_id: feedback.value.log_id }),
    });

    if (response.ok) {
      const data = await response.json();

      // Check for safety violation
      if (data.detailed_feedback && data.detailed_feedback.includes("Safety violation")) {
        toastStore.trigger(t('chat.safety_violation'), 'error');
        // Don't show modal if safety violation
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


function handleKeydown(event) {
  if (event.altKey && event.key === 'h') {
    event.preventDefault();
    revealHint();
  }
}

// Fetch the first exercise when the component is mounted

onMounted(() => {
  fetchNewExercise();
  window.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
  <main class="min-h-[calc(100vh-4rem)] h-full flex flex-col justify-center text-zinc-900 dark:text-zinc-100">
    <div class="mx-auto max-w-3xl px-4 pb-24 pt-10">
      <LoadingSpinner v-if="isLoading" />

      <div v-else-if="exercise">
        <!-- Question Card -->
        <transition name="slide-up" mode="out-in">
          <section :key="exercise.exercise_id"
            class="rounded-xl border p-8 shadow-sm transition-all bg-white border-zinc-200 shadow-zinc-200/50 dark:bg-zinc-900/60 dark:border-white/10 dark:shadow-none">
            <h1 class="text-2xl font-medium leading-relaxed tracking-wide mb-6 text-zinc-900 dark:text-zinc-100">
              <span lang="ja">{{ exercise.question_sentence }}</span>
            </h1>

            <!-- Hint -->
            <div v-if="showHint"
              class="mb-6 rounded-lg border p-4 text-sm shadow-inner border-indigo-200 bg-indigo-50 text-indigo-800 dark:border-indigo-500/20 dark:bg-indigo-500/10 dark:text-indigo-200">
              <span class="mr-2 select-none">💡</span>
              {{ exercise.hint_chinese }}
            </div>

            <!-- Input -->
            <form @submit.prevent="handleAnswerSubmit" class="space-y-4" v-if="!feedback">
              <label class="block text-sm font-medium text-zinc-700 dark:text-zinc-300" for="answer">{{
                $t('exercise.your_answer') }}</label>
              <input id="answer" ref="answerInput" v-model.trim="userAnswer"
                class="w-full rounded-xl px-5 py-4 text-lg outline-none transition-all shadow-inner border bg-white text-zinc-900 border-zinc-200 placeholder-zinc-400 focus:ring-2 focus:ring-emerald-500/40 dark:bg-zinc-900 dark:text-zinc-100 dark:border-white/15 dark:placeholder-zinc-500 dark:focus:ring-emerald-500/50"
                :placeholder="$t('exercise.type_here')" autocomplete="off" />
              <div class="flex items-center gap-3 pt-2">
                <button type="submit"
                  class="rounded-xl px-6 py-2.5 font-medium text-white shadow-lg transition-all active:scale-95 bg-gradient-to-br from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 shadow-emerald-200/40 dark:from-emerald-500 dark:to-emerald-600 dark:hover:from-emerald-400 dark:hover:to-emerald-500 dark:shadow-emerald-900/20 focus:outline-none focus:ring-2 focus:ring-emerald-500/50">{{
                    $t('exercise.check_answer') }}</button>
                <button type="button" @click="revealHint"
                  class="rounded-xl px-4 py-2.5 text-sm border transition-colors bg-zinc-50 border-zinc-200 text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:bg-white/5 dark:border-white/10 dark:text-zinc-300 dark:hover:bg-white/10 dark:hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/40">{{
                    $t('exercise.show_hint') }}</button>
              </div>
            </form>

            <!-- Feedback -->
            <transition name="fade">
              <div v-if="feedback" class="mt-6 space-y-6 border-t border-zinc-200/60 pt-6 dark:border-white/10">
                <div v-if="feedback.is_correct"
                  class="flex flex-col items-stretch gap-3 rounded-xl border px-5 py-4 bg-emerald-50 border-emerald-200 text-emerald-900 dark:bg-emerald-500/10 dark:border-emerald-400/25 dark:text-zinc-100">
                  <div class="flex items-center gap-2">
                    <span class="text-lg">✅</span>
                    <div>
                      <span class="font-semibold text-emerald-800 dark:text-emerald-200">{{ $t('exercise.correct')
                      }}</span>
                      <span class="ml-2 text-emerald-700 dark:text-emerald-200" lang="ja">{{ feedback.correct_answer
                      }}</span>
                    </div>
                  </div>

                  <!-- Correct Feedback Section -->
                  <div class="mt-2 pt-3 border-t border-emerald-200 dark:border-emerald-400/25">
                    <div class="flex justify-between items-start mb-1">
                      <span
                        class="text-xs font-medium text-emerald-800 dark:text-emerald-300 uppercase tracking-wider">{{
                          $t('exercise.feedback_label') }}</span>
                      <span
                        class="text-xs bg-emerald-100 text-emerald-900 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/20 px-2 py-0.5 rounded border font-mono">{{
                          $t('exercise.score') }}
                        100</span>
                    </div>
                    <p class="text-sm text-emerald-900 dark:text-emerald-100/90 leading-relaxed">完全正確！🎉</p>
                  </div>
                </div>
                <div v-else
                  class="rounded-xl border px-5 py-4 bg-rose-50 border-rose-200 text-rose-900 dark:bg-rose-500/10 dark:border-rose-400/25 dark:text-zinc-100">
                  <div class="flex items-center gap-2 mb-2">
                    <span class="text-lg">❌</span>
                    <span class="font-medium text-rose-700 dark:text-rose-200">{{ $t('exercise.incorrect') }}</span>
                  </div>
                  <div class="text-rose-800 pl-7 dark:text-zinc-200">{{ $t('exercise.correct_answer_label') }} <span
                      class="font-semibold text-rose-950 dark:text-zinc-100" lang="ja">{{ feedback.correct_answer
                      }}</span></div>

                  <!-- AI Feedback Section -->
                  <div v-if="feedback.feedback" class="mt-4 pt-3 border-t border-rose-200 pl-1 dark:border-rose-400/25">
                    <div class="flex justify-between items-start mb-2">
                      <span class="text-xs font-medium text-rose-800 dark:text-rose-300 uppercase tracking-wider">{{
                        $t('exercise.ai_analysis') }}</span>
                      <div class="flex gap-2">
                        <span v-if="feedback.score"
                          class="text-xs bg-rose-100 text-rose-900 border-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-500/15 px-2 py-0.5 rounded border font-mono">{{
                            $t('exercise.score') }}
                          {{ feedback.score }}</span>
                        <span v-if="feedback.error_type && feedback.error_type !== 'none'"
                          class="text-xs bg-rose-100 text-rose-900 border-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-500/15 px-2 py-0.5 rounded border uppercase tracking-wider">
                          {{ $t('error_type.' + feedback.error_type, feedback.error_type) }}
                        </span>
                        <span v-if="feedback.retry_count && feedback.retry_count > 0"
                          class="text-xs bg-amber-100 text-amber-900 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/15 px-2 py-0.5 rounded border uppercase tracking-wider">
                          Retried: {{ feedback.retry_count }}
                        </span>
                      </div>
                    </div>
                    <p class="text-sm text-rose-900 dark:text-zinc-200 leading-relaxed">{{ feedback.feedback }}</p>
                  </div>

                  <!-- Detailed Feedback Section -->
                  <div v-if="feedback.feedback && !feedback.is_correct"
                    class="mt-4 pt-4 border-t border-rose-200 dark:border-rose-400/25">

                    <!-- Smart Action Card -->
                    <div class="mt-2">
                      <button @click="!detailedFeedback ? fetchDetailedFeedback() : (showDetailModal = true)"
                        :disabled="isLoadingDetailed"
                        class="group relative flex w-full items-center justify-between rounded-xl border p-4 transition-all active:scale-[0.99] bg-white border-zinc-200 hover:bg-zinc-50 hover:border-indigo-500/30 dark:bg-white/5 dark:border-white/10 dark:hover:bg-white/7 dark:hover:border-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/30">
                        <div class="flex items-center gap-4">
                          <!-- Icon Container -->
                          <div
                            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-600 border border-indigo-200 dark:bg-indigo-400/10 dark:text-indigo-300 dark:border-indigo-400/20 transition-colors">
                            <template v-if="isLoadingDetailed">
                              <div
                                class="h-5 w-5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent">
                              </div>
                            </template>
                            <template v-else-if="detailedFeedback">
                              <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                              </svg>
                            </template>
                            <template v-else>
                              <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M13 10V3L4 14h7v7l9-11h-7z" />
                              </svg>
                            </template>
                          </div>

                          <div class="text-left">
                            <div
                              class="text-sm font-medium text-zinc-800 group-hover:text-black dark:text-zinc-200 dark:group-hover:text-white transition-colors">
                              <span v-if="isLoadingDetailed">{{ $t('exercise.analyzing') }}</span>
                              <span v-else-if="detailedFeedback">{{ $t('exercise.view_detailed') }}</span>
                              <span v-else>{{ $t('exercise.explain_answer') }}</span>
                            </div>
                            <div
                              class="text-xs text-zinc-600 group-hover:text-zinc-700 dark:text-zinc-400 dark:group-hover:text-zinc-300 transition-colors">
                              <span v-if="isLoadingDetailed">{{ $t('exercise.ai_generating_breakdown') }}</span>
                              <span v-else-if="detailedFeedback">{{ $t('exercise.review_grammar') }}</span>
                              <span v-else>{{ $t('exercise.get_detailed_breakdown') }}</span>
                            </div>
                          </div>
                        </div>

                        <!-- Chevron/Action Icon -->
                        <div
                          class="text-zinc-500 dark:text-zinc-400 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-all duration-300 group-hover:translate-x-1">
                          <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                          </svg>
                        </div>
                      </button>
                    </div>



                    <div v-if="detailedError" class="mt-2 text-xs text-rose-400 bg-rose-500/10 p-2 rounded">
                      {{ detailedError }}
                    </div>
                  </div>
                  <!-- Loading State -->
                  <div v-else-if="isExplaining"
                    class="mt-4 pt-3 border-t border-rose-200 dark:border-white/10 flex items-center justify-center gap-2 text-rose-700 dark:text-zinc-300 text-sm">
                    <div class="scale-75 origin-center">
                      <LoadingSpinner />
                    </div>
                    <span>{{ $t('exercise.analyzing') }}</span>
                  </div>

                </div>
                <div class="mt-8 flex justify-end">
                  <button ref="nextQuestionButton" @click="fetchNewExercise"
                    class="group flex items-center gap-2 rounded-xl py-2.5 px-5 text-sm font-medium transition-all border border-zinc-200 bg-zinc-50 hover:bg-zinc-100 text-zinc-900 dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/7 dark:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400/40 dark:focus-visible:ring-white/20">
                    {{ $t('exercise.next_question') }}
                    <span class="group-hover:translate-x-0.5 transition-transform">→</span>
                  </button>
                </div>
              </div>
            </transition>

            <!-- Detailed Feedback Modal -->
            <Modal :show="showDetailModal" :title="$t('exercise.detailed_modal_title')"
              @close="showDetailModal = false">
              <div v-if="detailedFeedback" class="prose prose-sm max-w-none prose-zinc dark:prose-invert">
                <div v-html="md.render(detailedFeedback)"></div>
              </div>
            </Modal>

          </section>
        </transition>

        <!-- Footer helper -->
        <i18n-t keypath="exercise.footer_helper" tag="p"
          class="mt-6 text-center text-xs text-zinc-500 dark:text-zinc-400">
          <template #enter>
            <kbd
              class="rounded px-1 bg-zinc-200 text-zinc-700 dark:bg-white/5 dark:border dark:border-white/10 dark:text-zinc-300">Enter</kbd>
          </template>
          <template #alt>
            <kbd
              class="rounded px-1 bg-zinc-200 text-zinc-700 dark:bg-white/5 dark:border dark:border-white/10 dark:text-zinc-300">Alt</kbd>
          </template>
          <template #h>
            <kbd
              class="rounded px-1 bg-zinc-200 text-zinc-700 dark:bg-white/5 dark:border dark:border-white/10 dark:text-zinc-300">H</kbd>
          </template>
        </i18n-t>
      </div>

      <div v-else class="error-message">
        <p>{{ $t('auth.error_generic') }}</p>
      </div>
    </div>
  </main>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity .2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease-out;
}

.slide-up-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.slide-up-leave-to {
  opacity: 0;
  transform: translateY(-20px);
}
</style>
