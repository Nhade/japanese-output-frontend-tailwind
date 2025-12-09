<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue';
import LoadingSpinner from '../components/LoadingSpinner.vue';
import { useAuthStore } from '../stores/auth';

// Reactive state for the view
const exercise = ref(null); // Holds the current exercise data
const feedback = ref(null); // Holds the feedback from the server after submission
const isLoading = ref(true); // Controls the loading spinner visibility
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
async function handleAnswerSubmit() {
  if (!exercise.value || !userAnswer.value.trim()) return;

  try {
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
    feedback.value = await response.json();
    await nextTick();
    nextQuestionButton.value?.focus();
  } catch (error) {
    console.error('Failed to submit answer:', error);
  }
}

async function revealHint() {
  showHint.value = true;
  await nextTick();
  answerInput.value?.focus();
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
                class="flex items-center gap-2 rounded-xl bg-emerald-500/15 px-3 py-2 text-emerald-300"
              >
                <span>✅ Correct!</span>
                <span class="text-emerald-200/80">{{ feedback.correct_answer }}</span>
              </div>
              <div
                v-else
                class="space-y-2 rounded-xl bg-rose-500/10 px-3 py-2 text-rose-300"
              >
                <div>❌ Not quite.</div>
                <div class="text-rose-200/90">Correct answer: <span class="font-semibold">{{ feedback.correct_answer }}</span></div>
              </div>
              <div class="mt-4">
                <button ref="nextQuestionButton" @click="fetchNewExercise" class="rounded-xl bg-white/10 px-4 py-2 text-sm text-white hover:bg-white/20">Next Question →</button>
              </div>
            </div>
          </transition>
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
</style>
