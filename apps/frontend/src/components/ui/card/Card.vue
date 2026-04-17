<script setup lang="ts">
import type { HTMLAttributes } from "vue"
import type { CardVariants } from "."
import { cn } from "@/lib/utils"
import { cardVariants } from "."

const props = defineProps<{
  tier?: CardVariants["tier"]
  padding?: CardVariants["padding"]
  radius?: CardVariants["radius"]
  class?: HTMLAttributes["class"]
}>()
</script>

<template>
  <div
    :class="
      cn(
        cardVariants({ tier: props.tier, padding: props.padding, radius: props.radius }),
        props.class,
      )
    "
  >
    <slot />
  </div>
</template>
