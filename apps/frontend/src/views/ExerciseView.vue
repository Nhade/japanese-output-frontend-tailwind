<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue';
import LoadingSpinner from '../components/LoadingSpinner.vue';
import Modal from '../components/Modal.vue';
import { useAuthStore } from '../stores/auth';
import MarkdownIt from 'markdown-it';

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
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/exercise/random`, {headers: {
      'Content-Type': 'application/json',
    }});
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
  <main class="min-h-[calc(100vh-4rem)] h-full flex flex-col justify-center bg-zinc-950 text-zinc-100">
    <div class="mx-auto max-w-3xl px-4 pb-24 pt-10">
      <LoadingSpinner v-if="isLoading" />

      <div v-else-if="exercise">
        <!-- Question Card -->
        <transition name="slide-up" mode="out-in">
          <section
            :key="exercise.exercise_id"
            class="rounded-xl bg-gradient-to-b from-zinc-900 to-zinc-950 shadow-[0_10px_30px_rgba(0,0,0,0.4)] border border-white/5 p-8"
          >
            <h1 class="text-2xl font-medium leading-relaxed tracking-wide text-zinc-100 font-serif mb-6">
              {{ exercise.question_sentence }}
            </h1>

            <!-- Hint -->
            <div v-if="showHint" class="mb-6 rounded-lg border border-indigo-500/20 bg-indigo-500/10 p-4 text-sm text-indigo-200 shadow-inner">
              <span class="mr-2 select-none">💡</span>
              {{ exercise.hint_chinese }}
            </div>

            <!-- Input -->
            <form @submit.prevent="handleAnswerSubmit" class="space-y-4" v-if="!feedback">
              <label class="block text-sm font-medium text-zinc-400" for="answer">Your Answer</label>
              <input
                id="answer"
                ref="answerInput"
                v-model.trim="userAnswer"
                class="w-full rounded-xl border border-white/10 bg-zinc-900/50 px-5 py-4 text-lg text-white placeholder-zinc-600 outline-none focus:ring-2 focus:ring-emerald-500/50 transition-all shadow-inner"
                placeholder="Type here..."
                autocomplete="off"
              />
              <div class="flex items-center gap-3 pt-2">
                <button type="submit" class="rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 px-6 py-2.5 font-medium text-white hover:from-emerald-400 hover:to-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 shadow-lg shadow-emerald-900/20 transition-all active:scale-95">Check Answer</button>
                <button type="button" @click="revealHint" class="rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-zinc-300 hover:bg-white/10 hover:text-white transition-colors">Show Hint</button>
              </div>
            </form>

            <!-- Feedback -->
            <transition name="fade">
              <div v-if="feedback" class="mt-6 space-y-6">
                <div
                  v-if="feedback.is_correct"
                  class="flex flex-col items-stretch gap-3 rounded-xl bg-gradient-to-r from-emerald-950/70 to-emerald-900/40 border border-emerald-400/20 px-5 py-4"
                >
                  <div class="flex items-center gap-2">
                    <span class="text-lg">✅</span>
                    <div>
                      <span class="font-semibold text-emerald-200">Correct!</span>
                      <span class="ml-2 text-emerald-200/80">{{ feedback.correct_answer }}</span>
                    </div>
                  </div>
                  
                  <!-- Correct Feedback Section -->
                  <div class="mt-2 pt-3 border-t border-emerald-500/20">
                      <div class="flex justify-between items-start mb-1">
                          <span class="text-xs font-medium text-emerald-300 uppercase tracking-wider">Feedback</span>
                          <span class="text-xs bg-emerald-500/10 px-2 py-0.5 rounded text-emerald-300 border border-emerald-500/20 font-mono">Score: 100</span>
                      </div>
                      <p class="text-sm text-emerald-100/90 leading-relaxed">完全正確！🎉</p>
                  </div>
                </div>
                <div
                  v-else
                  class="rounded-xl bg-gradient-to-r from-rose-950/70 to-rose-900/40 border border-rose-400/20 px-5 py-4 text-rose-200"
                >
                  <div class="flex items-center gap-2 mb-2">
                     <span class="text-lg">❌</span>
                     <span class="font-medium">Not quite.</span>
                  </div>
                  <div class="text-rose-200/90 pl-7">Correct answer: <span class="font-semibold text-rose-100">{{ feedback.correct_answer }}</span></div>
                  
                  <!-- AI Feedback Section -->
                  <div v-if="feedback.feedback" class="mt-4 pt-3 border-t border-rose-500/20 pl-1">
                      <div class="flex justify-between items-start mb-2">
                          <span class="text-xs font-medium text-rose-300 uppercase tracking-wider">AI Analysis</span>
                          <div class="flex gap-2">
                              <span v-if="feedback.score" class="text-xs bg-rose-500/10 px-2 py-0.5 rounded text-rose-300 border border-rose-500/20 font-mono">Score: {{ feedback.score }}</span>
                              <span v-if="feedback.error_type && feedback.error_type !== 'none'" class="text-xs bg-rose-500/10 px-2 py-0.5 rounded text-rose-300 border border-rose-500/20 uppercase tracking-wider">
                                  {{ feedback.error_type }}
                              </span>
                          </div>
                      </div>
                      <p class="text-sm text-rose-100/90 leading-relaxed">{{ feedback.feedback }}</p>
                  </div>

                  <!-- Detailed Feedback Section -->
                  <div v-if="feedback.feedback && !feedback.is_correct" class="mt-4 pt-4 border-t border-rose-500/20">
                      
                      <!-- Smart Action Card -->
                      <div class="mt-2">
                          <button 
                              @click="!detailedFeedback ? fetchDetailedFeedback() : (showDetailModal = true)"
                              :disabled="isLoadingDetailed"
                              class="group relative flex w-full items-center justify-between rounded-xl border border-white/5 bg-zinc-900/40 hover:bg-zinc-900/60 p-4 transition-all hover:border-indigo-500/30 active:scale-[0.99] shadow-sm"
                          >
                              <div class="flex items-center gap-4">
                                  <!-- Icon Container -->
                                  <div class="relative flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400 group-hover:bg-indigo-500/20 transition-colors border border-indigo-500/20">
                                      <template v-if="isLoadingDetailed">
                                          <div class="h-5 w-5 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent"></div>
                                      </template>
                                      <template v-else-if="detailedFeedback">
                                          <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                                          </svg>
                                      </template>
                                      <template v-else>
                                          <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                                          </svg>
                                      </template>
                                  </div>
                                  
                                  <div class="text-left">
                                      <div class="text-sm font-medium text-zinc-200 group-hover:text-white transition-colors">
                                          <span v-if="isLoadingDetailed">Analyzing details...</span>
                                          <span v-else-if="detailedFeedback">View Detailed Explanation</span>
                                          <span v-else>Explain this answer</span>
                                      </div>
                                      <div class="text-xs text-zinc-500 group-hover:text-zinc-400 transition-colors">
                                          <span v-if="isLoadingDetailed">AI is generating a breakdown</span>
                                          <span v-else-if="detailedFeedback">Review grammar and examples</span>
                                          <span v-else>Get detailed grammar breakdown with AI</span>
                                      </div>
                                  </div>
                              </div>

                              <!-- Chevron/Action Icon -->
                              <div class="text-zinc-600 group-hover:text-indigo-400 transition-all duration-300 group-hover:translate-x-1">
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
                  <div v-else-if="isExplaining" class="mt-4 pt-3 border-t border-rose-500/20 flex items-center justify-center gap-2 text-rose-200/50 text-sm">
                     <div class="scale-75 origin-center"><LoadingSpinner /></div>
                     <span>Analyzing details...</span>
                  </div>

                </div>
                <div class="mt-8 flex justify-end">
                  <button ref="nextQuestionButton" @click="fetchNewExercise" class="group flex items-center gap-2 rounded-xl bg-white/5 py-2.5 px-5 text-sm font-medium text-white hover:bg-white/10 transition-all border border-white/5 hover:border-white/10">
                      Next Question 
                      <span class="group-hover:translate-x-0.5 transition-transform">→</span>
                  </button>
                </div>
              </div>
            </transition>
            
            <!-- Detailed Feedback Modal -->
            <Modal 
              :show="showDetailModal" 
              title="Detailed AI Explanation" 
              @close="showDetailModal = false"
            >
              <div v-if="detailedFeedback" class="prose prose-invert prose-sm max-w-none text-zinc-300">
                <div v-html="md.render(detailedFeedback)"></div>
              </div>
            </Modal>

          </section>
        </transition>

        <!-- Footer helper -->
        <p class="mt-6 text-center text-xs text-zinc-500">Press <kbd class="rounded bg-zinc-800 px-1">Enter</kbd> to check. Press <kbd class="rounded bg-zinc-800 px-1">Alt</kbd>+<kbd class="rounded bg-zinc-800 px-1">H</kbd> for hint.</p>
      </div>

      <div v-else class="error-message">
        <p>An error occurred. Please try again later.</p>
      </div>
    </div>
  </main>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity .2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

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


/* Custom Markdown Styles */
:deep(.prose h1), :deep(.prose h2), :deep(.prose h3) {
  color: #e4e4e7; /* zinc-200 */
  font-weight: 700;
  margin-top: 1.5em;
  margin-bottom: 0.5em;
}
:deep(.prose p) {
  margin-bottom: 1em;
  line-height: 1.75;
}
:deep(.prose ul) {
  list-style-type: disc;
  padding-left: 1.5em;
  margin-bottom: 1em;
}
:deep(.prose ol) {
  list-style-type: decimal;
  padding-left: 1.5em;
  margin-bottom: 1em;
}
:deep(.prose li) {
  margin-bottom: 0.25em;
}
:deep(.prose strong) {
  color: #a7f3d0; /* emerald-200 */
  font-weight: 600;
}
:deep(.prose blockquote) {
  border-left: 4px solid #34d399;
  padding-left: 1em;
  color: #d1d5db;
  font-style: italic;
  margin-bottom: 1em;
}
:deep(.prose table) {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1em;
}
:deep(.prose th), :deep(.prose td) {
  border: 1px solid #3f3f46; /* zinc-700 */
  padding: 0.5em;
  text-align: left;
}
:deep(.prose th) {
  background-color: #27272a; /* zinc-800 */
  font-weight: 600;
}
</style>
