<script setup lang="ts">
/**
 * HankoSeal — a miniature "signature stamp" in Beni Red.
 *
 * Per design doc §5 & §6, the hanko (and its paired `tertiary`/Beni colour)
 * is reserved for signature / finality moments — "Lesson Complete",
 * "Mastered", a correct answer. Pair the visual with a readable label for
 * accessibility (§6 — state cues must not rely on a single visual signal).
 */
import { computed } from "vue"

const props = withDefaults(
  defineProps<{
    /** Text inside the seal. For CJK, stacks vertically if ≤ 3 chars. */
    label: string
    /** Optional accessible label override (defaults to `label`). */
    ariaLabel?: string
    /** Rotation in degrees — a slight tilt reads as a real stamp. */
    rotation?: number
    /** Pixel size of the stamp. */
    size?: number
  }>(),
  {
    rotation: -3,
    size: 56,
  },
)

const isShortCjk = computed(() => props.label.length <= 3 && /[\u3040-\u30FF\u4E00-\u9FFF]/.test(props.label))

const style = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  transform: `rotate(${props.rotation}deg)`,
}))
</script>

<template>
  <span
    class="inline-flex items-center justify-center rounded-md border-2 border-destructive text-destructive font-serif font-semibold select-none shrink-0"
    :style="style"
    role="img"
    :aria-label="ariaLabel ?? label"
  >
    <span
      v-if="isShortCjk"
      class="flex flex-col items-center justify-center leading-[1.05] text-[0.9rem]"
      aria-hidden="true"
    >
      <span v-for="(ch, i) in label.split('')" :key="i">{{ ch }}</span>
    </span>
    <span v-else class="text-[0.7rem] uppercase tracking-[0.1em]" aria-hidden="true">{{ label }}</span>
  </span>
</template>
