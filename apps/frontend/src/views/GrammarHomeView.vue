<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { useAuthStore } from '../stores/auth'
import { useGrammarStore, type ExtractionJob } from '../stores/grammar'
import { useToastStore } from '../stores/toast'

const { t, locale } = useI18n()
const authStore = useAuthStore()
const grammar = useGrammarStore()
const toast = useToastStore()
const router = useRouter()

const file = ref<File | null>(null)
const title = ref('')
const uploading = ref(false)
const activeJob = ref<ExtractionJob | null>(null)

const fileInput = ref<HTMLInputElement | null>(null)

const userId = computed<string>(() => String(authStore.user_id || ''))

function pickFile() {
  fileInput.value?.click()
}

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  const f = target.files?.[0] || null
  file.value = f
  if (f && !title.value) {
    title.value = f.name.replace(/\.(md|markdown|txt)$/i, '')
  }
}

async function refreshDocs() {
  if (!userId.value) return
  await grammar.listDocuments(userId.value)
}

async function pollJob(jobId: string) {
  // Naive polling — every 2s until terminal status. The graph runs in
  // a daemon thread on the server so we just need to watch the row.
  // Cap iterations and tell the user explicitly when we stop, so the
  // UI doesn't go silent on a long extraction.
  const MAX_ITERATIONS = 60
  for (let i = 0; i < MAX_ITERATIONS; i++) {
    const job = await grammar.pollExtractionJob(jobId)
    activeJob.value = job
    if (job.status === 'complete' || job.status === 'failed') {
      await refreshDocs()
      return job
    }
    await new Promise(r => setTimeout(r, 2000))
  }
  // Timed out without a terminal status — extraction is still running
  // server-side; surface that explicitly instead of dropping the job.
  toast.trigger(t('grammar.extraction_still_running'), 'info')
  await refreshDocs()
  return activeJob.value
}

async function onUpload() {
  if (!file.value || !title.value.trim() || !userId.value) return
  uploading.value = true
  try {
    const { extraction_job_id } = await grammar.uploadDocument({
      userId: userId.value,
      file: file.value,
      title: title.value.trim(),
      locale: locale.value,
    })
    toast.trigger(t('grammar.upload_started'), 'success')
    file.value = null
    title.value = ''
    if (fileInput.value) fileInput.value.value = ''
    const finalJob = await pollJob(extraction_job_id)
    if (finalJob?.status === 'complete') {
      toast.trigger(
        t('grammar.extraction_complete', {
          published: finalJob.patterns_published,
          pending: finalJob.patterns_pending,
        }),
        'success',
      )
    } else if (finalJob?.status === 'failed') {
      toast.trigger(t('grammar.extraction_failed'), 'error')
    }
  } catch (e: any) {
    toast.trigger(e?.message || t('grammar.upload_error'), 'error')
  } finally {
    uploading.value = false
  }
}

function openDoc(docId: string) {
  router.push({ name: 'grammar-range', params: { docId } })
}

onMounted(refreshDocs)
</script>

