<template>
  <main class="min-h-[calc(100vh-4rem)] p-6 pt-24 pb-24 text-zinc-900 dark:text-zinc-100">
    <div class="mx-auto max-w-5xl">
      <!-- Loading -->
      <div v-if="loading" class="text-center text-zinc-600 dark:text-zinc-500 py-12">{{ $t('video.loading') }}</div>

      <!-- Error -->
      <div v-else-if="!video" class="text-center text-zinc-600 dark:text-zinc-500 py-12">
        Video not found.
      </div>

      <template v-else>
        <!-- Header -->
        <div class="mb-4">
          <router-link to="/videos"
            class="text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white transition-colors">
            {{ $t('video.back_to_list') }}
          </router-link>
          <h1 class="text-xl font-bold mt-1">{{ video.info.title }}</h1>
          <p v-if="video.info.channel_name" class="text-sm text-zinc-500 dark:text-zinc-400">
            {{ video.info.channel_name }}
          </p>
        </div>

        <!-- YouTube Player -->
        <div class="mb-6 rounded-xl overflow-hidden border border-zinc-200 dark:border-white/10 bg-black">
          <div class="relative w-full" style="padding-bottom: 56.25%;">
            <div id="yt-player" class="absolute inset-0"></div>
          </div>
        </div>

        <!-- Transcript Panel -->
        <div v-if="transcript.length"
          class="mb-6 rounded-xl border bg-white border-zinc-200 dark:bg-zinc-900/50 dark:border-white/10">
          <button @click="showTranscript = !showTranscript"
            class="w-full flex items-center justify-between px-5 py-3 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors rounded-xl">
            <span>{{ $t('video.transcript') }}</span>
            <span class="text-xs">{{ showTranscript ? $t('video.hide_transcript') : $t('video.show_transcript')
              }}</span>
          </button>
          <div v-if="showTranscript" class="max-h-60 overflow-y-auto px-5 pb-4 space-y-1 custom-scrollbar">
            <button v-for="(seg, i) in transcript" :key="i" @click="seekTo(seg.start)"
              class="w-full text-left flex gap-3 px-2 py-1.5 rounded-lg text-sm hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
              :class="isActiveSegment(seg.start, i) ? 'bg-emerald-50 dark:bg-emerald-400/10 text-emerald-700 dark:text-emerald-300' : ''">
              <span class="shrink-0 text-xs font-mono text-zinc-400 dark:text-zinc-500 w-10 pt-0.5">
                {{ formatTime(seg.start) }}
              </span>
              <span>{{ seg.text }}</span>
            </button>
          </div>
        </div>

        <!-- Tabs -->
        <div class="flex gap-1 mb-4">
          <button @click="activeTab = 'vocabulary'"
            class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="activeTab === 'vocabulary' ? 'bg-emerald-500/10 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-200' : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800'">
            {{ $t('video.tab_vocabulary') }}
          </button>
          <button @click="activeTab = 'comprehension'"
            class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="activeTab === 'comprehension' ? 'bg-emerald-500/10 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-200' : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800'">
            {{ $t('video.tab_comprehension') }}
          </button>
        </div>

        <!-- Vocabulary Tab -->
        <div v-if="activeTab === 'vocabulary'" class="space-y-4">
          <div v-if="exercises.length === 0" class="text-center text-zinc-500 dark:text-zinc-400 py-6 text-sm">
            {{ $t('video.no_exercises') }}
          </div>
          <div v-for="(ex, idx) in exercises" :key="ex.exercise_id"
            class="rounded-xl border p-5 bg-white border-zinc-200 dark:bg-zinc-900/50 dark:border-white/10">
            <div class="flex items-start justify-between mb-3">
              <p class="text-base font-medium">
                <span class="text-zinc-400 dark:text-zinc-500 mr-2">Q{{ idx + 1 }}.</span>
                {{ ex.question_sentence }}
              </p>
              <button v-if="ex.hint_chinese && !ex.showHint" @click="ex.showHint = true"
                class="shrink-0 ml-3 text-xs text-indigo-600 dark:text-indigo-400 hover:underline">
                {{ $t('video.hint_label') }}
              </button>
            </div>
            <!-- Hint -->
            <p v-if="ex.showHint && ex.hint_chinese"
              class="mb-3 text-sm text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-400/10 rounded-lg px-3 py-2">
              {{ ex.hint_chinese }}
            </p>
            <!-- Answer Input -->
            <div v-if="!ex.answered" class="flex gap-2">
              <input v-model="ex.userAnswer" :placeholder="$t('exercise.type_here')"
                class="flex-1 rounded-lg border px-3 py-2 text-sm bg-white border-zinc-200 text-zinc-900 dark:bg-zinc-800 dark:border-white/10 dark:text-zinc-100 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors"
                @keydown.enter="submitCloze(ex)" />
              <button @click="submitCloze(ex)" :disabled="!ex.userAnswer?.trim() || ex.submitting"
                class="rounded-lg px-4 py-2 text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors">
                {{ $t('video.submit') }}
              </button>
            </div>
            <!-- Result -->
            <div v-else class="mt-2">
              <p v-if="ex.isCorrect" class="text-sm font-medium text-emerald-600 dark:text-emerald-400">
                {{ $t('video.correct') }}
              </p>
              <div v-else>
                <p class="text-sm font-medium text-rose-600 dark:text-rose-400">
                  {{ $t('video.incorrect') }}
                </p>
                <p class="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
                  {{ $t('video.correct_answer_is', { answer: ex.correct_answer }) }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- Comprehension Tab -->
        <div v-if="activeTab === 'comprehension'" class="space-y-4">
          <p class="text-sm text-zinc-500 dark:text-zinc-400">{{ $t('video.comprehension_intro') }}</p>

          <button v-if="comprehensionQuestions.length === 0" @click="generateComprehension"
            :disabled="isGenerating"
            class="rounded-lg px-5 py-2.5 text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors">
            <span v-if="isGenerating">{{ $t('video.generating') }}</span>
            <span v-else>{{ $t('video.generate_questions') }}</span>
          </button>

          <div v-for="(q, qi) in comprehensionQuestions" :key="qi"
            class="rounded-xl border p-5 bg-white border-zinc-200 dark:bg-zinc-900/50 dark:border-white/10">
            <p class="text-base font-medium mb-4">
              <span class="text-zinc-400 dark:text-zinc-500 mr-2">Q{{ qi + 1 }}.</span>
              {{ q.question }}
            </p>
            <!-- Choices -->
            <div class="space-y-2 mb-4">
              <button v-for="(choice, ci) in q.choices" :key="ci" @click="selectChoice(qi, ci)"
                :disabled="q.answered"
                class="w-full text-left flex items-center gap-3 px-4 py-2.5 rounded-lg border text-sm transition-colors"
                :class="choiceClass(q, ci)">
                <span
                  class="shrink-0 w-6 h-6 rounded-full border-2 flex items-center justify-center text-xs font-medium"
                  :class="choiceBulletClass(q, ci)">
                  {{ String.fromCharCode(65 + ci) }}
                </span>
                <span>{{ choice }}</span>
              </button>
            </div>
            <!-- Check Button -->
            <button v-if="!q.answered && q.selectedIndex !== undefined && q.selectedIndex !== null"
              @click="checkComprehension(qi)" :disabled="q.checking"
              class="rounded-lg px-4 py-2 text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors">
              {{ $t('video.check_answer') }}
            </button>
            <!-- Result -->
            <div v-if="q.answered" class="mt-3">
              <p v-if="q.isCorrect" class="text-sm font-medium text-emerald-600 dark:text-emerald-400">
                {{ $t('video.correct') }}
              </p>
              <div v-else>
                <p class="text-sm font-medium text-rose-600 dark:text-rose-400 mb-1">{{ $t('video.incorrect') }}</p>
                <p v-if="q.feedback" class="text-sm text-zinc-600 dark:text-zinc-400">{{ q.feedback }}</p>
              </div>
              <p v-if="q.explanation && q.isCorrect" class="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
                {{ q.explanation }}
              </p>
            </div>
          </div>
        </div>
      </template>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const authStore = useAuthStore()

const API = import.meta.env.VITE_API_BASE_URL
const videoId = route.params.id as string

const loading = ref(true)
const video = ref<any>(null)
const transcript = ref<any[]>([])
const exercises = ref<any[]>([])
const showTranscript = ref(true)
const activeTab = ref('vocabulary')
const currentTime = ref(0)

// Comprehension state
const comprehensionQuestions = ref<any[]>([])
const isGenerating = ref(false)

// YouTube player
let player: any = null
let timeInterval: ReturnType<typeof setInterval> | null = null

const formatTime = (seconds: number): string => {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

const isActiveSegment = (start: number, index: number): boolean => {
  const nextStart = index + 1 < transcript.value.length ? transcript.value[index + 1].start : Infinity
  return currentTime.value >= start && currentTime.value < nextStart
}

const seekTo = (seconds: number) => {
  if (player && player.seekTo) {
    player.seekTo(seconds, true)
  }
}

// YouTube IFrame API
const initPlayer = () => {
  if (!video.value?.info?.external_id) return

  // Load the IFrame API if not already loaded
  if (!(window as any).YT) {
    const tag = document.createElement('script')
    tag.src = 'https://www.youtube.com/iframe_api'
    document.head.appendChild(tag)
    ;(window as any).onYouTubeIframeAPIReady = () => createPlayer()
  } else {
    createPlayer()
  }
}

const createPlayer = () => {
  player = new (window as any).YT.Player('yt-player', {
    videoId: video.value.info.external_id,
    width: '100%',
    height: '100%',
    playerVars: {
      rel: 0,
      modestbranding: 1,
      cc_load_policy: 0,
    },
    events: {
      onReady: () => {
        // Poll current time for transcript highlighting
        timeInterval = setInterval(() => {
          if (player && player.getCurrentTime) {
            currentTime.value = player.getCurrentTime()
          }
        }, 500)
      },
    },
  })
}

// Fetch data
const fetchVideo = async () => {
  try {
    const res = await fetch(`${API}/api/videos/${videoId}`)
    if (!res.ok) return
    video.value = await res.json()
    transcript.value = video.value.transcript || []
  } catch (e) {
    console.error(e)
  }
}

const fetchExercises = async () => {
  try {
    const res = await fetch(`${API}/api/videos/${videoId}/exercises`)
    if (!res.ok) return
    const data = await res.json()
    // Add UI state to each exercise
    exercises.value = data.map((ex: any) => ({
      ...ex,
      userAnswer: '',
      answered: false,
      isCorrect: false,
      submitting: false,
      showHint: false,
    }))
  } catch (e) {
    console.error(e)
  }
}

// Submit cloze answer
const submitCloze = async (ex: any) => {
  if (!ex.userAnswer?.trim() || ex.submitting) return
  ex.submitting = true

  try {
    const res = await fetch(`${API}/api/videos/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        exercise_id: ex.exercise_id,
        video_id: videoId,
        user_answer: ex.userAnswer.trim(),
        user_id: authStore.user_id,
      }),
    })
    const data = await res.json()
    ex.answered = true
    ex.isCorrect = data.is_correct
  } catch (e) {
    console.error(e)
  } finally {
    ex.submitting = false
  }
}

// Comprehension
const generateComprehension = async () => {
  isGenerating.value = true
  try {
    const res = await fetch(`${API}/api/videos/${videoId}/comprehension`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ num_questions: 5 }),
    })
    const data = await res.json()
    comprehensionQuestions.value = (data.questions || []).map((q: any) => ({
      ...q,
      selectedIndex: null,
      answered: false,
      isCorrect: false,
      checking: false,
      feedback: '',
    }))
  } catch (e) {
    console.error(e)
  } finally {
    isGenerating.value = false
  }
}

const selectChoice = (qi: number, ci: number) => {
  const q = comprehensionQuestions.value[qi]
  if (!q.answered) {
    q.selectedIndex = ci
  }
}

const checkComprehension = async (qi: number) => {
  const q = comprehensionQuestions.value[qi]
  if (q.selectedIndex === null || q.selectedIndex === undefined) return
  q.checking = true

  try {
    const res = await fetch(`${API}/api/videos/comprehension/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: q.question,
        choices: q.choices,
        correct_index: q.correct_index,
        user_answer_index: q.selectedIndex,
        transcript_context: transcript.value.map((s: any) => s.text).join(' ').slice(0, 500),
        user_id: authStore.user_id,
        video_id: videoId,
      }),
    })
    const data = await res.json()
    q.answered = true
    q.isCorrect = data.is_correct
    q.feedback = data.feedback || ''
  } catch (e) {
    console.error(e)
  } finally {
    q.checking = false
  }
}

