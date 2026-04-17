<script setup lang="ts">
/**
 * BlankSlot — replaces the inline `[＿＿＿]` marker in the verso prompt.
 *
 * Initial state: a faint underline placeholder (the visual blank).
 * Correct: indigo underline + correct answer in primary.
 * Incorrect: kohaku underline + struck-through user answer in secondary.
 */
withDefaults(
  defineProps<{
    state: "initial" | "correct" | "incorrect"
    userAnswer?: string
    correctAnswer?: string
  }>(),
  {
    userAnswer: "",
    correctAnswer: "",
  },
)
</script>

<template>
  <span
    class="blank-slot"
    :class="{
      'is-initial': state === 'initial',
      'is-correct': state === 'correct',
      'is-incorrect': state === 'incorrect',
    }"
  >
    <template v-if="state === 'correct'">{{ correctAnswer }}</template>
    <span v-else-if="state === 'incorrect'" class="strike">{{ userAnswer || '　' }}</span>
    <template v-else>　</template>
  </span>
</template>

<style scoped>
.blank-slot {
  display: inline-block;
  min-width: 2.4em;
  text-align: center;
  font-family: var(--font-serif);
  position: relative;
  margin-bottom: 4px;
}
.blank-slot.is-initial {
  color: transparent;
  border-bottom: 2px solid color-mix(in oklab, var(--foreground) 35%, transparent);
}
.blank-slot.is-correct {
  color: var(--primary);
  border-bottom: 2px solid var(--primary);
}
.blank-slot.is-incorrect {
  color: var(--secondary);
  border-bottom: 2px solid var(--secondary);
}
.blank-slot .strike {
  text-decoration: line-through;
  text-decoration-color: var(--secondary);
  text-decoration-thickness: 2px;
}
</style>
