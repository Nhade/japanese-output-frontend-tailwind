<script setup>
import TheHeader from './components/TheHeader.vue';
import TheFooter from './components/TheFooter.vue';
</script>

<template>
  <div id="app-container overscroll-contain">
    <TheHeader />
    <main class="main-content h-screen bg-zinc-950">
      <router-view />
    </main>
    <TheFooter />
  </div>
</template>

<style>
</style>