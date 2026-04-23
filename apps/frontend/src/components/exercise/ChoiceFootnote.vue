<script setup lang="ts">
/**
 * ChoiceFootnote — a single MCQ row in Variation B's "Footnotes" list.
 *
 * Indexed by katakana (ア・イ・ウ・エ) in the left rail; the kanji choice
 * sits in the main column; a "Selected" eyebrow appears in the right tail.
 * The selection dot is positioned in the absolute left margin (-22px), so it
 * reads as a proofreader's mark rather than inline UI chrome.
 */
const KATAKANA = ["ア", "イ", "ウ", "エ"] as const

defineProps<{
  choice: string
  index: number
  selected: boolean
  selectedLabel: string
}>()

const emit = defineEmits<{
  (e: "select"): void
}>()
</script>

<template>
  <li class="footnote-row">
    <span aria-hidden="true" class="margin-dot" :class="{ 'is-on': selected }" />
    <button
      type="button"
      class="footnote-button"
      :class="{ 'is-selected': selected }"
      :aria-pressed="selected"
      @click="emit('select')"
    >
      <span class="label" :class="{ 'is-selected': selected }">
        {{ KATAKANA[index] || "" }}.
      </span>
      <span lang="ja" class="choice" :class="{ 'is-selected': selected }">
        {{ choice }}
      </span>
      <span class="selected-eyebrow" :class="{ 'is-on': selected }">
        {{ selectedLabel }}
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
  transition: opacity 180ms ease;
  pointer-events: none;
}
.margin-dot.is-on {
  opacity: 1;
}
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
  padding-left: 0;
  transition: padding-left 180ms ease;
  font-family: inherit;
}
.footnote-button.is-selected {
  padding-left: 10px;
}
.footnote-button:focus-visible {
  outline: 2px solid var(--ring);
  outline-offset: 4px;
  border-radius: 4px;
}
.label {
  font-family: var(--font-sans);
  font-size: 0.78rem;
  letter-spacing: 0.16em;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
  transition: color 180ms ease;
}
.label.is-selected {
  color: var(--secondary);
}
.choice {
  font-family: var(--font-serif);
  font-size: 1.65rem;
  color: var(--foreground);
  font-weight: 400;
  transition: color 180ms ease, font-weight 180ms ease;
  line-height: 1.3;
}
.choice.is-selected {
  color: var(--primary);
  font-weight: 500;
}
.selected-eyebrow {
  font-family: var(--font-sans);
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--primary);
  opacity: 0;
  transition: opacity 180ms ease;
}
.selected-eyebrow.is-on {
  opacity: 1;
}
@media (prefers-reduced-motion: reduce) {
  .margin-dot,
  .footnote-button,
  .label,
  .choice,
  .selected-eyebrow {
    transition: none;
  }
}
</style>
