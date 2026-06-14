<script setup lang="ts">
// Practice hub. Hosts two decks:
//   • exam    — the 1142 final-exam MCQ bank (選択問題, verified vs the green-book
//               keys p.284/p.295). The urgent, primary deck.
//   • lessons — the per-lesson fill-blank / vocab drills (the original practice).
// The chosen deck persists across visits.
import { ref, watch } from 'vue';

import ExamDrill from './ExamDrill.vue';
import LessonDrill from './LessonDrill.vue';

type Deck = 'exam' | 'lessons';
const STORAGE_KEY = 'shiori.practice.deck';

function readDeck(): Deck {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'lessons' ? 'lessons' : 'exam';
  } catch {
    return 'exam';
  }
}

const deck = ref<Deck>(readDeck());

watch(deck, (v) => {
  try {
    localStorage.setItem(STORAGE_KEY, v);
  } catch {
    /* storage may be unavailable (private mode) — non-fatal */
  }
});
</script>

<template>
  <div class="practice-root">
    <nav class="deck-switch" :aria-label="$t('practice.deck_label')">
      <button
        type="button"
        class="deck-tab"
        :class="{ 'is-active': deck === 'exam' }"
        :aria-pressed="deck === 'exam'"
        @click="deck = 'exam'"
      >
        {{ $t('practice.deck_exam') }}
      </button>
      <button
        type="button"
        class="deck-tab"
        :class="{ 'is-active': deck === 'lessons' }"
        :aria-pressed="deck === 'lessons'"
        @click="deck = 'lessons'"
      >
        {{ $t('practice.deck_lessons') }}
      </button>
    </nav>

    <ExamDrill v-if="deck === 'exam'" />
    <LessonDrill v-else />
  </div>
</template>

<style scoped>
.practice-root {
  display: flex;
  flex-direction: column;
}
.deck-switch {
  display: flex;
  justify-content: center;
  gap: 36px;
  padding: 18px 32px 0;
  background: var(--background);
}
.deck-tab {
  font-family: var(--font-serif);
  font-size: 1.05rem;
  color: color-mix(in oklab, var(--foreground) 52%, transparent);
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px 2px 10px;
  border-bottom: 2px solid transparent;
  transition: color 160ms ease, border-color 160ms ease;
}
.deck-tab:hover {
  color: var(--foreground);
}
.deck-tab.is-active {
  color: var(--primary);
  border-bottom-color: var(--secondary);
  font-weight: 500;
}
@media (max-width: 560px) {
  .deck-switch { gap: 24px; padding: 14px 18px 0; }
  .deck-tab { font-size: 0.98rem; }
}
</style>
