<script setup lang="ts">
/**
 * SegmentedToggle — editorial mode switcher.
 *
 * A thin wrapper over reka-ui's ToggleGroup that renders options as
 * small-caps Inter labels with an underline indicator for the active
 * option. No pill, no fill — per design doc §6 ("No standard progress
 * bars / toy bubbliness"): discreet, editorial, paper-first.
 */
import type { AcceptableValue } from "reka-ui"
import { ToggleGroupItem, ToggleGroupRoot } from "reka-ui"
import { cn } from "@/lib/utils"

interface Option {
  value: string
  label: string
}

const props = defineProps<{
  modelValue: string
  options: Option[]
  class?: string
}>()

const emits = defineEmits<{
  (e: "update:modelValue", value: string): void
}>()

function onUpdate(value: AcceptableValue | AcceptableValue[]) {
  // Single-select mode — reka emits a single value or undefined on deselect.
  if (typeof value === "string" && value && value !== props.modelValue) {
    emits("update:modelValue", value)
  }
}
</script>

<template>
  <ToggleGroupRoot
    type="single"
    :model-value="modelValue"
    @update:model-value="onUpdate"
    :class="cn('inline-flex items-center gap-6', props.class)"
  >
    <ToggleGroupItem
      v-for="opt in options"
      :key="opt.value"
      :value="opt.value"
      class="font-sans uppercase tracking-[0.22em] text-xs py-2
             text-foreground/55 hover:text-foreground
             border-b-2 border-transparent hover:border-secondary/40
             data-[state=on]:text-foreground data-[state=on]:font-medium
             data-[state=on]:border-b-[3px] data-[state=on]:border-primary
             focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
             transition-colors"
    >
      {{ opt.label }}
    </ToggleGroupItem>
  </ToggleGroupRoot>
</template>
