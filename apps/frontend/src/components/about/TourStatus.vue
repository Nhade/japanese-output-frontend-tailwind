<script setup lang="ts">
// Says the tour is still running while it has nothing else on screen:
// between pages, or while a dialog it opened (review, explanation) is up.
import { useTourStore } from '../../stores/tour';

const tour = useTourStore();
</script>

<template>
  <div role="status" class="tour-status-region">
    <p v-if="tour.active && tour.pending" class="tour-status">
      {{ $t(`tour.status.${tour.pending}`) }}
    </p>
  </div>
</template>

<style scoped>
.tour-status {
  position: fixed;
  z-index: 70;
  left: 16px;
  bottom: calc(var(--bottomnav-h) + 16px);
  max-width: min(360px, calc(100vw - 32px));
  margin: 0;
  padding: 10px 14px;
  font-family: var(--font-sans);
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--foreground);
  background: var(--surface-container-lowest);
  border: 1px solid color-mix(in oklab, var(--foreground) 12%, transparent);
  border-left: 3px solid var(--secondary);
  box-shadow: 0 12px 32px -16px color-mix(in oklab, var(--foreground) 30%, transparent);
  pointer-events: none;
}
</style>
