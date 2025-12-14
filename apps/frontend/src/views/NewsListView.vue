<template>
  <main class="min-h-[calc(100vh-4rem)] bg-zinc-950 text-zinc-100 p-6 pt-24">
    <div class="mx-auto max-w-4xl">
      <h1 class="text-2xl font-bold mb-6">News Reading Practice</h1>
      
      <div v-if="loading" class="text-center text-zinc-500">Loading articles...</div>
      
      <div v-else class="grid gap-4">
        <router-link 
          v-for="article in articles" 
          :key="article.article_id"
          :to="`/news/${article.article_id}`"
          class="block p-5 rounded-xl border border-white/10 bg-zinc-900/50 hover:bg-zinc-800 transition"
        >
          <div class="flex justify-between items-start mb-2">
            <span class="text-xs font-mono text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded">
              {{ article.category || 'News' }}
            </span>
            <span class="text-xs text-zinc-500">{{ formatDate(article.publish_timestamp) }}</span>
          </div>
          <h2 class="text-lg font-semibold">{{ article.title }}</h2>
        </router-link>
      </div>
    </div>
  </main>
</template>
<script setup>
import { ref, onMounted } from 'vue';
const articles = ref([]);
const loading = ref(true);
const formatDate = (ts) => {
  if (!ts) return '';
  return new Date(ts).toLocaleDateString();
};
onMounted(async () => {
  try {
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/news`);
    articles.value = await res.json();
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
});
</script>
