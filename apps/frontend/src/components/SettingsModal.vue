<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue';
import { useAuthStore } from '../stores/auth';
import { useToastStore } from '../stores/toast';
import { useI18n } from 'vue-i18n';
import { apiJson } from '../lib/api';

const props = defineProps<{
  show: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'updated'): void;
}>();

const { t } = useI18n();
const auth = useAuthStore();
const toast = useToastStore();
const isLoading = ref(false);

const jlptLevel = ref('N5');
const feedbackPref = ref<'gentle' | 'normal' | 'strict'>('gentle');

const jlptOptions = ['N5', 'N4', 'N3', 'N2', 'N1'] as const;
const prefOptions: { value: 'gentle' | 'normal' | 'strict'; label: string; desc: string }[] = [
  { value: 'gentle', label: 'settings.pref_gentle', desc: 'settings.pref_gentle_desc' },
  { value: 'normal', label: 'settings.pref_normal', desc: 'settings.pref_normal_desc' },
  { value: 'strict', label: 'settings.pref_strict', desc: 'settings.pref_strict_desc' },
];

watch(() => props.show, async (newVal) => {
  if (!newVal || !auth.user_id) return;
  try {
    const data = await apiJson<{ level_est?: string; feedback_preference?: 'gentle' | 'normal' | 'strict' }>(
      '/api/learner/profile/me',
    );
    if (data.level_est) jlptLevel.value = data.level_est;
    if (data.feedback_preference) feedbackPref.value = data.feedback_preference;
  } catch (e) {
    console.error(e);
  }
});

async function saveSettings() {
  if (!auth.user_id || isLoading.value) return;
  isLoading.value = true;
  try {
    await apiJson('/api/users/profile', {
      method: 'POST',
      body: {
        settings: {
          level_est: jlptLevel.value,
          feedback_preference: feedbackPref.value,
        },
      },
    });
    toast.trigger(t('settings.saved_success'), 'success');
    emit('updated');
    emit('close');
  } catch (e) {
    toast.trigger(t('exercise.network_error'), 'error');
  } finally {
    isLoading.value = false;
  }
}

function close() {
  emit('close');
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.show) close();
}

onMounted(() => window.addEventListener('keydown', handleKeydown));
onUnmounted(() => window.removeEventListener('keydown', handleKeydown));
</script>

