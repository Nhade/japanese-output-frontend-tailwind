<script setup lang="ts">
import type { HTMLAttributes } from "vue"
import { useVModel } from "@vueuse/core"
import { cn } from "@/lib/utils"

const props = defineProps<{
  defaultValue?: string | number
  modelValue?: string | number
  class?: HTMLAttributes["class"]
}>()

const emits = defineEmits<{
  (e: "update:modelValue", payload: string | number): void
}>()

const modelValue = useVModel(props, "modelValue", emits, {
  passive: true,
  defaultValue: props.defaultValue,
})
</script>

<template>
  <input
    v-model="modelValue"
    :class="cn(
      // Editorial Intelligence — minimalist bottom-line input (design doc §5).
      // No full box; just an underline that thickens & shifts to primary on focus.
      'w-full bg-transparent border-0 border-b border-input rounded-none px-0 py-2 font-sans text-lg text-foreground placeholder:text-foreground/40 focus:outline-none focus:border-b-2 focus:border-primary transition-[border-color,border-width] duration-200 disabled:cursor-not-allowed disabled:opacity-50',
      props.class,
    )"
  >
</template>
