<script setup lang="ts">
/**
 * MarginNote — the "editor's margin correction" slot.
 *
 * Per design doc §5, AI corrections should appear as italic Inter at 80%
 * opacity, aligned straight (no rotation — rotation is reserved for the
 * Tutor's Letter in the daily review). On desktop the note sits alongside
 * the content with a soft kohaku hairline; on narrow viewports it flips
 * below with a top hairline so rhythm is preserved.
 */
</script>

<template>
  <aside
    class="font-sans italic text-sm text-foreground/80 leading-relaxed
           border-t border-secondary/40 pt-3 mt-3
           md:border-t-0 md:pt-0 md:mt-0
           md:border-l md:border-secondary/40 md:pl-6"
  >
    <slot />
  </aside>
</template>
