import { defineStore } from 'pinia'
import {
  ApiError,
  SESSION_USER_ID_STORAGE_KEY,
  UNAUTHORIZED_EVENT,
  apiJson,
  getSessionToken,
  setSessionToken,
} from '../lib/api'

let pendingHydration: Promise<boolean> | null = null

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user_id: localStorage.getItem(SESSION_USER_ID_STORAGE_KEY),
    token: getSessionToken(),
    hasHydrated: false,
    isHydrating: false,
    unauthorizedListenerStarted: false,
  }),
  getters: {
    isAuthenticated: (state) => state.user_id !== null && state.token !== null,
    scopedStorageKey: (state) => (key: string) => {
      return state.user_id ? `${key}:${state.user_id}` : `${key}:anonymous`;
    },
  },
  actions: {
    login(userId: unknown, token: string) {
      this.user_id = userId === null || userId === undefined ? null : String(userId)
      this.token = token
      setSessionToken(token)
      if (this.user_id) {
        localStorage.setItem(SESSION_USER_ID_STORAGE_KEY, this.user_id)
      } else {
        localStorage.removeItem(SESSION_USER_ID_STORAGE_KEY)
      }
      this.hasHydrated = true
    },
    logout() {
      this.user_id = null
      this.token = null
      setSessionToken(null)
      localStorage.removeItem(SESSION_USER_ID_STORAGE_KEY)
      this.hasHydrated = true
    },
    clearSession() {
      this.user_id = null
      this.token = null
      setSessionToken(null)
      localStorage.removeItem(SESSION_USER_ID_STORAGE_KEY)
    },
    async hydrateSession(): Promise<boolean> {
      if (pendingHydration) return pendingHydration
      pendingHydration = this.doHydrateSession().finally(() => {
        pendingHydration = null
      })
      return pendingHydration
    },
    async doHydrateSession(): Promise<boolean> {
      if (this.isHydrating) return this.isAuthenticated

      this.token = getSessionToken()
      if (!this.token) {
        this.clearSession()
        this.hasHydrated = true
        return false
      }

      this.isHydrating = true
      try {
        const data = await apiJson<{ user_id: string }>('/api/users/me')
        this.user_id = data.user_id
        localStorage.setItem(SESSION_USER_ID_STORAGE_KEY, data.user_id)
        this.hasHydrated = true
        return true
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          this.clearSession()
          this.hasHydrated = true
          return false
        }
        console.warn('Session hydration failed', err)
        this.hasHydrated = true
        return this.isAuthenticated
      } finally {
        this.isHydrating = false
      }
    },
    initSessionEvents() {
      if (this.unauthorizedListenerStarted) return
      window.addEventListener(UNAUTHORIZED_EVENT, () => {
        this.clearSession()
        this.hasHydrated = true
      })
      this.unauthorizedListenerStarted = true
    },
    requireUserId(): string {
      if (!this.user_id) {
        throw new Error('A logged-in user is required for this action')
      }
      return this.user_id
    },
  },
})
