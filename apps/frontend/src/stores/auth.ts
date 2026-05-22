import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user_id: null as string | null,
  }),
  getters: {
    isAuthenticated: (state) => state.user_id !== null,
    scopedStorageKey: (state) => (key: string) => {
      return state.user_id ? `${key}:${state.user_id}` : `${key}:anonymous`;
    },
  },
  actions: {
    login(userId: unknown) {
      this.user_id = userId === null || userId === undefined ? null : String(userId)
    },
    logout() {
      this.user_id = null
    },
    requireUserId(): string {
      if (!this.user_id) {
        throw new Error('A logged-in user is required for this action')
      }
      return this.user_id
    },
  },
})
