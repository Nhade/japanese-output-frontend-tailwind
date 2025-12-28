import { createRouter, createWebHistory } from 'vue-router'
import ExerciseView from '../views/ExerciseView.vue'
import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import MistakesView from '../views/MistakesView.vue'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'exercise',
      component: ExerciseView,
      meta: { requiresAuth: true }
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView
    },
    {
      path: '/register',
      name: 'register',
      component: RegisterView
    },
    {
      path: '/mistakes',
      name: 'mistakes',
      component: MistakesView,
      meta: { requiresAuth: true }
    },
    {
      path: '/statistics',
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
    }
  ]
})

router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()
  const isLoggedIn = authStore.user_id !== null

  if (to.meta.requiresAuth && !isLoggedIn) {
    next({ name: 'login' })
  } else {
    next()
  }
})

export default router