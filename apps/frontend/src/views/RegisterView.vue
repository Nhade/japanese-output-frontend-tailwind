<template>
  <main class="grid min-h-[calc(100vh-4rem)] place-items-center px-4 text-zinc-900 dark:text-zinc-100">
    <section
      class="w-full max-w-md rounded-2xl border p-6 shadow-xl bg-white border-zinc-200 shadow-zinc-200/50 dark:bg-zinc-900/60 dark:border-white/5 dark:shadow-black/30">
      <div class="mb-6 flex items-center gap-2">
        <div
          class="inline-flex h-9 w-9 items-center justify-center rounded-lg font-bold bg-emerald-50 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-300">
          O</div>
        <h1 class="text-lg font-semibold">{{ $t('auth.register_title') }}</h1>
      </div>
      <form @submit.prevent="register" class="space-y-4">
        <div>
          <label class="mb-1 block text-sm text-zinc-700 dark:text-zinc-300">{{ $t('auth.username') }}</label>
          <input v-model="username"
            class="w-full rounded-xl px-4 py-3 text-base outline-none focus:ring-2 border shadow-inner transition-all bg-white text-zinc-900 border-zinc-200 placeholder-zinc-400 focus:ring-emerald-500/40 dark:bg-zinc-800 dark:text-white dark:border-white/10 dark:placeholder-zinc-500 dark:focus:ring-emerald-400"
            :placeholder="$t('auth.username_placeholder')" />
        </div>
        <div>
          <label class="mb-1 block text-sm text-zinc-700 dark:text-zinc-300">{{ $t('auth.password') }}</label>
          <input v-model="password" type="password"
            class="w-full rounded-xl px-4 py-3 text-base outline-none focus:ring-2 border shadow-inner transition-all bg-white text-zinc-900 border-zinc-200 placeholder-zinc-400 focus:ring-emerald-500/40 dark:bg-zinc-800 dark:text-white dark:border-white/10 dark:placeholder-zinc-500 dark:focus:ring-emerald-400"
            :placeholder="$t('auth.create_password_placeholder')" />
        </div>
        <button type="submit"
          class="w-full rounded-xl px-4 py-2.5 font-medium shadow-lg transition-all active:scale-95 bg-gradient-to-br from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 text-white dark:from-emerald-500 dark:to-emerald-600 dark:hover:from-emerald-400 dark:hover:to-emerald-500">{{
            $t('auth.register_button') }}</button>
      </form>
      <p v-if="error" class="mt-4 text-center text-sm text-red-400">{{ error }}</p>
      <p v-if="message" class="mt-4 text-center text-sm text-emerald-700 dark:text-emerald-400">{{ message }}</p>
      <p class="mt-4 text-center text-sm text-zinc-600 dark:text-zinc-400">{{ $t('auth.has_account') }}
        <router-link to="/login" class="text-emerald-700 hover:underline dark:text-emerald-300">{{ $t('auth.login_link')
          }}</router-link>
      </p>
    </section>
  </main>
</template>

<script setup>
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
const username = ref('');
const password = ref('');
const error = ref('');
const message = ref('');

const register = async () => {
  try {
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/users/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value, password: password.value })
    });
    const data = await response.json();
    if (response.ok) {
      message.value = data.message;
      error.value = '';
    } else {
      error.value = data.error;
      message.value = '';
    }
  } catch (err) {
    error.value = t('auth.error_generic');
    message.value = '';
  }
};
</script>