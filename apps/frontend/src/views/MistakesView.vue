<template>
  <main class="min-h-[calc(100vh-4rem)] text-zinc-900 dark:text-zinc-100">
    <div class="mx-auto max-w-5xl px-4 pb-24 pt-10">
      <div class="my-6">
        <h1 class="text-xl font-semibold tracking-wide mb-4">{{ $t('mistakes.title') }}</h1>

        <!-- Smart Action Card -->
        <button @click="!dailyReview ? generateReview() : (showReviewModal = true)"
          :disabled="isAgentWorking || mistakes.length === 0"
          :class="['group relative flex w-full items-center justify-between rounded-xl border p-4 transition-all shadow-lg active:scale-[0.99]',
            dailyReview ? 'bg-indigo-50 border-indigo-200 hover:bg-indigo-100 dark:bg-indigo-900/30 dark:border-indigo-500/50 dark:hover:bg-indigo-900/40' : 'bg-white border-zinc-200 hover:bg-zinc-50 hover:border-indigo-500/30 dark:bg-zinc-900/80 dark:border-white/5 dark:hover:bg-zinc-800']">
          <div class="flex items-center gap-4">
            <!-- Icon Container -->
            <div
              class="relative flex h-12 w-12 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400 group-hover:bg-indigo-100 dark:group-hover:bg-indigo-500/20 transition-colors">
              <template v-if="isAgentWorking">
                <div class="h-6 w-6 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent"></div>
              </template>
              <template v-else-if="dailyReview">
                <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </template>
              <template v-else>
                <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                </svg>
              </template>
            </div>

            <div class="text-left">
              <div
                class="text-base font-medium text-zinc-900 dark:text-zinc-200 group-hover:text-black dark:group-hover:text-white transition-colors">
                <span v-if="isAgentWorking">{{ agentStatus }}</span>
                <span v-else-if="dailyReview">{{ $t('mistakes.review_ready') }}</span>
                <span v-else>{{ $t('mistakes.generate_review') }}</span>
              </div>
              <div
                class="text-sm text-zinc-600 group-hover:text-zinc-800 dark:text-zinc-500 dark:group-hover:text-zinc-400 transition-colors">
                <span v-if="isAgentWorking">{{ $t('mistakes.analyzing') }}</span>
                <span v-else-if="dailyReview">{{ $t('mistakes.view_review') }}</span>
                <span v-else>{{ $t('mistakes.get_advice') }}</span>
              </div>
            </div>
          </div>

          <!-- Chevron/Action Icon -->
          <div
            class="text-zinc-600 dark:text-zinc-600 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-all duration-300 transform group-hover:translate-x-1"
            v-if="!isAgentWorking">
            <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </button>
      </div>

      <!-- Review Modal -->
      <Modal :show="showReviewModal" :title="`📅 ${$t('mistakes.generate_review')}`" @close="showReviewModal = false">
        <div v-if="dailyReview" class="prose prose-sm max-w-none prose-zinc dark:prose-invert">
          <div v-html="md.render(dailyReview)"></div>
        </div>
      </Modal>

      <div v-if="isLoading">{{ $t('common.loading') }}</div>
      <div v-else-if="error">{{ error }}</div>

      <div v-else-if="mistakes.length > 0" class="grid gap-4 md:grid-cols-2">
        <article v-for="mistake in mistakes" :key="mistake.log_id"
          class="rounded-2xl border p-5 bg-white border-zinc-200 dark:bg-zinc-900/60 dark:border-white/5">
          <p class="text-sm leading-relaxed"><span lang="ja">{{ mistake.question_sentence }}</span></p>
          <div class="mt-3 rounded-lg p-3 text-sm bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">
            <div class="font-medium">{{ $t('mistakes.your_answer') }}</div>
            <div><span lang="ja">{{ mistake.user_answer }}</span></div>
          </div>
          <div
            class="mt-2 rounded-lg p-3 text-sm bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
            <div class="font-medium">{{ $t('mistakes.correct_answer') }}</div>
            <div class="font-semibold"><span lang="ja">{{ mistake.correct_answer }}</span></div>
          </div>

          <!-- AI Feedback -->
          <div v-if="mistake.feedback" class="mt-3 border-t pt-3 border-zinc-200 dark:border-white/5">
            <div class="flex items-center justify-between mb-1">
              <span class="text-xs font-medium uppercase tracking-widest text-indigo-700 dark:text-indigo-300">{{
                $t('mistakes.ai_feedback') }}</span>
              <div class="flex gap-2">
                <span v-if="mistake.score !== null"
                  class="text-xs px-2 py-0.5 rounded bg-indigo-50 text-indigo-800 dark:bg-indigo-500/20 dark:text-indigo-200">{{
                    $t('mistakes.score') }}
                  {{ mistake.score }}</span>
                <span v-if="mistake.error_type"
                  class="text-xs px-2 py-0.5 rounded uppercase bg-indigo-50 text-indigo-800 dark:bg-indigo-500/20 dark:text-indigo-200">{{
                    $t('error_type.' + mistake.error_type, mistake.error_type) }}</span>
              </div>
            </div>
            <p class="text-sm text-zinc-700 dark:text-zinc-300">{{ mistake.feedback }}</p>
          </div>
        </article>
      </div>

      <p v-else class="mt-10 text-center text-sm text-zinc-500 dark:text-zinc-400">{{ $t('mistakes.no_mistakes') }}</p>
    </div>
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '../stores/auth';
import Modal from '../components/Modal.vue';
import MarkdownIt from 'markdown-it';

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true
});

const mistakes = ref([]);
const isLoading = ref(true);
const error = ref('');
const auth = useAuthStore();
const dailyReview = ref('');
const isAgentWorking = ref(false);
const agentStatus = ref('');
const showReviewModal = ref(false);

const simulateAgentThinking = () => {
  const steps = [
    'Analyzing your mistakes...',
    'Identifying weak points...',
    'Drafting study plan...',
    'Polishing content...'
  ];
  let stepIndex = 0;
  agentStatus.value = steps[0];

  const interval = setInterval(() => {
    stepIndex = (stepIndex + 1) % steps.length;
    if (isAgentWorking.value) {
      agentStatus.value = steps[stepIndex];
    } else {
      clearInterval(interval);
    }
  }, 2000);
};

const generateReview = async () => {
  if (!auth.user_id) return;

  isAgentWorking.value = true;
  dailyReview.value = '';
  simulateAgentThinking();

  try {
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/agent/daily_review/${auth.user_id}`);
    const data = await res.json();

    if (res.ok) {
      dailyReview.value = data.review;
      showReviewModal.value = true;
    } else {
      // In case of error we might want to show it in a different way or alert
      console.error("Agent error:", data.error);
    }
  } catch (e) {
    console.error(e);
  } finally {
    isAgentWorking.value = false;
  }
};

onMounted(async () => {
  if (auth.user_id) {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/mistakes/${auth.user_id}`);
      if (response.ok) {
        mistakes.value = await response.json();
      } else {
        const data = await response.json();
        error.value = data.error || 'Failed to load mistakes.';
      }
    } catch (err) {
      error.value = 'An error occurred. Please try again.';
    } finally {
      isLoading.value = false;
    }
  } else {
    error.value = 'Please login to see your mistakes.';
    isLoading.value = false;
  }
});
</script>
<style scoped></style>
