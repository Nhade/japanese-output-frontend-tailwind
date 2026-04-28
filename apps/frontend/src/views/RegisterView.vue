<script setup lang="ts">
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';

import AuthLayout from '../components/AuthLayout.vue';
import { apiUrl } from '../lib/api';

const { t } = useI18n();

const username = ref('');
const password = ref('');
const error = ref('');
const message = ref('');
const isSubmitting = ref(false);

const usernameFocused = ref(false);
const passwordFocused = ref(false);

// Passphrase strength — 0 (none) .. 4 (masterful). The labels mirror
// the mock's editorial scale ("Fragile" → "Masterful").
const strengthScore = computed<number>(() => {
  const v = password.value;
  if (!v) return 0;
  let s = 0;
  if (v.length >= 8) s += 1;
  if (/[A-Z]/.test(v)) s += 1;
  if (/\d/.test(v)) s += 1;
  if (/[^A-Za-z0-9]/.test(v)) s += 1;
  if (v.length >= 14) s += 1;
  return Math.min(s, 4);
});

const strengthLabel = computed<string>(() => {
  if (!password.value) return t('auth.strength_empty');
  return t(`auth.strength_${strengthScore.value || 1}`);
});

async function register() {
  if (isSubmitting.value) return;
  error.value = '';
  message.value = '';
  isSubmitting.value = true;
  try {
    const res = await fetch(`${apiUrl('/api/users/register')}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value, password: password.value }),
    });
    const data = await res.json();
    if (res.ok) {
      message.value = data.message;
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
  <AuthLayout :eyebrow="$t('auth.eyebrow_join')">
    <h2 class="auth-heading">
      {{ $t('auth.begin_habit_prefix') }}
      <span class="emphasis">{{ $t('auth.begin_habit_emphasis') }}</span>{{ $t('auth.begin_habit_suffix') }}
    </h2>
    <p class="auth-sub">{{ $t('auth.register_sub') }}</p>

    <form class="auth-form" @submit.prevent="register">
      <div
        class="auth-field"
        :class="{ 'is-active': usernameFocused || username.length > 0, 'is-focused': usernameFocused }"
      >
        <label for="reg-username" class="auth-field-label">
          {{ $t('auth.username') }}
        </label>
        <input
          id="reg-username"
          v-model="username"
          class="auth-field-input"
          type="text"
          autocomplete="username"
          :placeholder="usernameFocused ? $t('auth.username_placeholder') : ''"
          @focus="usernameFocused = true"
          @blur="usernameFocused = false"
        />
      </div>

      <div>
        <div
          class="auth-field"
          :class="{ 'is-active': passwordFocused || password.length > 0, 'is-focused': passwordFocused }"
        >
          <label for="reg-password" class="auth-field-label">
            {{ $t('auth.password') }}
          </label>
          <input
            id="reg-password"
            v-model="password"
            class="auth-field-input"
            type="password"
            autocomplete="new-password"
            :placeholder="passwordFocused ? $t('auth.create_password_placeholder') : ''"
            @focus="passwordFocused = true"
            @blur="passwordFocused = false"
          />
        </div>

        <!-- Ink-wash strength meter -->
        <div class="strength-meter">
          <div class="strength-bars" aria-hidden="true">
            <span
              v-for="i in 4"
              :key="i"
              class="strength-bar"
              :class="{ 'is-on': i <= strengthScore }"
            />
          </div>
          <div class="strength-row">
            <span>{{ $t('auth.strength_label') }}</span>
            <span
              class="strength-label"
              :class="{ 'is-strong': strengthScore >= 3 }"
            >
              {{ strengthLabel }}
            </span>
          </div>
        </div>
      </div>

      <p class="auth-margin-note">{{ $t('auth.register_legal') }}</p>

      <button
        type="submit"
        class="auth-cta"
        :disabled="isSubmitting || !username.trim() || !password"
      >
        {{ $t('auth.register_cta') }}
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
      <div v-if="message" class="auth-success" role="status">
        <p class="auth-success-text">{{ message }}</p>
        <router-link to="/login" class="auth-toggle-link">
          {{ $t('auth.register_success_cta') }} →
        </router-link>
      </div>

      <div class="auth-divider" aria-hidden="true">
        <span class="auth-divider-rule" />
        <span>{{ $t('common.divider_or') }}</span>
        <span class="auth-divider-rule" />
      </div>

      <div class="auth-toggle">
        <span>{{ $t('auth.has_account_line') }}</span>
        <router-link to="/login" class="auth-toggle-link">
          {{ $t('auth.to_login') }} →
        </router-link>
      </div>
    </form>
  </AuthLayout>
</template>

<style scoped>
/* Shared auth form atoms (.auth-heading, .auth-field*, .auth-cta,
   .auth-divider*, .auth-toggle*) are global — see styles/auth.css.
   The blocks below are register-only: strength meter, legal note and
   success block. */

/* Strength meter --------------------------------------------- */
.strength-meter {
  margin-top: 10px;
}
.strength-bars {
  display: flex;
  gap: 4px;
  height: 3px;
}
.strength-bar {
  flex: 1;
  background: color-mix(in oklab, var(--foreground) 9%, transparent);
  transition: background 240ms ease;
}
.strength-bar.is-on { background: var(--primary); }
.strength-row {
  margin-top: 6px;
  font-family: var(--font-sans);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  font-weight: 600;
  display: flex;
  justify-content: space-between;
}
.strength-label.is-strong { color: var(--primary); }

/* Margin note ------------------------------------------------ */
.auth-margin-note {
  margin: 0;
  padding-left: 12px;
  border-left: 1px solid color-mix(in oklab, var(--foreground) 10%, transparent);
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 13px;
  line-height: 1.65;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
}

/* Register-specific CTA override — sits closer to the margin note
   above (shared .auth-cta has a larger default top margin). */
.auth-cta { margin-top: 4px; }

.auth-success {
  padding: 14px 18px;
  background: var(--surface-container-low);
  border-left: 2px solid var(--secondary);
  border-radius: 0 3px 3px 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.auth-success-text {
  margin: 0;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 14px;
  color: color-mix(in oklab, var(--foreground) 75%, transparent);
  line-height: 1.6;
}

</style>
