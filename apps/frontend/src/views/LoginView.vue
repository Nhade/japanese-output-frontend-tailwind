<template>
  <main class="grid min-h-[calc(100vh-4rem)] place-items-center bg-zinc-950 px-4 text-zinc-100">
    <section class="w-full max-w-md rounded-2xl border border-white/5 bg-zinc-900/60 p-6 shadow-xl shadow-black/30">
      <div class="mb-6 flex items-center gap-2">
        <div class="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-300 font-bold">O</div>
        <h1 class="text-lg font-semibold">Login to OWO</h1>
      </div>
      <form @submit.prevent="login" class="space-y-4">
        <div>
          <label class="mb-1 block text-sm text-zinc-300" autocomplete="username">Username</label>
          <input v-model="username" class="w-full rounded-xl border border-white/10 bg-zinc-800 px-4 py-3 text-base text-white placeholder-zinc-500 outline-none focus:ring-2 focus:ring-emerald-400" placeholder="Your Username" />
        </div>
        <div>
          <label class="mb-1 block text-sm text-zinc-300">Password</label>
          <input v-model="password" type="password" class="w-full rounded-xl border border-white/10 bg-zinc-800 px-4 py-3 text-base text-white placeholder-zinc-500 outline-none focus:ring-2 focus:ring-emerald-400" placeholder="••••••••" />
        </div>
        <button type="submit" class="w-full rounded-xl bg-emerald-500 px-4 py-2.5 font-medium text-zinc-900 hover:bg-emerald-400">Login</button>
      </form>
      <p v-if="error" class="mt-4 text-center text-sm text-red-400">{{ error }}</p>
      <p class="mt-4 text-center text-sm text-zinc-400">Don’t have an account?
        <router-link to="/register" class="text-emerald-300 hover:underline">Register here</router-link>
      </p>
    </section>
  </main>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';

const username = ref('');
const password = ref('');
const error = ref('');
const router = useRouter();
const auth = useAuthStore();

const login = async () => {
  try {
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/users/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value, password: password.value })
    });
    const data = await response.json();
    if (response.ok) {
      auth.login(data.user_id);
      router.push('/');
    } else {
      error.value = data.error;
    }
  } catch (err) {
    error.value = 'An error occurred. Please try again.';
  }
};
</script>