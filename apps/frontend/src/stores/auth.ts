import { defineStore } from 'pinia'
import {
  ApiError,
  SESSION_GUEST_STORAGE_KEY,
  SESSION_USER_ID_STORAGE_KEY,
  UNAUTHORIZED_EVENT,
  apiJson,
  getSessionToken,
  setSessionToken,
} from '../lib/api'

let pendingHydration: Promise<boolean> | null = null

function readGuestFlag(): boolean {
  try {
    return localStorage.getItem(SESSION_GUEST_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function writeGuestFlag(isGuest: boolean): void {
  try {
    if (isGuest) localStorage.setItem(SESSION_GUEST_STORAGE_KEY, '1')
    else localStorage.removeItem(SESSION_GUEST_STORAGE_KEY)
  } catch {
    /* storage may be unavailable (private mode) — non-fatal */
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user_id: localStorage.getItem(SESSION_USER_ID_STORAGE_KEY),
    token: getSessionToken(),
    // Guest previews are real (temporary) accounts on the backend; the flag
    // only drives chrome: the banner, "Create account" in place of Logout,
    // and where an expired session is sent.
    isGuest: readGuestFlag(),
    // Set when a guest session is cleared *implicitly* (401 / expiry) so the
    // router can start a fresh preview instead of showing the login form.
    // An explicit "End preview" / logout resets it.
    lastSessionWasGuest: false,
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
    login(userId: unknown, token: string, guest = false) {
      this.user_id = userId === null || userId === undefined ? null : String(userId)
      this.token = token
      this.isGuest = guest
      this.lastSessionWasGuest = false
      setSessionToken(token)
      writeGuestFlag(guest)
      if (this.user_id) {
        localStorage.setItem(SESSION_USER_ID_STORAGE_KEY, this.user_id)
      } else {
        localStorage.removeItem(SESSION_USER_ID_STORAGE_KEY)
      }
      this.hasHydrated = true
    },
    logout() {
      // Explicit sign-out (including "End preview"): never auto-restart a preview.
      this.lastSessionWasGuest = false
      this.forgetSession()
      this.hasHydrated = true
    },
    clearSession() {
      if (this.isGuest) this.lastSessionWasGuest = true
      this.forgetSession()
    },
    forgetSession() {
      this.user_id = null
      this.token = null
      this.isGuest = false
      setSessionToken(null)
      writeGuestFlag(false)
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
        const data = await apiJson<{ user_id: string; guest?: boolean }>('/api/users/me')
        this.user_id = data.user_id
        this.isGuest = !!data.guest
        writeGuestFlag(this.isGuest)
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
    async startGuestSession(seedHistory = true): Promise<void> {
      const data = await apiJson<{ user_id: string; token: string }>('/api/guest/session', {
        method: 'POST',
        body: { seed_history: seedHistory },
      })
      this.login(data.user_id, data.token, true)
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
