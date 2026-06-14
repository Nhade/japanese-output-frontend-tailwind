<script setup lang="ts">
/**
 * ChoiceFootnote — a single MCQ row in the "Footnotes" list.
 *
 * Indexed by katakana (ア・イ・ウ・エ) in the left rail; the kanji choice sits
 * in the main column; a status eyebrow appears in the right tail. The margin
 * dot sits in the absolute left margin (-22px), so it reads as a proofreader's
 * mark rather than inline UI chrome.
 *
 * Selection is signalled by a background shift + left ink-rule (design doc
 * §Cards & Lists — the background shift is the primary cue, never the dot
 * alone), reinforced by the amber margin dot, amber index and indigo choice.
 *
 * Optional post-submit result states (`result`) let drill views keep the list
 * visible and mark the correct / wrongly-picked rows. ExerciseView omits them
 * (it swaps the list for a feedback panel), so its only visible change is the
 * stronger selected treatment shared here.
 */
const KATAKANA = ["ア", "イ", "ウ", "エ"] as const

withDefaults(
  defineProps<{
    choice: string
    index: number
    selected: boolean
    selectedLabel: string
    result?: "correct" | "incorrect" | null
    resultLabel?: string
    disabled?: boolean
    /** Language of the choice text — `ja` by default; pass `zh-Hant` for
     *  Chinese choices (e.g. vocab-meaning options) so glyphs render correctly. */
    lang?: string
  }>(),
  { result: null, resultLabel: "", disabled: false, lang: "ja" },
)

const emit = defineEmits<{
  (e: "select"): void
}>()
</script>

<template>
  <li class="footnote-row">
    <span
      aria-hidden="true"
      class="margin-dot"
      :class="{ 'is-on': selected, 'is-correct': result === 'correct', 'is-wrong': result === 'incorrect' }"
    />
    <button
      type="button"
      class="footnote-button"
      :class="{ 'is-selected': selected, 'is-correct': result === 'correct', 'is-wrong': result === 'incorrect' }"
      :aria-pressed="selected"
      :disabled="disabled"
      @click="emit('select')"
    >
      <span
        class="label"
        :class="{ 'is-selected': selected, 'is-correct': result === 'correct', 'is-wrong': result === 'incorrect' }"
      >
        {{ KATAKANA[index] || "" }}.
      </span>
      <span
        :lang="lang"
        class="choice"
        :class="{ 'is-selected': selected, 'is-correct': result === 'correct', 'is-wrong': result === 'incorrect' }"
      >
        {{ choice }}
      </span>
      <span
        class="tail-eyebrow"
        :class="{ 'is-on': selected || result === 'correct' }"
      >
        {{ result === 'correct' ? resultLabel : (result === null && selected ? selectedLabel : '') }}
      </span>
    </button>
  </li>
</template>

<style scoped>
.footnote-row {
  position: relative;
  list-style: none;
}
.margin-dot {
  position: absolute;
  left: -22px;
  top: 50%;
  transform: translateY(-50%);
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--secondary);
  opacity: 0;
  transition: opacity 180ms ease, background 180ms ease;
  pointer-events: none;
}
.margin-dot.is-on { opacity: 1; }
.margin-dot.is-correct { opacity: 1; background: var(--primary); }
.margin-dot.is-wrong { opacity: 1; background: var(--destructive); }

.footnote-button {
  display: grid;
  grid-template-columns: 32px 1fr auto;
  align-items: center;
  gap: 18px;
  width: 100%;
  padding: 18px 0;
  border: none;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 12%, transparent);
  background: transparent;
  text-align: left;
  cursor: pointer;
  border-radius: 4px;
  transition: padding 180ms ease, background 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
  font-family: inherit;
}
.footnote-button:disabled { cursor: default; }
.footnote-button:focus-visible {
  outline: 2px solid var(--ring);
  outline-offset: 4px;
}

/* Selected (pre-submit) — background shift is the primary cue, with a left
   ink-rule and the amber dot/index as reinforcement. */
.footnote-button.is-selected {
  padding: 18px 14px 18px 16px;
  background: color-mix(in oklab, var(--secondary) 12%, transparent);
  box-shadow: inset 3px 0 0 0 var(--secondary);
  border-bottom-color: transparent;
}
/* Post-submit results (drill views only). */
.footnote-button.is-correct {
  padding: 18px 14px 18px 16px;
  background: color-mix(in oklab, var(--primary) 10%, transparent);
  box-shadow: inset 3px 0 0 0 var(--primary);
  border-bottom-color: transparent;
}
.footnote-button.is-wrong {
  padding: 18px 14px 18px 16px;
  background: color-mix(in oklab, var(--destructive) 8%, transparent);
  box-shadow: inset 3px 0 0 0 var(--destructive);
  border-bottom-color: transparent;
}

.label {
  font-family: var(--font-sans);
  font-size: 0.78rem;
  letter-spacing: 0.16em;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
  transition: color 180ms ease;
}
.label.is-selected { color: var(--secondary); }
.label.is-correct { color: var(--primary); }
.label.is-wrong { color: var(--destructive); }

.choice {
  font-family: var(--font-serif);
  font-size: 1.65rem;
  color: var(--foreground);
  font-weight: 400;
  transition: color 180ms ease, font-weight 180ms ease;
  line-height: 1.3;
}
.choice.is-selected { color: var(--primary); font-weight: 500; }
.choice.is-correct { color: var(--primary); font-weight: 500; }
.choice.is-wrong {
  color: var(--destructive);
  text-decoration: line-through;
  text-decoration-thickness: 2px;
  text-decoration-color: color-mix(in oklab, var(--destructive) 70%, transparent);
}

.tail-eyebrow {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--primary);
  opacity: 0;
  transition: opacity 180ms ease;
  white-space: nowrap;
}
.tail-eyebrow.is-on { opacity: 1; }

@media (prefers-reduced-motion: reduce) {
  .margin-dot,
  .footnote-button,
  .label,
  .choice,
  .tail-eyebrow {
    transition: none;
  }
}
</style>
