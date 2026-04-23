import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

export { default as Card } from "./Card.vue"
export { default as CardContent } from "./CardContent.vue"
export { default as CardDescription } from "./CardDescription.vue"
export { default as CardFooter } from "./CardFooter.vue"
export { default as CardHeader } from "./CardHeader.vue"
export { default as CardTitle } from "./CardTitle.vue"

/**
 * Editorial Intelligence — tiered "sheet of paper" card.
 * Tonal layering is the primary structural signal (design doc §2).
 * Borders are omitted by default; consumers can opt into `border border-border`
 * via the class prop when accessibility needs a hairline.
 */
export const cardVariants = cva("text-card-foreground", {
  variants: {
    tier: {
      lowest: "bg-surface-container-lowest",
      low: "bg-surface-container-low",
      default: "bg-surface-container",
      high: "bg-surface-container-high",
      highest: "bg-surface-container-highest",
    },
    padding: {
      none: "",
      sm: "p-4",
      md: "p-6",
      lg: "p-8 md:p-10",
    },
    radius: {
      none: "rounded-none",
      md: "rounded-md",
      lg: "rounded-lg",
      xl: "rounded-xl",
    },
  },
  defaultVariants: {
    tier: "default",
    padding: "md",
    radius: "lg",
  },
})

export type CardVariants = VariantProps<typeof cardVariants>
