<template>
  <main class="min-h-[calc(100vh-4rem)] p-6 pt-24 text-zinc-900 dark:text-zinc-100">
    <div class="mx-auto max-w-5xl">
      <div class="flex flex-col md:flex-row justify-between items-center mb-6 gap-4">
        <h1 class="text-2xl font-bold">{{ $t('video.title') }}</h1>
        <BaseSelect v-model="filterCategory" :options="categoryOptions" @update:model-value="fetchVideos" class="w-40"
          placeholder="All" />
      </div>

      <!-- Import Section -->
      <div
        class="mb-8 p-5 rounded-xl border bg-white border-zinc-200 dark:bg-zinc-900/50 dark:border-white/10">
        <label class="block text-sm font-medium mb-2 text-zinc-700 dark:text-zinc-300">
          {{ $t('video.import_label') }}
        </label>
        <div class="flex gap-2">
          <input v-model="importUrl" type="url" :placeholder="$t('video.import_placeholder')"
            :disabled="isImporting"
            class="flex-1 rounded-lg border px-3 py-2 text-sm bg-white border-zinc-200 text-zinc-900 dark:bg-zinc-800 dark:border-white/10 dark:text-zinc-100 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors disabled:opacity-50"
            @keydown.enter="handleImport" />
          <button @click="handleImport" :disabled="isImporting || !importUrl.trim()"
            class="rounded-lg px-4 py-2 text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap">
            <span v-if="isImporting">{{ $t('video.importing') }}</span>
            <span v-else>{{ $t('video.import_button') }}</span>
          </button>
        </div>
        <p v-if="importError" class="mt-2 text-sm text-red-600 dark:text-red-400">{{ importError }}</p>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="text-center text-zinc-600 dark:text-zinc-500">{{ $t('video.loading') }}</div>

      <!-- Video Grid -->
      <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div v-if="videos.length === 0" class="col-span-full text-center text-zinc-600 dark:text-zinc-500 py-8">
          {{ $t('video.no_videos') }}
        </div>
        <router-link v-for="video in videos" :key="video.video_id" :to="`/videos/${video.video_id}`"
          class="block rounded-xl border overflow-hidden transition bg-white border-zinc-200 hover:bg-zinc-50 dark:border-white/10 dark:bg-zinc-900/50 dark:hover:bg-zinc-800">
          <!-- Thumbnail -->
          <div class="aspect-video bg-zinc-100 dark:bg-zinc-800 overflow-hidden">
            <img v-if="video.thumbnail_url" :src="video.thumbnail_url" :alt="video.title"
              class="w-full h-full object-cover" />
            <div v-else class="w-full h-full flex items-center justify-center text-zinc-400 text-4xl">
              &#9654;
            </div>
          </div>
          <!-- Info -->
          <div class="p-4">
            <h2 class="text-sm font-semibold line-clamp-2 mb-2">{{ video.title }}</h2>
            <div class="flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
              <span class="truncate">{{ video.channel_name || 'YouTube' }}</span>
              <span v-if="video.duration_seconds" class="ml-2 shrink-0">{{ formatDuration(video.duration_seconds) }}</span>
            </div>
          </div>
        </router-link>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToastStore } from '../stores/toast'
import BaseSelect from '../components/BaseSelect.vue'

const router = useRouter()
const toast = useToastStore()

const API = import.meta.env.VITE_API_BASE_URL

const videos = ref<any[]>([])
const loading = ref(true)
const filterCategory = ref('')
const importUrl = ref('')
const isImporting = ref(false)
const importError = ref('')

const categoryOptions = [
  { value: '', label: 'All' },
]

const formatDuration = (seconds: number): string => {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

const fetchVideos = async () => {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (filterCategory.value) params.append('category', filterCategory.value)
    const query = params.toString() ? `?${params.toString()}` : ''
    const res = await fetch(`${API}/api/videos${query}`)
    videos.value = await res.json()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const handleImport = async () => {
  const url = importUrl.value.trim()
  if (!url) return

  isImporting.value = true
  importError.value = ''

  try {
    const res = await fetch(`${API}/api/videos/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    })
    const data = await res.json()

    if (!res.ok) {
      importError.value = data.error || 'Import failed'
      return
    }

    toast.trigger(data.already_exists ? 'Video already imported' : 'Video imported successfully!', 'success')
    importUrl.value = ''
    router.push(`/videos/${data.video_id}`)
  } catch (e) {
    importError.value = 'Network error. Please try again.'
  } finally {
    isImporting.value = false
  }
}

onMounted(() => {
  fetchVideos()
})
</script>
