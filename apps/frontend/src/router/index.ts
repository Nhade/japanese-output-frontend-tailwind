import { createRouter, createWebHistory } from 'vue-router'
import ExerciseView from '../views/ExerciseView.vue'
import TodayView from '../views/TodayView.vue'
import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import MistakesView from '../views/MistakesView.vue'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'today',
      component: TodayView,
      meta: { requiresAuth: true }
    },
    {
      path: '/study/exercise',
      alias: '/exercise',
      name: 'exercise',
      component: ExerciseView,
      meta: { requiresAuth: true }
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { hideChrome: true }
    },
    {
      path: '/register',
      name: 'register',
      component: RegisterView,
      meta: { hideChrome: true }
    },
    {
      path: '/mistakes',
      alias: '/progress/mistakes',
      name: 'mistakes',
      component: MistakesView,
      meta: { requiresAuth: true }
    },
    {
      path: '/statistics',
      alias: '/progress/statistics',
      name: 'statistics',
      component: () => import('../views/StatisticsView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/news',
      name: 'news-list',
      component: () => import('../views/NewsListView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/videos',
      name: 'video-list',
      component: () => import('../views/VideoListView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/videos/:id',
      name: 'video-study',
      component: () => import('../views/VideoStudyView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('../views/ChatView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/news/:id',
      name: 'news-reader',
      component: () => import('../views/NewsReaderView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/practice',
      alias: '/study/practice',
      name: 'practice',
      component: () => import('../views/PracticeView.vue'),
      meta: { requiresAuth: true }
    },
    {
      // Public entry for the guest preview (linked from outside). Mints a
      // guest session and forwards to Today; see PreviewEntryView.
      path: '/preview',
      name: 'preview',
      component: () => import('../views/PreviewEntryView.vue'),
      meta: { hideChrome: true }
    }
  ]
})

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.hasHydrated) {
    await authStore.hydrateSession()
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    // A guest whose preview expired gets a fresh one; everyone else signs in.
    next(authStore.lastSessionWasGuest ? { name: 'preview', query: { expired: '1' } } : { name: 'login' })
  } else {
    next()
  }
})

export default router
