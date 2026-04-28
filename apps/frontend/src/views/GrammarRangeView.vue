<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { useAuthStore } from '../stores/auth'
import { useGrammarStore } from '../stores/grammar'
import { useToastStore } from '../stores/toast'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const grammar = useGrammarStore()
const toast = useToastStore()

const docId = computed<string>(() => String(route.params.docId))
const userId = computed<string>(() => String(authStore.user_id || ''))

const selected = ref<Set<string>>(new Set())
const label = ref('')
const saving = ref(false)

const chunks = computed(() => grammar.chunksByDoc[docId.value] || [])
const ranges = computed(() => grammar.rangesByDoc[docId.value] || [])

function toggleChunk(chunkId: string) {
  const next = new Set(selected.value)
  if (next.has(chunkId)) next.delete(chunkId)
  else next.add(chunkId)
  selected.value = next
}

function selectAll() {
  selected.value = new Set(chunks.value.map(c => c.chunk_id))
}

function clearSelection() {
  selected.value = new Set()
}

async function saveRange() {
  if (selected.value.size === 0 || !label.value.trim()) return
  saving.value = true
  try {
    await grammar.createRange({
      userId: userId.value,
      docId: docId.value,
      label: label.value.trim(),
      chunkIds: Array.from(selected.value),
    })
    toast.trigger(t('grammar.range_saved'), 'success')
    label.value = ''
    selected.value = new Set()
    await grammar.loadRanges(userId.value, docId.value)
  } catch (e: any) {
    toast.trigger(e?.message || t('grammar.range_error'), 'error')
  } finally {
    saving.value = false
  }
}

function startPractice(rangeId: string) {
  router.push({ name: 'grammar-practice', params: { rangeId } })
}

// Truncate long chunks for the picker preview.
function preview(text: string, n = 90): string {
  const cleaned = text.replace(/\s+/g, ' ').trim()
  return cleaned.length > n ? cleaned.slice(0, n) + '…' : cleaned
}

onMounted(async () => {
  await Promise.all([
    grammar.loadChunks(docId.value),
    grammar.loadRanges(userId.value, docId.value),
  ])
})
</script>

<template>
  <main class="grammar-page">
    <header class="page-header">
      <p class="eyebrow">
        <router-link to="/grammar" class="back-link">← {{ t('grammar.back_to_library') }}</router-link>
      </p>
      <h1>{{ t('grammar.range_title') }}</h1>
      <p class="lede">{{ t('grammar.range_lede') }}</p>
    </header>

    <!-- Existing ranges -->
    <section v-if="ranges.length > 0" class="card">
      <h2>{{ t('grammar.saved_ranges') }}</h2>
      <ul class="range-list">
        <li v-for="r in ranges" :key="r.range_id" class="range-row">
          <div>
            <h3>{{ r.label }}</h3>
            <p class="muted small">{{ r.chunk_count }} {{ t('grammar.chunks') }}</p>
          </div>
          <button class="btn-primary" @click="startPractice(r.range_id)">
            {{ t('grammar.practice') }}
          </button>
        </li>
      </ul>
    </section>

    <!-- Chunk picker -->
    <section class="card">
      <div class="section-head">
        <h2>{{ t('grammar.pick_sections') }}</h2>
        <div class="picker-actions">
          <button type="button" class="btn-link" @click="selectAll">
            {{ t('grammar.select_all') }}
          </button>
          <button type="button" class="btn-link" @click="clearSelection">
            {{ t('grammar.clear') }}
          </button>
        </div>
      </div>

      <p v-if="chunks.length === 0" class="muted">{{ t('common.loading') }}</p>
      <ul v-else class="chunk-list">
        <li
          v-for="chunk in chunks"
          :key="chunk.chunk_id"
          class="chunk-row"
          :class="{ 'is-selected': selected.has(chunk.chunk_id) }"
          @click="toggleChunk(chunk.chunk_id)"
        >
          <input
            type="checkbox"
            :checked="selected.has(chunk.chunk_id)"
            @click.stop="toggleChunk(chunk.chunk_id)"
          />
          <div class="chunk-body">
            <p class="chunk-label">
              {{ chunk.section_label || t('grammar.unlabeled_section') }}
            </p>
            <p class="muted small">{{ preview(chunk.text) }}</p>
          </div>
        </li>
      </ul>

      <div class="save-row">
        <input
          v-model="label"
          class="text-input"
          :placeholder="t('grammar.range_label_placeholder')"
          :disabled="saving"
        />
        <button
          type="button"
          class="btn-primary"
          :disabled="saving || selected.size === 0 || !label.trim()"
          @click="saveRange"
        >
          {{ t('grammar.save_range') }}
          <span v-if="selected.size > 0" class="badge">{{ selected.size }}</span>
        </button>
      </div>
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
.eyebrow { margin: 0; }
.back-link {
  font-family: var(--font-sans);
  font-size: 0.72rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  text-decoration: none;
}
.back-link:hover { color: var(--foreground); }
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
}

.card {
  background: var(--card);
  border: 1px solid color-mix(in oklab, var(--foreground) 10%, transparent);
  border-radius: 12px;
  padding: 24px;
  display: grid;
  gap: 12px;
}
.card h2 { font-family: var(--font-serif); font-size: 1.15rem; margin: 0; }
.muted { color: color-mix(in oklab, var(--foreground) 60%, transparent); margin: 0; }
.muted.small { font-size: 0.85rem; }

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.picker-actions { display: flex; gap: 12px; }

.btn-link {
  background: none;
  border: none;
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  cursor: pointer;
  padding: 4px 0;
}
.btn-link:hover { color: var(--foreground); }

.range-list, .chunk-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 4px;
}
.range-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
}
.range-row h3 {
  font-family: var(--font-serif);
  font-size: 1.05rem;
  margin: 0 0 2px 0;
}

.chunk-row {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 160ms ease;
  align-items: flex-start;
}
.chunk-row:hover {
  background: color-mix(in oklab, var(--foreground) 5%, transparent);
}
.chunk-row.is-selected {
  background: color-mix(in oklab, var(--secondary) 12%, transparent);
}
.chunk-row input[type="checkbox"] { margin-top: 4px; flex-shrink: 0; }

.chunk-body { display: grid; gap: 4px; min-width: 0; flex: 1; }
.chunk-label {
  font-family: var(--font-serif);
  font-size: 0.95rem;
  margin: 0;
  font-weight: 500;
}

.save-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: center;
  margin-top: 12px;
  border-top: 1px dashed color-mix(in oklab, var(--foreground) 12%, transparent);
  padding-top: 16px;
}
@media (max-width: 640px) {
  .save-row { grid-template-columns: 1fr; }
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
.text-input:focus { outline: none; border-color: var(--secondary); }

.btn-primary {
  font-family: var(--font-sans);
  font-size: 0.78rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  padding: 10px 18px;
  border-radius: 8px;
  cursor: pointer;
  background: var(--primary);
  color: var(--primary-foreground);
  border: 1px solid transparent;
  transition: opacity 160ms ease;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  padding: 0 6px;
  height: 20px;
  border-radius: 10px;
  background: color-mix(in oklab, var(--primary-foreground) 30%, transparent);
  font-size: 0.7rem;
  letter-spacing: 0;
}
</style>
