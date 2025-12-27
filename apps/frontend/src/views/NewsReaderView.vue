<template>
  <main class="min-h-[calc(100vh-4rem)] pb-20 pt-24 text-zinc-900 dark:text-zinc-100">
    <div class="mx-auto max-w-3xl px-4">
      
      <router-link to="/news" class="inline-flex items-center text-sm mb-6 text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white">
        ← Back to list
      </router-link>

      <div v-if="loading" class="text-center py-10">Loading article...</div>
      
      <article v-else-if="article">
        <header class="mb-8 border-b pb-6 border-zinc-200 dark:border-white/10">
          <h1 class="text-2xl font-bold leading-relaxed mb-4">{{ article.info.title }}</h1>
          <div class="flex gap-4 text-sm text-zinc-600 dark:text-zinc-500">
            <span>{{ article.info.category }}</span>
            <span>{{ new Date(article.info.date).toLocaleString() }}</span>
          </div>
        </header>

        <div class="space-y-8">
          <div 
            v-for="(para, index) in article.paragraphs" 
            :key="index"
            class="group relative rounded-lg p-3 transition duration-300 hover:bg-zinc-100 dark:hover:bg-white/5"
          >
            <p class="text-lg leading-8 tracking-wide text-zinc-800 dark:text-zinc-200">
              {{ para.text }}
            </p>

            <div class="mt-3 flex items-center gap-4 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
              <button 
                @click="playAudio(para.text)" 
                class="flex items-center gap-1.5 text-xs font-medium disabled:opacity-50 text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300"
              >
                <span v-if="isPlaying && currentPlayingText === para.text">⏹️ Stop</span>
                <span v-else>▶️ Listen</span>
              </button>
              
              <button 
                @click="toggleTranslation(index)" 
                class="flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
              >
                文 Translate
              </button>
            </div>

            <div v-if="para.showTranslation" class="mt-3 pl-3 border-l-2 border-blue-500/30">
                <p v-if="para.loadingTranslation" class="text-sm text-zinc-500 animate-pulse">Translating...</p>
                <p v-else class="text-base text-zinc-600 dark:text-zinc-400">{{ para.translation }}</p>
            </div>
          </div>
        </div>
      </article>
      
      <div v-else class="text-center py-10 text-red-400">
          Article not found or failed to load.
      </div>

    </div>
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const article = ref(null);
const loading = ref(true);
const isPlaying = ref(false);
const currentPlayingText = ref('');
const currentAudio = ref(null);

// Fetch Article
onMounted(async () => {
  try {
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/news/${route.params.id}`);
    if (!res.ok) throw new Error('Failed to fetch article');
    article.value = await res.json();
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
});

// Translation Logic
const toggleTranslation = async (index) => {
  const para = article.value.paragraphs[index];
  
  // If already shown, just toggle off
  if (para.showTranslation) {
    para.showTranslation = false;
    return;
  }

  // Show immediately
  para.showTranslation = true;

  // If no translation cached, fetch it
  if (!para.translation) {
    para.loadingTranslation = true;
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: para.text })
      });
      const data = await res.json();
      para.translation = data.translated_text;
    } catch (e) {
      para.translation = "Translation failed.";
      console.error(e);
    } finally {
      para.loadingTranslation = false;
    }
  }
};

// TTS Logic
const playAudio = async (text) => {
  if (isPlaying.value) {
      if (currentAudio.value) {
          currentAudio.value.pause();
          currentAudio.value = null;
      }
      
      const wasPlayingSameText = currentPlayingText.value === text;
      
      isPlaying.value = false;
      currentPlayingText.value = '';

      if (wasPlayingSameText) {
          return;
      }
  }
  
  isPlaying.value = true;
  currentPlayingText.value = text;

  try {
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });

    if (!res.ok) throw new Error("TTS Failed");

    const blob = await res.blob();
    const audioUrl = URL.createObjectURL(blob);
    const audio = new Audio(audioUrl);
    currentAudio.value = audio;
    
    audio.onended = () => {
      isPlaying.value = false;
      currentPlayingText.value = '';
      currentAudio.value = null;
      URL.revokeObjectURL(audioUrl); // Cleanup memory
    };
    
    await audio.play();
  } catch (e) {
    console.error(e);
    isPlaying.value = false;
    currentPlayingText.value = '';
    currentAudio.value = null;
    alert("Unable to play audio.");
  }
};
</script>
