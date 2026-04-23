<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useAuthStore } from '../stores/auth';

import AuthLayout from '../components/AuthLayout.vue';

const { t } = useI18n();
const router = useRouter();
const auth = useAuthStore();

const username = ref('');
const password = ref('');
const error = ref('');
const isSubmitting = ref(false);

const usernameFocused = ref(false);
const passwordFocused = ref(false);

async function login() {
  if (isSubmitting.value) return;
  error.value = '';
  isSubmitting.value = true;
  try {
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/users/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value, password: password.value }),
    });
    const data = await res.json();
    if (res.ok) {
      auth.login(data.user_id);
      router.push('/');
    } else {
      error.value = data.error || t('auth.error_generic');
    }
  } catch (err) {
    error.value = t('auth.error_generic');
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <AuthLayout :eyebrow="$t('auth.eyebrow_return')">
    <h2 class="auth-heading">
      {{ $t('auth.welcome_back') }}
      <span class="emphasis">{{ $t('auth.welcome_back_emphasis') }}</span>{{ $t('auth.welcome_back_suffix') }}
    </h2>
    <p class="auth-sub">{{ $t('auth.login_sub') }}</p>

    <form class="auth-form" @submit.prevent="login">
      <div
        class="auth-field"
        :class="{ 'is-active': usernameFocused || username.length > 0, 'is-focused': usernameFocused }"
      >
        <label for="login-username" class="auth-field-label">
          {{ $t('auth.username') }}
        </label>
        <input
          id="login-username"
          v-model="username"
          class="auth-field-input"
          type="text"
          autocomplete="username"
          :placeholder="usernameFocused ? $t('auth.username_placeholder') : ''"
          @focus="usernameFocused = true"
          @blur="usernameFocused = false"
        />
      </div>

      <div
        class="auth-field"
        :class="{ 'is-active': passwordFocused || password.length > 0, 'is-focused': passwordFocused }"
      >
        <label for="login-password" class="auth-field-label">
          {{ $t('auth.password') }}
        </label>
        <input
          id="login-password"
          v-model="password"
          class="auth-field-input"
          type="password"
          autocomplete="current-password"
          :placeholder="passwordFocused ? $t('auth.password_placeholder') : ''"
          @focus="passwordFocused = true"
          @blur="passwordFocused = false"
        />
      </div>

      <button
        type="submit"
        class="auth-cta"
        :disabled="isSubmitting || !username.trim() || !password"
      >
        {{ $t('auth.login_cta') }}
        <svg width="14" height="10" viewBox="0 0 14 10" aria-hidden="true">
          <path
            d="M1 5 H12 M8 1 L12 5 L8 9"
            stroke="currentColor"
            stroke-width="1.4"
            fill="none"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>

      <p v-if="error" class="auth-error" role="alert">{{ error }}</p>

      <div class="auth-divider" aria-hidden="true">
        <span class="auth-divider-rule" />
        <span class="auth-divider-word">{{ $t('common.divider_or') }}</span>
        <span class="auth-divider-rule" />
      </div>

      <div class="auth-toggle">
        <span>{{ $t('auth.no_account_line') }}</span>
        <router-link to="/register" class="auth-toggle-link">
          {{ $t('auth.to_register') }} →
        </router-link>
      </div>
    </form>
  </AuthLayout>
</template>

<!--
  All shared auth form styles (.auth-heading, .auth-field*, .auth-cta,
  .auth-divider*, .auth-toggle*) live globally in styles/auth.css.
  LoginView has no view-specific styles worth adding a scoped block for.
-->
