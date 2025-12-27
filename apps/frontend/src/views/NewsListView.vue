<template>
  <main class="min-h-[calc(100vh-4rem)] p-6 pt-24 text-zinc-900 dark:text-zinc-100">
    <div class="mx-auto max-w-4xl">
      <div class="flex flex-col md:flex-row justify-between items-center mb-6 gap-4">
        <h1 class="text-2xl font-bold">{{ $t('news.title') }}</h1>

        <!-- Filter Controls -->
        <div class="flex gap-2">
          <input type="date" v-model="filterDate" @change="fetchArticles"
            class="bg-white border-zinc-200 text-zinc-900 dark:bg-zinc-900/50 dark:border-white/10 dark:text-zinc-200 border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors shadow-sm" />
          <BaseSelect v-model="filterCategory" :options="categoryOptions" @update:model-value="fetchArticles"
            class="w-40" placeholder="All Categories" />
        </div>
      </div>

      <div v-if="loading" class="text-center text-zinc-600 dark:text-zinc-500">{{ $t('news.loading_articles') }}</div>

      <div v-else class="grid gap-4">
        <div v-if="articles.length === 0" class="text-center text-zinc-600 dark:text-zinc-500 py-8">
          {{ $t('news.no_articles') }}
        </div>
        <router-link v-for="article in articles" :key="article.article_id" :to="`/news/${article.article_id}`"
          class="block p-5 rounded-xl border transition bg-white border-zinc-200 hover:bg-zinc-50 dark:border-white/10 dark:bg-zinc-900/50 dark:hover:bg-zinc-800">
          <div class="flex justify-between items-start mb-2">
            <span
              class="text-xs font-mono px-2 py-1 rounded text-emerald-700 bg-emerald-50 dark:text-emerald-400 dark:bg-emerald-400/10">
              {{ article.category || 'News' }}
            </span>
            <span class="text-xs text-zinc-600 dark:text-zinc-500">{{ formatDate(article.publish_timestamp) }}</span>
          </div>
          <h2 class="text-lg font-semibold">{{ article.title }}</h2>
        </router-link>
      </div>
    </div>
  </main>
</template>
<script setup>
import { ref, onMounted } from 'vue';
import BaseSelect from '../components/BaseSelect.vue';

const articles = ref([]);
const loading = ref(true);
const filterDate = ref('');
const filterCategory = ref('');

// Common categories found in the database
const categories = ['国際', '社会', '気象・災害', '科学・文化', '政治', '経済', '暮らし'];

const categoryOptions = [
  { value: '', label: 'All Categories' },
  ...categories.map(c => ({ value: c, label: c }))
];

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
