<template>
  <main class="min-h-[calc(100vh-4rem)] bg-zinc-950 text-zinc-100 p-6 pt-24">
    <div class="mx-auto max-w-4xl">
      <div class="flex flex-col md:flex-row justify-between items-center mb-6 gap-4">
        <h1 class="text-2xl font-bold">News Reading Practice</h1>
        
        <!-- Filter Controls -->
        <div class="flex gap-2">
          <input 
            type="date" 
            v-model="filterDate" 
            @change="fetchArticles"
            class="bg-zinc-900 border border-zinc-700 rounded px-3 py-1 text-sm text-zinc-200 focus:outline-none focus:border-emerald-500"
          />
          <select 
            v-model="filterCategory" 
            @change="fetchArticles"
            class="bg-zinc-900 border border-zinc-700 rounded px-3 py-1 text-sm text-zinc-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="">All Categories</option>
            <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
          </select>
        </div>
      </div>
      
      <div v-if="loading" class="text-center text-zinc-500">Loading articles...</div>
      
      <div v-else class="grid gap-4">
        <div v-if="articles.length === 0" class="text-center text-zinc-500 py-8">
          No articles found matching your criteria.
        </div>
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
const filterDate = ref('');
const filterCategory = ref('');

// Common categories found in the database
const categories = ['国際', '社会', '気象・災害', '科学・文化', '政治', '経済', '暮らし'];

const formatDate = (ts) => {
  if (!ts) return '';
  return new Date(ts).toLocaleDateString();
};

const fetchArticles = async () => {
  loading.value = true;
  try {
    const params = new URLSearchParams();
    if (filterDate.value) params.append('date', filterDate.value);
    if (filterCategory.value) params.append('category', filterCategory.value);
    
    const query = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/news${query}`);
    articles.value = await res.json();
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  fetchArticles();
});
</script>
