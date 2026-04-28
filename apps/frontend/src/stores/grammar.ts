import { defineStore } from 'pinia'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string) || '/api'

export interface DocumentSummary {
  doc_id: string
  title: string
  source_type: string
  status: string
  created_timestamp: string
  chunk_count: number
  pattern_count: number
}

export interface DocChunk {
  chunk_id: string
  seq: number
  section_label: string | null
  heading_level: number | null
  text: string
  token_count: number
}

export interface PracticeRange {
  range_id: string
  doc_id: string
  label: string
  chunk_ids: string[]
  chunk_count: number
  created_timestamp: string
}

export interface ExtractionJob {
  job_id: string
  doc_id: string
  user_id: string
  locale: string
  status: 'queued' | 'running' | 'complete' | 'failed'
  total_chunks: number | null
  processed_chunks: number
  patterns_extracted: number
  patterns_published: number
  patterns_pending: number
  error: string | null
  started_at: string | null
  completed_at: string | null
  created_timestamp: string
}

export interface PracticeExercise {
  exercise_id: string
  type: 'pattern_use'
  target_pattern_id: string
  target_pattern_name: string
  difficulty: number
  prompt: string
  source: 'graph' | 'fallback_canonical'
  retries: number
  pattern_index_in_session: number
  pattern_count_in_range: number
}

export interface SessionState {
  total_in_range: number
  covered_in_session: number
  /** True iff the backend returned `error: 'session_complete'`
   *  meaning every pattern in the range has been practised. */
  is_complete: boolean
}

export interface SubmissionResult {
  attempt_id: string
  score: number
  is_correct: boolean
  used_pattern: boolean
  feedback_text: string
  issues: string[]
  detector: { detected: boolean; matched: string[]; reason: string; pattern_name: string }
  morph_diff: unknown | null
  target_register: string
}

interface State {
  documents: DocumentSummary[]
  chunksByDoc: Record<string, DocChunk[]>
  rangesByDoc: Record<string, PracticeRange[]>
  jobsById: Record<string, ExtractionJob>
  loading: boolean
  /** Localised error key suitable for i18n lookup, or a plain message. */
  errorKey: string | null
  currentExercise: PracticeExercise | null
  lastResult: SubmissionResult | null
  /** Per-range record of pattern_ids practised in the current session.
   *  Used as exclude_pattern_ids so the planner rotates instead of
   *  repeating one pattern. */
  seenPatternIdsByRange: Record<string, string[]>
  sessionState: SessionState | null
}

/** Result of a fetch that may carry an `error` key in its JSON body
 *  (the backend uses this for 422 responses on /practice/next). */
