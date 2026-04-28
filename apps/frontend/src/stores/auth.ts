import { defineStore } from 'pinia'

const STORAGE_KEY = 'shiori.auth.user_id'

function readStoredUserId(): string | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw && raw !== 'null' ? raw : null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: (): { user_id: string | null } => ({
    // Survives reload by reading the persisted id at store-init time.
    user_id: readStoredUserId(),
  }),
  actions: {
    login(user_id: any) {
      this.user_id = user_id ? String(user_id) : null
      try {
        if (this.user_id) localStorage.setItem(STORAGE_KEY, this.user_id)
        else localStorage.removeItem(STORAGE_KEY)
      } catch {
        /* localStorage unavailable — fall back to in-memory only */
      }
    },
    logout() {
      this.user_id = null
      try { localStorage.removeItem(STORAGE_KEY) } catch { /* ignore */ }
    },
  },
})