<template>
  <transition name="settings-entry">
    <div
      v-if="show"
      class="settings-overlay"
      aria-modal="true"
      role="dialog"
      :aria-label="$t('settings.title')"
    >
      <div class="settings-backdrop" @click="close" />

      <div class="settings-card" @click.stop>
        <button
          type="button"
          class="settings-close"
          @click="close"
          :aria-label="$t('settings.close')"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
            <path d="M4 4 L12 12 M12 4 L4 12" />
          </svg>
        </button>

        <header class="settings-head">
          <div class="eyebrow-sm eyebrow-kohaku">{{ $t('settings.eyebrow') }}</div>
          <h2 class="settings-h1">{{ $t('settings.heading') }}</h2>
          <p class="settings-sub">{{ $t('settings.subtitle') }}</p>
        </header>

        <div class="settings-body">
          <!-- JLPT level ------------------------------------ -->
          <section class="settings-section">
            <div class="settings-label">{{ $t('settings.jlpt_level') }}</div>
            <div class="settings-chip-row" role="radiogroup">
              <button
                v-for="level in jlptOptions"
                :key="level"
                type="button"
                role="radio"
                class="settings-chip"
                :class="{ 'is-active': jlptLevel === level }"
                :aria-checked="jlptLevel === level"
                @click="jlptLevel = level"
              >
                {{ level }}
              </button>
            </div>
          </section>

          <!-- Feedback style ------------------------------- -->
          <section class="settings-section">
            <div class="settings-label">{{ $t('settings.feedback_preference') }}</div>
            <div class="settings-pref-list" role="radiogroup">
              <button
                v-for="opt in prefOptions"
                :key="opt.value"
                type="button"
                role="radio"
                class="settings-pref"
                :class="{ 'is-active': feedbackPref === opt.value }"
                :aria-checked="feedbackPref === opt.value"
                @click="feedbackPref = opt.value"
              >
                <div class="settings-pref-head">
                  <span class="settings-pref-name">{{ $t(opt.label) }}</span>
                  <span v-if="feedbackPref === opt.value" class="settings-pref-dot" aria-hidden="true" />
                </div>
                <div class="settings-pref-desc">{{ $t(opt.desc) }}</div>
              </button>
            </div>
          </section>
        </div>

        <footer class="settings-foot">
          <button
            type="button"
            class="settings-save"
            :disabled="isLoading"
            @click="saveSettings"
          >
            {{ isLoading ? $t('settings.saving') : $t('settings.save') }}
          </button>
        </footer>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.settings-overlay {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

/* Glass backdrop — per design doc §2 / §4 (transient overlays only). */
.settings-backdrop {
  position: absolute;
  inset: 0;
  background: color-mix(in oklab, var(--foreground) 32%, transparent);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

/* Paper card — surface_container_lowest on a ghost hairline. */
.settings-card {
  position: relative;
  width: 100%;
  max-width: 540px;
  max-height: calc(100dvh - 8rem);
  display: flex;
  flex-direction: column;
  background: var(--surface-container-lowest);
  border: 1px solid color-mix(in oklab, var(--foreground) 10%, transparent);
  border-radius: 6px;
  box-shadow:
    0 32px 64px -24px color-mix(in oklab, var(--foreground) 18%, transparent),
    0 4px 12px -6px color-mix(in oklab, var(--foreground) 8%, transparent);
  overflow: hidden;
}

.settings-close {
  position: absolute;
  top: 14px; right: 14px;
  width: 32px; height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: color-mix(in oklab, var(--foreground) 45%, transparent);
  cursor: pointer;
  border-radius: 4px;
  transition: color 160ms ease, background 160ms ease;
}
.settings-close:hover {
  color: var(--foreground);
  background: var(--surface-container-low);
}
.settings-close svg { width: 14px; height: 14px; }

/* Header ---------------------------------------------------- */
.settings-head {
  padding: 32px 36px 22px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 8%, transparent);
}
.settings-h1 {
  font-family: var(--font-serif);
  font-size: 1.75rem;
  line-height: 1.2;
  margin: 10px 0 6px;
  font-weight: 500;
  letter-spacing: -0.005em;
  color: var(--foreground);
}
.settings-sub {
  margin: 0;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.95rem;
  line-height: 1.55;
  color: color-mix(in oklab, var(--foreground) 65%, transparent);
  max-width: 28em;
}

/* Body ------------------------------------------------------ */
.settings-body {
  padding: 24px 36px 8px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 28px;
}
.settings-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.settings-label {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.62rem;
  font-weight: 500;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}

/* JLPT chip row — mirrors news filter chips. */
.settings-chip-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.settings-chip {
  font-family: var(--font-serif);
  font-size: 0.95rem;
  padding: 6px 14px;
  color: color-mix(in oklab, var(--foreground) 65%, transparent);
  background: transparent;
  border: none;
  cursor: pointer;
  border-bottom: 1px solid transparent;
  transition: color 160ms ease, border-color 160ms ease;
  letter-spacing: 0.01em;
}
.settings-chip:hover { color: var(--foreground); }
.settings-chip.is-active {
  color: var(--primary);
  border-bottom-color: var(--secondary);
  font-weight: 500;
}

/* Preference list — left kohaku rule on active. */
.settings-pref-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.settings-pref {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
  padding: 12px 16px 12px 18px;
  background: transparent;
  border: none;
  border-left: 2px solid transparent;
  cursor: pointer;
  transition: background 160ms ease, border-color 160ms ease;
  font-family: inherit;
  color: inherit;
}
.settings-pref:hover { background: var(--surface-container-low); }
.settings-pref.is-active {
  border-left-color: var(--secondary);
  background: var(--surface-container-low);
}
.settings-pref-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}
.settings-pref-name {
  font-family: var(--font-serif);
  font-size: 1.05rem;
  color: var(--foreground);
}
.settings-pref.is-active .settings-pref-name {
  color: var(--primary);
  font-weight: 500;
}
.settings-pref-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--secondary);
  flex-shrink: 0;
}
.settings-pref-desc {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.85rem;
  line-height: 1.5;
  color: color-mix(in oklab, var(--foreground) 62%, transparent);
}

/* Footer ---------------------------------------------------- */
.settings-foot {
  padding: 20px 36px 28px;
  border-top: 1px solid color-mix(in oklab, var(--foreground) 8%, transparent);
}
.settings-save {
  width: 100%;
  font-family: var(--font-sans);
  font-size: 0.72rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  background: var(--primary);
  color: var(--background);
  border: none;
  padding: 14px 24px;
  border-radius: 2px;
  cursor: pointer;
  font-weight: 500;
  transition: background 180ms ease, opacity 180ms ease;
}
.settings-save:hover:not(:disabled) { background: var(--primary-container); }
.settings-save:disabled { opacity: 0.55; cursor: not-allowed; }

/* Eyebrow helpers ------------------------------------------- */
.eyebrow-sm {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.62rem;
  font-weight: 500;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}
.eyebrow-kohaku { color: var(--secondary); }

/* Transitions ------------------------------------------------ */
.settings-entry-enter-active,
.settings-entry-leave-active {
  transition: opacity 220ms ease;
}
.settings-entry-enter-active .settings-backdrop,
.settings-entry-leave-active .settings-backdrop {
  transition: opacity 220ms ease;
}
.settings-entry-enter-active .settings-card,
.settings-entry-leave-active .settings-card {
  transition: opacity 260ms cubic-bezier(0.16, 1, 0.3, 1),
              transform 260ms cubic-bezier(0.16, 1, 0.3, 1);
}
.settings-entry-enter-from .settings-backdrop,
.settings-entry-leave-to .settings-backdrop { opacity: 0; }
.settings-entry-enter-from .settings-card,
.settings-entry-leave-to .settings-card {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}

@media (max-width: 600px) {
  .settings-card { max-height: calc(100dvh - 2rem); }
  .settings-head, .settings-body, .settings-foot { padding-left: 24px; padding-right: 24px; }
  .settings-head { padding-top: 28px; }
}
</style>
