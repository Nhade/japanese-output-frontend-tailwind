<script setup lang="ts">
// Side sheet that shows one About section over the current page. The tour's
// "Learn more" opens it (the tour pauses while it is open) so a visitor never
// has to leave the screen they were looking at.
import { computed, onMounted, onUnmounted } from 'vue';
import { ABOUT_SECTIONS, aboutKey } from '../../lib/aboutContent';
import { useTourStore } from '../../stores/tour';
import AboutSection from './AboutSection.vue';

const tour = useTourStore();

const index = computed(() => ABOUT_SECTIONS.findIndex((s) => s.id === tour.drawerSection));
const section = computed(() => (index.value >= 0 ? ABOUT_SECTIONS[index.value] : null));

function close() {
  tour.closeDrawer();
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && section.value) close();
}

onMounted(() => window.addEventListener('keydown', onKeydown));
onUnmounted(() => window.removeEventListener('keydown', onKeydown));
</script>

<template>
  <transition name="ad-entry">
    <div
      v-if="section"
      class="ad-overlay"
      role="dialog"
      aria-modal="true"
      :aria-label="$t(aboutKey(section.id, 'title'))"
    >
      <div class="ad-backdrop" @click="close" />
      <aside class="ad-sheet">
        <header class="ad-head">
          <span class="eyebrow-sm eyebrow-kohaku">{{ $t('about.drawer_eyebrow') }}</span>
          <button type="button" class="ad-close" :aria-label="$t('about.drawer_close')" @click="close">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
              <path d="M4 4 L12 12 M12 4 L4 12" />
            </svg>
          </button>
        </header>
        <div class="ad-body">
          <AboutSection :def="section" :index="index" compact />
          <router-link :to="{ path: '/about', hash: '#' + section.id }" class="ad-full" @click="close">
            {{ $t('about.drawer_full') }} →
          </router-link>
        </div>
      </aside>
    </div>
  </transition>
</template>

<style scoped>
.ad-overlay {
  position: fixed;
  inset: 0;
  z-index: 95;
}

.ad-backdrop {
  position: absolute;
  inset: 0;
  background: color-mix(in oklab, var(--foreground) 22%, transparent);
}

.ad-sheet {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(520px, 100%);
  display: flex;
  flex-direction: column;
  background: var(--surface-container-lowest);
  border-left: 1px solid color-mix(in oklab, var(--foreground) 12%, transparent);
  box-shadow: -24px 0 48px -24px color-mix(in oklab, var(--foreground) 22%, transparent);
}

.ad-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 28px 14px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 8%, transparent);
}

.ad-close {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 4px;
  color: color-mix(in oklab, var(--foreground) 45%, transparent);
  cursor: pointer;
  transition: color 160ms ease, background 160ms ease;
}

.ad-close:hover {
  color: var(--foreground);
  background: var(--surface-container-low);
}

.ad-close svg {
  width: 14px;
  height: 14px;
}

.ad-body {
  flex: 1;
  overflow-y: auto;
  padding: 26px 28px 40px;
}

.ad-full {
  display: inline-block;
  margin-top: 28px;
  font-family: var(--font-sans);
  font-size: 0.66rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 600;
  color: var(--primary);
  text-decoration: none;
  border-bottom: 1px solid var(--primary);
  padding-bottom: 2px;
}

.ad-full:hover {
  color: var(--primary-container);
  border-bottom-color: var(--secondary);
}

.ad-entry-enter-active,
.ad-entry-leave-active {
  transition: opacity 200ms ease;
}

.ad-entry-enter-active .ad-sheet,
.ad-entry-leave-active .ad-sheet {
  transition: transform 240ms cubic-bezier(0.16, 1, 0.3, 1);
}

.ad-entry-enter-from,
.ad-entry-leave-to {
  opacity: 0;
}

.ad-entry-enter-from .ad-sheet,
.ad-entry-leave-to .ad-sheet {
  transform: translateX(24px);
}
</style>
