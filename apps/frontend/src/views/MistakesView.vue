<template>
  <main class="min-h-[calc(100vh-4rem)] bg-zinc-950 text-zinc-100">
    <div class="mx-auto max-w-5xl px-4 pb-24 pt-10">
      <div class="my-6">
        <h1 class="text-xl font-semibold tracking-wide mb-4">Past Mistakes</h1>

        <!-- Smart Action Card -->
        <button 
          @click="!dailyReview ? generateReview() : (showReviewModal = true)"
          :disabled="isAgentWorking || mistakes.length === 0"
          :class="['group relative flex w-full items-center justify-between rounded-xl border p-4 transition-all shadow-lg active:scale-[0.99]', 
                   dailyReview ? 'bg-indigo-900/30 border-indigo-500/50 hover:bg-indigo-900/40' : 'bg-zinc-900/80 border-white/5 hover:bg-zinc-800 hover:border-indigo-500/30']"
        >
            <div class="flex items-center gap-4">
                <!-- Icon Container -->
                <div class="relative flex h-12 w-12 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400 group-hover:bg-indigo-500/20 transition-colors">
                    <template v-if="isAgentWorking">
                        <div class="h-6 w-6 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent"></div>
                    </template>
                    <template v-else-if="dailyReview">
                        <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                           <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    </template>
                    <template v-else>
                        <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                           <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                        </svg>
                    </template>
                </div>
                
                <div class="text-left">
                    <div class="text-base font-medium text-zinc-200 group-hover:text-white transition-colors">
                        <span v-if="isAgentWorking">{{ agentStatus }}</span>
                        <span v-else-if="dailyReview">Daily Review Ready</span>
                        <span v-else>Generate Daily Review</span>
                    </div>
                    <div class="text-sm text-zinc-500 group-hover:text-zinc-400 transition-colors">
                        <span v-if="isAgentWorking">AI is analyzing your mistakes...</span>
                        <span v-else-if="dailyReview">Click to view your personalized study plan</span>
                        <span v-else>Get personalized advice based on your recent mistakes</span>
                    </div>
                </div>
            </div>

            <!-- Chevron/Action Icon -->
            <div class="text-zinc-600 group-hover:text-indigo-400 transition-all duration-300 transform group-hover:translate-x-1" v-if="!isAgentWorking">
                 <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                </svg>
            </div>
        </button>
      </div>

      <!-- Review Modal -->
      <Modal 
        :show="showReviewModal" 
        title="📅 Daily Review" 
        @close="showReviewModal = false"
      >
        <div v-if="dailyReview" class="prose prose-invert prose-sm max-w-none text-zinc-300">
           <div v-html="md.render(dailyReview)"></div>
        </div>
      </Modal>

      <div v-if="isLoading">Loading...</div>
      <div v-else-if="error">{{ error }}</div>

      <div v-else-if="mistakes.length > 0" class="grid gap-4 md:grid-cols-2">
        <article v-for="mistake in mistakes" :key="mistake.log_id" class="rounded-2xl border border-white/5 bg-zinc-900/60 p-5">
          <p class="text-sm leading-relaxed">{{ mistake.question_sentence }}</p>
          <div class="mt-3 rounded-lg bg-rose-500/10 p-3 text-sm text-rose-300">
            <div class="font-medium">Your Answer:</div>
            <div>{{ mistake.user_answer }}</div>
          </div>
          <div class="mt-2 rounded-lg bg-emerald-500/10 p-3 text-sm text-emerald-300">
            <div class="font-medium">Correct Answer:</div>
            <div class="font-semibold">{{ mistake.correct_answer }}</div>
          </div>

          <!-- AI Feedback -->
          <div v-if="mistake.feedback" class="mt-3 border-t border-white/5 pt-3">
             <div class="flex items-center justify-between mb-1">
                <span class="text-xs font-medium text-indigo-300 uppercase tracking-widest">AI Feedback</span>
                <div class="flex gap-2">
                    <span v-if="mistake.score !== null" class="text-xs bg-indigo-500/20 px-2 py-0.5 rounded text-indigo-200">Score: {{ mistake.score }}</span>
                    <span v-if="mistake.error_type" class="text-xs bg-indigo-500/20 px-2 py-0.5 rounded text-indigo-200 uppercase">{{ mistake.error_type }}</span>
                </div>
             </div>
             <p class="text-sm text-zinc-300">{{ mistake.feedback }}</p>
          </div>
        </article>
      </div>
      
      <p v-else class="mt-10 text-center text-sm text-zinc-400">No mistakes found. 🎉</p>
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
<style scoped>
/* Custom Markdown Styles */
:deep(.prose h1), :deep(.prose h2), :deep(.prose h3) {
  color: #e4e4e7; /* zinc-200 */
  font-weight: 700;
  margin-top: 1.5em;
  margin-bottom: 0.5em;
}
:deep(.prose h1) { font-size: 1.5em; }
:deep(.prose h2) { font-size: 1.25em; }
:deep(.prose h3) { font-size: 1.1em; }

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
  border-left: 4px solid #818cf8; /* indigo-400 */
  background-color: rgba(129, 140, 248, 0.1);
  padding: 0.5em 1em;
  color: #d1d5db;
  font-style: italic;
  margin-bottom: 1em;
  border-top-right-radius: 0.5rem;
  border-bottom-right-radius: 0.5rem;
}
</style>
