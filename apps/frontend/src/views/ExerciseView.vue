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
            // (or if we want to be clean, we can always turn it off, but consistency matters)
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
        <section
          class="rounded-2xl border border-white/5 bg-zinc-900/60 p-6 shadow-xl shadow-black/30"
        >
          <h1 class="text-xl leading-relaxed tracking-wide">
            {{ exercise.question_sentence }}
          </h1>

          <!-- Hint -->
          <div v-if="showHint" class="mt-4 rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-zinc-300">
            <span class="mr-2 select-none">💡</span>
            {{ exercise.hint_chinese }}
          </div>

          <!-- Input -->
          <form @submit.prevent="handleAnswerSubmit" class="mt-6 space-y-3" v-if="!feedback">
            <label class="block text-sm text-zinc-300" for="answer">Your Answer</label>
            <input
              id="answer"
              ref="answerInput"
              v-model.trim="userAnswer"
              class="w-full rounded-xl border border-white/10 bg-zinc-800 px-4 py-3 text-base text-white placeholder-zinc-500 outline-none focus:ring-2 focus:ring-emerald-400"
              placeholder="Type here"
              autocomplete="off"
            />
            <div class="flex items-center gap-3">
              <button type="submit" class="rounded-xl bg-emerald-500 px-4 py-2 font-medium text-zinc-900 hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-400">Check</button>
              <button type="button" @click="revealHint" class="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-zinc-200 hover:bg-white/10">Show Hint</button>
            </div>
          </form>

          <!-- Feedback -->
          <transition name="fade">
            <div v-if="feedback" class="mt-4">
              <div
                v-if="feedback.is_correct"
                class="flex flex-col items-stretch gap-2 rounded-xl bg-emerald-500/15 px-3 py-2 text-emerald-300"
              >
                <div>
                  <span class="font-bold">✅ Correct!</span>
                  <span class="ml-2 text-emerald-200/80">{{ feedback.correct_answer }}</span>
                </div>
                
                <!-- Correct Feedback Section -->
                <div class="mt-2 pt-2 border-t border-emerald-500/20">
                    <div class="flex justify-between items-start">
                        <span class="text-sm font-medium text-emerald-200">Feedback:</span>
                        <span class="text-xs bg-emerald-500/20 px-2 py-0.5 rounded text-emerald-100">Score: 100</span>
                    </div>
                    <p class="text-sm mt-1 text-emerald-100/90">完全正確！🎉</p>
                </div>
              </div>
              <div
                v-else
                class="space-y-2 rounded-xl bg-rose-500/10 px-3 py-2 text-rose-300"
              >
                <div>❌ Not quite.</div>
                <div class="text-rose-200/90">Correct answer: <span class="font-semibold">{{ feedback.correct_answer }}</span></div>
                
                <!-- AI Feedback Section -->
                <div v-if="feedback.feedback" class="mt-2 pt-2 border-t border-rose-500/20">
                    <div class="flex justify-between items-start">
                        <span class="text-sm font-medium text-rose-200">AI Feedback:</span>
                        <span v-if="feedback.score" class="text-xs bg-rose-500/20 px-2 py-0.5 rounded text-rose-100">Score: {{ feedback.score }}</span>
                    </div>
                    <p class="text-sm mt-1 text-rose-100/90">{{ feedback.feedback }}</p>
                    <div v-if="feedback.error_type && feedback.error_type !== 'none'" class="mt-1 text-xs text-rose-400 uppercase tracking-wider">
                        Type: {{ feedback.error_type }}
                    </div>
                </div>

                <!-- Detailed Feedback Section -->
                <div v-if="feedback.feedback && !feedback.is_correct" class="mt-4 pt-2 border-t border-rose-500/20">
                    
                    <div v-if="!detailedFeedback && !isLoadingDetailed">
                         <button 
                            @click="fetchDetailedFeedback"
                            class="text-xs flex items-center gap-1 text-rose-300 hover:text-rose-100 transition-colors underline decoration-rose-500/30 underline-offset-2"
                        >
                            <span>Need more explanation?</span>
                         </button>
                    </div>
                    <div v-else-if="detailedFeedback">
                         <button 
                            @click="showDetailModal = true"
                            class="text-xs flex items-center gap-1 text-emerald-300 hover:text-emerald-100 transition-colors underline decoration-emerald-500/30 underline-offset-2"
                        >
                            <span>View detailed explanation</span>
                         </button>
                    </div>

                    <div v-if="isLoadingDetailed" class="flex items-center gap-2 text-rose-200/50 text-xs mt-2">
                         <div class="scale-50 origin-left"><LoadingSpinner /></div>
                         <span>Generating detailed explanation...</span>
                    </div>


                    <div v-if="detailedError" class="mt-2 text-xs text-rose-400 bg-rose-500/10 p-2 rounded">
                        {{ detailedError }}
                    </div>
                </div>
                <!-- Loading State -->
                <div v-else-if="isExplaining" class="mt-2 pt-2 border-t border-rose-500/20 flex items-center justify-center gap-2 text-rose-200/50 text-sm">
                   <div class="scale-50 origin-center -ml-2"><LoadingSpinner /></div>
                   <span>Analyzing details...</span>
                </div>

              </div>
              <div class="mt-4">
                <button ref="nextQuestionButton" @click="fetchNewExercise" class="rounded-xl bg-white/10 px-4 py-2 text-sm text-white hover:bg-white/20">Next Question →</button>
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

/* Custom Markdown Styles (since we don't have @tailwindcss/typography installed yet, or just to be safe) */
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
