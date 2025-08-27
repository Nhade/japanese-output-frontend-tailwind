<template>
  <main class="min-h-[calc(100vh-4rem)] bg-zinc-950 text-zinc-100">
    <div class="mx-auto max-w-5xl px-4 pb-24 pt-10">
      <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 class="text-xl font-semibold tracking-wide">Past Mistakes</h1>
      </div>

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
        </article>
      </div>
      
      <p v-else class="mt-10 text-center text-sm text-zinc-400">No mistakes found. 🎉</p>
    </div>
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '../stores/auth';

const mistakes = ref([]);
const isLoading = ref(true);
const error = ref('');
const auth = useAuthStore();

onMounted(async () => {
  if (auth.user_id) {
    try {
      const response = await fetch(`/api/mistakes/${auth.user_id}`);
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
