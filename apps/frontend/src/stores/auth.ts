import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user_id: null,
  }),
  actions: {
    login(user_id: any) {
      this.user_id = user_id
    },
    logout() {
      this.user_id = null
    },
  },
})