const choiceClass = (q: any, ci: number): string => {
  if (q.answered) {
    if (ci === q.correct_index)
      return 'border-emerald-300 bg-emerald-50 dark:bg-emerald-400/10 dark:border-emerald-400/30'
    if (ci === q.selectedIndex && !q.isCorrect)
      return 'border-rose-300 bg-rose-50 dark:bg-rose-400/10 dark:border-rose-400/30'
    return 'border-zinc-200 dark:border-white/10 opacity-50'
  }
  if (ci === q.selectedIndex)
    return 'border-emerald-400 bg-emerald-50 dark:bg-emerald-400/10 dark:border-emerald-400/40'
  return 'border-zinc-200 dark:border-white/10 hover:border-zinc-300 dark:hover:border-white/20'
}

const choiceBulletClass = (q: any, ci: number): string => {
  if (q.answered && ci === q.correct_index)
    return 'border-emerald-500 text-emerald-600 dark:border-emerald-400 dark:text-emerald-300'
  if (q.answered && ci === q.selectedIndex && !q.isCorrect)
    return 'border-rose-500 text-rose-600 dark:border-rose-400 dark:text-rose-300'
  if (ci === q.selectedIndex)
    return 'border-emerald-500 text-emerald-600 dark:border-emerald-400 dark:text-emerald-300'
  return 'border-zinc-300 text-zinc-400 dark:border-zinc-600 dark:text-zinc-500'
}

onMounted(async () => {
  await Promise.all([fetchVideo(), fetchExercises()])
  loading.value = false
  await nextTick()
  initPlayer()
})

onBeforeUnmount(() => {
  if (timeInterval) clearInterval(timeInterval)
  if (player && player.destroy) player.destroy()
})
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #a1a1aa;
  border-radius: 3px;
}

:global(.dark) .custom-scrollbar::-webkit-scrollbar-thumb {
  background: #52525b;
}

:global(#yt-player iframe) {
  width: 100% !important;
  height: 100% !important;
}
</style>
