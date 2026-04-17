import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

export { default as Button } from "./Button.vue"

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline:
          "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
        /**
         * Editorial Intelligence — Shiori (bookmark) primary CTA.
         * Vertical-ish ribbon: square top, rounded bottom; slides down on hover
         * as if being tucked into the page. Uses Ai Indigo gradient.
         */
        shiori:
          "relative inline-flex flex-col items-center justify-center gap-1 bg-gradient-to-b from-primary to-primary-container text-primary-foreground font-sans uppercase tracking-[0.18em] text-xs px-6 py-3 rounded-t-none rounded-b-md shadow-[0_4px_0_0_color-mix(in_oklab,var(--primary)_15%,transparent)] transition-transform duration-200 hover:translate-y-1 hover:shadow-[0_0_0_0_transparent] focus-visible:ring-2 focus-visible:ring-ring",
        /**
         * Editorial Intelligence — secondary/tertiary editorial action.
         * Italic serif at a readable size with a firm kohaku underline.
         * Text shifts to indigo primary on hover for explicit pressable
         * feedback — underline-only hover was too quiet.
         */
        "ghost-serif":
          "font-serif italic text-base text-foreground underline decoration-secondary decoration-[3px] underline-offset-[6px] hover:text-primary hover:decoration-primary focus-visible:ring-2 focus-visible:ring-ring bg-transparent px-1 py-1 rounded-sm transition-colors",
      },
      size: {
        "default": "h-9 px-4 py-2",
        "xs": "h-7 rounded px-2",
        "sm": "h-8 rounded-md px-3 text-xs",
        "lg": "h-10 rounded-md px-8",
        "icon": "h-9 w-9",
        "icon-sm": "size-8",
        "icon-lg": "size-10",
        // Intrinsic sizing used by shiori/ghost-serif (they set their own padding).
        "auto": "h-auto",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
)

export type ButtonVariants = VariantProps<typeof buttonVariants>
