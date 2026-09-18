import { defineStore } from 'pinia'
import { ref } from 'vue'

// Glue between the tour runner (lib/tour.ts) and the views. Views register
// small handlers ("answer the exercise wrongly", "send this chat message")
// while mounted; the tour runs them from its popovers so a visitor who does
// not read Japanese can still drive every feature.

export type TourActionHandler = (payload?: unknown) => Promise<void> | void

const ASSISTED_KEY = 'shiori.tour.assisted'

// Kept outside Pinia state on purpose: handlers are functions, not data.
const handlers = new Map<string, TourActionHandler>()

function readAssisted(): boolean {
  try {
    return localStorage.getItem(ASSISTED_KEY) === '1'
  } catch {
    return false
  }
}

export const useTourStore = defineStore('tour', () => {
  /** "Assist me": switch prompts to multiple choice, open translations, offer one-click inputs. */
  const assisted = ref(readAssisted())
  const active = ref(false)
  /** About section shown in the Learn-more drawer, or null when closed. */
  const drawerSection = ref<string | null>(null)

  function setAssisted(value: boolean) {
    assisted.value = value
    try {
      localStorage.setItem(ASSISTED_KEY, value ? '1' : '0')
    } catch {
      /* storage may be unavailable (private mode) — non-fatal */
    }
  }

  function registerHandler(name: string, handler: TourActionHandler) {
    handlers.set(name, handler)
  }

  function unregisterHandler(name: string) {
    handlers.delete(name)
  }

  function hasHandler(name: string): boolean {
    return handlers.has(name)
  }

  async function runAction(name: string, payload?: unknown): Promise<void> {
    const handler = handlers.get(name)
    if (!handler) throw new Error(`No tour handler registered for "${name}"`)
    await handler(payload)
  }

  function openDrawer(sectionId: string) {
    drawerSection.value = sectionId
  }

  function closeDrawer() {
    drawerSection.value = null
  }

  return {
    assisted,
    active,
    drawerSection,
    setAssisted,
    registerHandler,
    unregisterHandler,
    hasHandler,
    runAction,
    openDrawer,
    closeDrawer,
  }
})
