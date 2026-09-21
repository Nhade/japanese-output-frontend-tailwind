<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useTourStore } from '../../stores/tour';
import { controlsBusy, learnMore, nextTourStep, performTourAction, previousTourStep, stopTour, TOUR_STEPS, tourActionLabel } from '../../lib/tour';

const tour = useTourStore();
const { t } = useI18n();
const panel = ref<HTMLElement>();
const expanded = ref(true);
const step = computed(() => TOUR_STEPS[tour.inlineStep ?? -1]);
const busy = computed(() => controlsBusy(tour));
watch(() => tour.inlineStep, async (index) => {
  if (index === null) return;
  expanded.value = tour.actionState !== 'done';
  await nextTick();
  panel.value?.focus({ preventScroll: true });
  panel.value?.scrollIntoView({ block: 'nearest' });
}, { immediate: true });
watch(() => tour.actionState, (state) => {
  if (state === 'working' || state === 'done') expanded.value = false;
});
</script>

<template>
  <section v-if="step" ref="panel" class="tour-chat" tabindex="-1" aria-labelledby="tour-chat-title">
    <div class="tour-chat-heading">
      <span class="tour-chat-progress">{{ (tour.inlineStep ?? 0) + 1 }} / {{ TOUR_STEPS.length }}</span>
      <h2 id="tour-chat-title">{{ t(`tour.steps.${step.id}.title`) }}</h2>
      <button type="button" class="tour-chat-close" :aria-label="t('about.drawer_close')" @click="stopTour">×</button>
    </div>
    <button type="button" class="tour-chat-toggle" :aria-expanded="expanded" aria-controls="tour-chat-description" @click="expanded = !expanded">
      {{ t(expanded ? 'tour.buttons.hide_instructions' : 'tour.buttons.show_instructions') }}
    </button>
    <p v-show="expanded" id="tour-chat-description">{{ t(`tour.steps.${step.id}.body`) }}</p>
    <div class="tour-chat-controls">
      <button type="button" class="shiori-tour-btn is-primary" :disabled="busy || tour.actionState === 'done'" @click="performTourAction">{{ tourActionLabel() }}</button>
      <button type="button" class="shiori-tour-btn" :disabled="busy" @click="learnMore">{{ t('tour.buttons.learn_more') }}</button>
      <div class="tour-chat-navigation">
        <button type="button" :disabled="busy" @click="previousTourStep">{{ t('tour.buttons.prev') }}</button>
        <button type="button" :disabled="busy" @click="nextTourStep">{{ t('tour.buttons.next') }}</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.tour-chat { flex: none; margin: 16px 0; padding: 16px 20px; border: 1px solid var(--border); border-left: 3px solid var(--secondary); background: var(--surface-container-lowest); }
.tour-chat-heading, .tour-chat-controls, .tour-chat-navigation { display: flex; align-items: center; gap: 12px; }
.tour-chat-heading h2 { margin: 0; font: 500 1.15rem var(--font-serif); }
.tour-chat-progress { font-size: .75rem; color: var(--secondary); white-space: nowrap; }
.tour-chat-close { margin-left: auto; font-size: 1.4rem; padding: 0 6px; }
.tour-chat-toggle { margin: 6px 0; font-size: .8rem; text-decoration: underline; color: var(--primary); }
.tour-chat p { margin: 4px 0 12px; line-height: 1.6; font-size: .95rem; }
.tour-chat-controls { flex-wrap: wrap; }
.tour-chat-navigation { margin-left: auto; }
.tour-chat-navigation button { border: 1px solid var(--border); padding: 6px 12px; font-size: .85rem; }
.tour-chat-navigation button:last-child { background: var(--primary); color: var(--primary-foreground); }
button { cursor: pointer; }
button:disabled { opacity: .55; cursor: default; }
</style>
