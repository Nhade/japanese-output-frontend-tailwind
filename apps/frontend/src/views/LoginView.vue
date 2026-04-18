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
        <span class="auth-divider-word">or</span>
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

<style scoped>
.auth-heading {
  font-family: var(--font-serif);
  font-size: clamp(34px, 2.5vw + 1.4rem, 44px);
  line-height: 1.05;
  font-weight: 500;
  margin: 0 0 12px 0;
  letter-spacing: -0.015em;
  color: var(--foreground);
}
.auth-heading .emphasis {
  font-style: italic;
  color: var(--secondary);
}
.auth-sub {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 15px;
  color: color-mix(in oklab, var(--foreground) 62%, transparent);
  margin: 0 0 36px 0;
  line-height: 1.6;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

/* Underline field w/ floating margin label ------------------- */
.auth-field {
  position: relative;
  padding-top: 18px;
}
.auth-field-label {
  position: absolute;
  left: 0;
  top: 24px;
  font-family: var(--font-sans);
  font-size: 14px;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  pointer-events: none;
  transition: top 200ms ease, font-size 200ms ease, color 200ms ease, letter-spacing 200ms ease;
}
.auth-field.is-active .auth-field-label {
  top: 0;
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 600;
}
.auth-field.is-focused .auth-field-label {
  color: var(--primary);
}
.auth-field-input {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 0;
  font-family: var(--font-serif);
  font-size: 16px;
  color: var(--foreground);
  background: transparent;
  border: none;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 20%, transparent);
  outline: none;
  transition: border-color 180ms ease;
}
.auth-field.is-focused .auth-field-input {
  border-bottom-color: var(--primary);
  border-bottom-width: 2px;
  padding-bottom: 7px;
}
.auth-field-input::placeholder {
  color: color-mix(in oklab, var(--foreground) 35%, transparent);
  font-style: italic;
}

/* CTA -------------------------------------------------------- */
.auth-cta {
  margin-top: 8px;
  width: 100%;
  padding: 14px 20px;
  font-family: var(--font-sans);
  font-size: 12px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  font-weight: 600;
  color: var(--background);
  background: linear-gradient(180deg, var(--primary) 0%, var(--primary-container) 100%);
  border: none;
  border-radius: 2px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  transition: transform 180ms ease, box-shadow 180ms ease, opacity 180ms ease;
  box-shadow: 0 2px 0 color-mix(in oklab, var(--primary) 16%, transparent);
}
.auth-cta:hover:not(:disabled) {
  transform: translateY(3px);
  box-shadow: 0 8px 24px color-mix(in oklab, var(--primary) 22%, transparent);
}
.auth-cta:active:not(:disabled) {
  transform: translateY(2px);
}
.auth-cta:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.auth-error {
  margin: 0;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 14px;
  color: var(--destructive);
}

.auth-divider {
  display: flex;
  align-items: center;
  gap: 14px;
  font-family: var(--font-sans);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 40%, transparent);
  font-weight: 600;
  margin: 4px 0;
}
.auth-divider-rule {
  flex: 1;
  height: 1px;
  background: color-mix(in oklab, var(--foreground) 12%, transparent);
}

.auth-toggle {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 14px;
  font-family: var(--font-serif);
  font-size: 14px;
  color: color-mix(in oklab, var(--foreground) 62%, transparent);
}
.auth-toggle-link {
  font-family: var(--font-sans);
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 600;
  color: var(--primary);
  border-bottom: 1px solid var(--primary);
  padding: 2px 0;
  text-decoration: none;
  transition: border-color 160ms ease, color 160ms ease;
}
.auth-toggle-link:hover {
  color: var(--primary-container);
  border-bottom-color: var(--secondary);
}
</style>