interface FetchOk<T> { ok: true; data: T }
interface FetchErr  { ok: false; status: number; body: any }
type FetchResult<T> = FetchOk<T> | FetchErr

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}: ${body || path}`)
  }
  return (await res.json()) as T
}

async function jsonFetchSafe<T>(path: string, init?: RequestInit
                                ): Promise<FetchResult<T>> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (res.ok) {
    return { ok: true, data: (await res.json()) as T }
  }
  const body = await res.json().catch(() => ({}))
  return { ok: false, status: res.status, body }
}

export const useGrammarStore = defineStore('grammar', {
  state: (): State => ({
    documents: [],
    chunksByDoc: {},
    rangesByDoc: {},
    jobsById: {},
    loading: false,
    errorKey: null,
    currentExercise: null,
    lastResult: null,
    seenPatternIdsByRange: {},
    sessionState: null,
  }),

  actions: {
    async listDocuments(userId: string) {
      this.loading = true
      this.errorKey = null
      try {
        this.documents = await jsonFetch<DocumentSummary[]>(
          `/documents?user_id=${encodeURIComponent(userId)}`,
        )
      } catch (e: any) {
        this.errorKey = e?.message ?? String(e)
      } finally {
        this.loading = false
      }
    },

    async uploadDocument(args: {
      userId: string
      file: File
      title: string
      sourceType?: string
      locale: string
    }): Promise<{ doc_id: string; extraction_job_id: string }> {
      const fd = new FormData()
      fd.append('file', args.file)
      fd.append('user_id', args.userId)
      fd.append('title', args.title)
      fd.append('source_type', args.sourceType || 'grammar_notes')
      fd.append('locale', args.locale)
      const res = await fetch(`${API_BASE}/documents/upload`, {
        method: 'POST',
        body: fd,
      })
      if (!res.ok) {
        const body = await res.text().catch(() => '')
        throw new Error(`Upload failed (${res.status}): ${body}`)
      }
      return res.json()
    },

    async pollExtractionJob(jobId: string): Promise<ExtractionJob> {
      const job = await jsonFetch<ExtractionJob>(`/extraction/jobs/${jobId}`)
      this.jobsById[jobId] = job
      return job
    },

    async loadChunks(docId: string) {
      const data = await jsonFetch<{ doc_id: string; title: string; chunks: DocChunk[] }>(
        `/documents/${docId}/chunks`,
      )
      this.chunksByDoc[docId] = data.chunks
    },

    async loadRanges(userId: string, docId: string) {
      this.rangesByDoc[docId] = await jsonFetch<PracticeRange[]>(
        `/documents/${docId}/ranges?user_id=${encodeURIComponent(userId)}`,
      )
    },

    async createRange(args: {
      userId: string
      docId: string
      label: string
      chunkIds: string[]
    }): Promise<PracticeRange> {
      return jsonFetch<PracticeRange>(`/documents/${args.docId}/ranges`, {
        method: 'POST',
        body: JSON.stringify({
          user_id: args.userId,
          label: args.label,
          chunk_ids: args.chunkIds,
        }),
      })
    },

    /** Frontend-side session memory of which patterns have been
     *  practised in this range so the planner rotates instead of
     *  repeating one pattern. */
    markPatternSeen(rangeId: string, patternId: string) {
      const list = this.seenPatternIdsByRange[rangeId] || []
      if (!list.includes(patternId)) {
        this.seenPatternIdsByRange[rangeId] = [...list, patternId]
      }
    },

    resetSession(rangeId: string) {
      this.seenPatternIdsByRange[rangeId] = []
      this.sessionState = null
      this.currentExercise = null
      this.lastResult = null
      this.errorKey = null
    },

    async fetchNextExercise(userId: string, rangeId: string, locale: string) {
      this.loading = true
      this.errorKey = null
      this.lastResult = null
      try {
        const exclude = this.seenPatternIdsByRange[rangeId] || []
        const res = await jsonFetchSafe<PracticeExercise>(`/practice/next`, {
          method: 'POST',
          body: JSON.stringify({
            user_id: userId,
            range_id: rangeId,
            locale,
            exclude_pattern_ids: exclude,
          }),
        })
        if (res.ok) {
          this.currentExercise = res.data
          this.sessionState = {
            total_in_range: res.data.pattern_count_in_range,
            covered_in_session: res.data.pattern_index_in_session - 1,
            is_complete: false,
          }
        } else {
          this.currentExercise = null
          // The backend returns a structured 422 with an error key like
          // "session_complete", "no_published_patterns_in_range", or
          // "plan_invented_pattern_id". Surface that key so the UI can
          // localise it instead of toasting raw JSON.
          const body = res.body || {}
          const errKey = typeof body.error === 'string' ? body.error : 'unknown'
          this.errorKey = errKey
          if (errKey === 'session_complete') {
            this.sessionState = {
              total_in_range: body.total_in_range || 0,
              covered_in_session: body.covered_in_session || 0,
              is_complete: true,
            }
          }
        }
      } catch (e: any) {
        this.errorKey = e?.message ?? 'network_error'
        this.currentExercise = null
      } finally {
        this.loading = false
      }
    },

    async submitResponse(args: {
      userId: string
      exerciseId: string
      response: string
      locale: string
    }) {
      this.loading = true
      try {
        this.lastResult = await jsonFetch<SubmissionResult>(`/practice/submit`, {
          method: 'POST',
          body: JSON.stringify({
            user_id: args.userId,
            exercise_id: args.exerciseId,
            user_response: args.response,
            locale: args.locale,
          }),
        })
        return this.lastResult
      } finally {
        this.loading = false
      }
    },
  },
})