<template>
  <main class="grammar-page">
    <header class="page-header">
      <p class="eyebrow">{{ t('grammar.eyebrow') }}</p>
      <h1>{{ t('grammar.home_title') }}</h1>
      <p class="lede">{{ t('grammar.home_lede') }}</p>
    </header>

    <!-- Upload card -->
    <section class="card">
      <h2>{{ t('grammar.upload_heading') }}</h2>
      <p class="muted">{{ t('grammar.upload_subhead') }}</p>

      <div class="upload-row">
        <button
          type="button"
          class="btn-secondary"
          :disabled="uploading"
          @click="pickFile"
        >
          {{ file ? file.name : t('grammar.pick_file') }}
        </button>
        <input
          ref="fileInput"
          type="file"
          accept=".md,.markdown,.txt"
          hidden
          @change="onFileChange"
        />
        <input
          v-model="title"
          class="text-input"
          :placeholder="t('grammar.title_placeholder')"
          :disabled="uploading"
        />
        <button
          type="button"
          class="btn-primary"
          :disabled="!file || !title.trim() || uploading"
          @click="onUpload"
        >
          {{ uploading ? t('grammar.uploading') : t('grammar.upload_button') }}
        </button>
      </div>

      <!-- Job progress -->
      <div v-if="activeJob" class="job-status">
        <p class="muted small">
          <strong>{{ t(`grammar.job_status_${activeJob.status}`) }}</strong>
          ·
          {{ activeJob.processed_chunks }} / {{ activeJob.total_chunks ?? '—' }}
          {{ t('grammar.chunks') }}
          <span v-if="activeJob.patterns_extracted > 0">
            · {{ activeJob.patterns_published }}{{ ' ' }}{{ t('grammar.published') }},
            {{ activeJob.patterns_pending }} {{ t('grammar.pending') }}
          </span>
        </p>
      </div>
    </section>

    <!-- Documents list -->
    <section class="card">
      <h2>{{ t('grammar.docs_heading') }}</h2>
      <p v-if="grammar.loading && grammar.documents.length === 0" class="muted">
        {{ t('common.loading') }}
      </p>
      <p v-else-if="grammar.documents.length === 0" class="muted">
        {{ t('grammar.no_docs') }}
      </p>
      <ul v-else class="doc-list">
        <li
          v-for="doc in grammar.documents"
          :key="doc.doc_id"
          class="doc-row"
          @click="openDoc(doc.doc_id)"
        >
          <div class="doc-row-main">
            <h3>{{ doc.title }}</h3>
            <p class="muted small">
              {{ doc.chunk_count }} {{ t('grammar.chunks') }} ·
              {{ doc.pattern_count }} {{ t('grammar.patterns') }}
            </p>
          </div>
          <span class="chevron">→</span>
        </li>
      </ul>
    </section>
  </main>
</template>

<style scoped>
.grammar-page {
  max-width: 880px;
  margin: 96px auto 64px;
  padding: 0 24px;
  display: grid;
  gap: 32px;
}

.page-header { display: grid; gap: 8px; }
.eyebrow {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  margin: 0;
}
.page-header h1 {
  font-family: var(--font-serif);
  font-size: 2rem;
  margin: 0;
}
.page-header .lede {
  font-family: var(--font-serif);
  font-style: italic;
  color: color-mix(in oklab, var(--foreground) 70%, transparent);
  margin: 0;
  max-width: 60ch;
}

.card {
  background: var(--card);
  border: 1px solid color-mix(in oklab, var(--foreground) 10%, transparent);
  border-radius: 12px;
  padding: 24px;
  display: grid;
  gap: 12px;
}
.card h2 {
  font-family: var(--font-serif);
  font-size: 1.15rem;
  margin: 0;
}
.muted { color: color-mix(in oklab, var(--foreground) 60%, transparent); margin: 0; }
.muted.small { font-size: 0.85rem; }

.upload-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 12px;
  align-items: center;
  margin-top: 8px;
}
@media (max-width: 640px) {
  .upload-row { grid-template-columns: 1fr; }
}

.text-input {
  font-family: var(--font-serif);
  font-size: 0.95rem;
  padding: 10px 12px;
  background: var(--background);
  border: 1px solid color-mix(in oklab, var(--foreground) 14%, transparent);
  border-radius: 8px;
  color: var(--foreground);
}
.text-input:focus {
  outline: none;
  border-color: var(--secondary);
}

.btn-primary, .btn-secondary {
  font-family: var(--font-sans);
  font-size: 0.78rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  padding: 10px 18px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: opacity 160ms ease, background 160ms ease;
}
.btn-primary {
  background: var(--primary);
  color: var(--primary-foreground);
}
.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-secondary {
  background: transparent;
  color: var(--foreground);
  border-color: color-mix(in oklab, var(--foreground) 22%, transparent);
}
.btn-secondary:hover:not(:disabled) {
  background: color-mix(in oklab, var(--foreground) 5%, transparent);
}

.job-status {
  border-top: 1px dashed color-mix(in oklab, var(--foreground) 12%, transparent);
  padding-top: 12px;
  margin-top: 4px;
}

.doc-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 4px;
}
.doc-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 160ms ease;
}
.doc-row:hover {
  background: color-mix(in oklab, var(--foreground) 5%, transparent);
}
.doc-row h3 {
  font-family: var(--font-serif);
  font-size: 1.05rem;
  margin: 0 0 2px 0;
}
.chevron {
  font-family: var(--font-serif);
  color: color-mix(in oklab, var(--foreground) 40%, transparent);
}
</style>
