<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import SettingsModal from '../components/SettingsModal.vue';
import { useAuthStore } from '../stores/auth';
import { useToastStore } from '../stores/toast';

interface FeedbackCorrection {
  original: string;
  corrected: string;
  explanation: string;
}

interface Feedback {
  overall: string;
  corrections: FeedbackCorrection[];
  retry_count?: number;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  time: string;
  feedback?: Feedback;
  showFeedback?: boolean;
}

interface LearnerFocus {
  tag: string;
  progress: number;
  target: number;
}

interface LearnerProfile {
  current_focus?: LearnerFocus;
}

const { t, locale } = useI18n();
const authStore = useAuthStore();
const toastStore = useToastStore();

const LOCAL_STORAGE_KEY = 'japanese_agent_chat_history';

const messages = ref<Message[]>([]);
const inputMessage = ref('');
const isLoading = ref(false);
const streamEl = ref<HTMLElement | null>(null);
const learnerProfile = ref<LearnerProfile | null>(null);
const showSettings = ref(false);

const currentFocus = computed<LearnerFocus | null>(() => {
  const f = learnerProfile.value?.current_focus;
  if (!f || !f.tag) return null;
  return f;
});

const userExchanges = computed(() =>
  messages.value.filter(m => m.role === 'user').length,
);

const corrections = computed<FeedbackCorrection[]>(() =>
  messages.value
    .filter(m => m.role === 'user' && m.feedback && m.feedback.corrections?.length)
    .flatMap(m => m.feedback!.corrections),
);

function intlLocale(): string {
  if (locale.value === 'ja') return 'ja-JP';
  if (locale.value === 'zh-tw') return 'zh-Hant';
  return 'en-US';
}

const headerDate = computed(() => {
  const now = new Date();
  const dateStr = new Intl.DateTimeFormat(intlLocale(), { month: 'short', day: 'numeric' }).format(now);
  const timeStr = new Intl.DateTimeFormat(intlLocale(), { hour: '2-digit', minute: '2-digit', hour12: false }).format(now);
  return `${dateStr} · ${timeStr}`;
});

function localizedFocusTag(tag: string): string {
  return t(`pos.${tag.toLowerCase()}`, tag);
}

function formatTime(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

async function scrollToBottom() {
  await nextTick();
  if (streamEl.value) {
    streamEl.value.scrollTop = streamEl.value.scrollHeight;
  }
}

async function sendMessage(rawText?: string) {
  const text = (rawText ?? inputMessage.value).trim();
  if (!text || isLoading.value) return;
  inputMessage.value = '';

  const nowISO = new Date().toISOString();
  messages.value.push({ role: 'user', content: text, time: nowISO });
  await scrollToBottom();
  isLoading.value = true;

  try {
    const historyPayload = messages.value.map(m => ({
      role: m.role,
      content: m.content,
    }));

    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || '/api'}/chat/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        history: historyPayload,
        locale: locale.value,
        user_id: authStore.user_id,
      }),
    });

    if (!response.ok) throw new Error('Network response was not ok');

    const data = await response.json();

    if (data.feedback?.overall?.includes?.('Safety violation')) {
      toastStore.trigger(t('chat.safety_violation'), 'error');
    }

    // Feedback semantically belongs to the user's turn; attach it to the
    // preceding user message so the margin-note appears alongside it.
    if (data.feedback) {
      const lastUser = [...messages.value].reverse().find(m => m.role === 'user');
      if (lastUser) {
        lastUser.feedback = data.feedback;
        lastUser.showFeedback = true;
      }
    }

    messages.value.push({
      role: 'assistant',
      content: data.response || t('chat.error_response'),
      time: new Date().toISOString(),
    });
  } catch (err) {
    console.error('Chat error:', err);
    messages.value.push({
      role: 'assistant',
      content: t('chat.error_response'),
      time: new Date().toISOString(),
    });
  } finally {
    isLoading.value = false;
    await scrollToBottom();
  }
}

function onComposerKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function toggleFeedback(index: number) {
  const msg = messages.value[index];
  if (msg && msg.role === 'user' && msg.feedback) {
    msg.showFeedback = !msg.showFeedback;
  }
}

onMounted(async () => {
  const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
  if (saved) {
    try {
      const parsed = JSON.parse(saved) as Message[];
      const migrated = parsed.map(m => ({
        ...m,
        time: m.time || new Date().toISOString(),
      }));
      // Legacy persisted data attached feedback to the assistant turn.
      // The redesigned UI renders feedback under the preceding user turn,
      // so migrate each assistant feedback onto the user message before it.
      for (let i = 0; i < migrated.length; i++) {
        const m = migrated[i];
        if (m.role === 'assistant' && m.feedback) {
          for (let j = i - 1; j >= 0; j--) {
            if (migrated[j].role === 'user') {
              if (!migrated[j].feedback) {
                migrated[j].feedback = m.feedback;
                migrated[j].showFeedback = false;
              }
              break;
            }
          }
          delete m.feedback;
          delete m.showFeedback;
        }
      }
      messages.value = migrated;
      scrollToBottom();
    } catch (e) {
      console.error('Failed to load chat history', e);
    }
  }

  if (authStore.user_id) {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL || '/api'}/learner/profile/${authStore.user_id}`);
      if (res.ok) {
        learnerProfile.value = await res.json();
      }
    } catch (e) {
      console.error('Failed to fetch learner profile', e);
    }
  }
});

watch(messages, (val) => {
  localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(val));
}, { deep: true });
</script>

<template>
  <main class="chat-shell text-foreground">
    <div class="ch-workspace-page">
      <!-- Unified masthead ---------------------------------------- -->
      <header class="ch-header">
        <div class="ch-header-lede">
          <div class="eyebrow-sm eyebrow-kohaku">{{ $t('chat.tutor_desk') }}</div>
          <h1 class="ch-h1">{{ $t('chat.study_session') }}</h1>
        </div>

        <div v-if="currentFocus" class="ch-header-focus">
          <div class="ch-header-focus-row">
            <span class="focus-tag" lang="ja">{{ localizedFocusTag(currentFocus.tag) }}</span>
            <span class="focus-progress" aria-hidden="true">
              <span
                v-for="n in currentFocus.target"
                :key="n"
                class="focus-dot"
                :class="{ 'is-on': n <= currentFocus.progress }"
              />
              <span class="focus-count">
                {{ currentFocus.progress }} / {{ currentFocus.target }}
              </span>
            </span>
          </div>
        </div>
        <div v-else class="ch-header-focus ch-header-focus--empty" />

        <div class="ch-header-meta">
          <div class="ch-header-date">{{ headerDate }}</div>
          <div class="ch-header-count">{{ $t('chat.exchanges', { n: userExchanges }) }}</div>
          <button
            class="ch-settings-btn"
            type="button"
            @click="showSettings = true"
            :aria-label="$t('chat.settings')"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
                 fill="none" stroke="currentColor" stroke-width="1.8"
                 stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </button>
        </div>
      </header>

      <SettingsModal :show="showSettings" @close="showSettings = false" />

      <!-- Desk workspace ------------------------------------------ -->
      <div class="ch-workspace ch-workspace-desk">
        <div class="ch-workspace-main">
          <div ref="streamEl" class="ch-stream">
            <div class="ch-stream-inner">
              <!-- Empty state -->
              <div v-if="messages.length === 0" class="ch-empty">
                {{ $t('chat.empty_stream') }}
              </div>

              <div
                v-for="(msg, i) in messages"
                :key="i"
                class="ch-row"
                :class="{
                  'is-user': msg.role === 'user',
                  'is-assistant': msg.role === 'assistant',
                }"
              >
                <div
                  class="ch-bubble"
                  :class="msg.role === 'user' ? 'is-user' : 'is-assistant'"
                >
                  <div class="ch-bubble-head">
                    <span class="ch-bubble-role">
                      {{ msg.role === 'user' ? $t('chat.you') : $t('chat.tutor') }}
                    </span>
                    <span class="ch-bubble-time">{{ formatTime(msg.time) }}</span>
                  </div>
                  <div class="ch-bubble-body" lang="ja">{{ msg.content }}</div>
                </div>

                <!-- Inline feedback under the user's turn ------- -->
                <div
                  v-if="msg.role === 'user' && msg.feedback"
                  class="ch-inline-feedback-wrap"
                >
                  <button
                    class="ch-feedback-toggle"
                    type="button"
                    @click="toggleFeedback(i)"
                  >
                    <span class="ch-feedback-toggle-dot" :class="{ 'has-errors': (msg.feedback.corrections?.length ?? 0) > 0 }" />
                    {{ msg.showFeedback ? $t('chat.hide_feedback') : $t('chat.analysis_ready') }}
                  </button>

                  <div v-if="msg.showFeedback" class="ch-inline-feedback">
                    <div class="ch-margin-eyebrow">{{ $t('chat.tutors_note') }}</div>
                    <p v-if="msg.feedback.overall" class="ch-margin-overall">
                      {{ msg.feedback.overall }}
                    </p>
                    <ul
                      v-if="msg.feedback.corrections && msg.feedback.corrections.length"
                      class="ch-margin-corrections"
                    >
                      <li v-for="(c, cIx) in msg.feedback.corrections" :key="cIx">
                        <div class="ch-corr-line">
                          <span class="ch-corr-strike" lang="ja">{{ c.original }}</span>
                          <span class="ch-corr-arrow">→</span>
                          <span class="ch-corr-right" lang="ja">{{ c.corrected }}</span>
                        </div>
                        <div class="ch-corr-note">{{ c.explanation }}</div>
                      </li>
                    </ul>
                    <div v-else class="ch-margin-empty">{{ $t('chat.no_errors') }}</div>
                  </div>
                </div>
              </div>

              <!-- Loading -->
              <div v-if="isLoading" class="ch-row is-assistant">
                <div class="ch-bubble is-assistant is-loading">
                  <div class="ch-bubble-head">
                    <span class="ch-bubble-role">{{ $t('chat.tutor') }}</span>
                  </div>
                  <div class="ch-loading-dots" aria-hidden="true">
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Composer ------------------------------------------- -->
          <div class="ch-composer">
            <div class="ch-composer-eyebrow">
              <span class="eyebrow-sm">{{ $t('chat.compose_eyebrow') }}</span>
              <span class="ch-composer-hint">{{ $t('chat.compose_hint') }}</span>
            </div>
            <div class="ch-composer-row">
              <textarea
                v-model="inputMessage"
                class="ch-composer-input"
                :placeholder="$t('chat.placeholder_ja')"
                rows="2"
                lang="ja"
                @keydown="onComposerKeydown"
              />
              <button
                class="ch-send"
                type="button"
                :disabled="!inputMessage.trim() || isLoading"
                @click="sendMessage()"
              >
                {{ $t('chat.send') }}
              </button>
            </div>
            <p class="ch-disclaimer">{{ $t('chat.disclaimer') }}</p>
          </div>
        </div>

        <!-- Desk rail --------------------------------------------- -->
        <aside class="ch-desk">
          <div class="ch-desk-section">
            <div class="eyebrow-sm eyebrow-kohaku">{{ $t('chat.todays_focus') }}</div>
            <template v-if="currentFocus">
              <div class="ch-desk-focus-tag" lang="ja">
                {{ localizedFocusTag(currentFocus.tag) }}
              </div>
              <div class="ch-desk-bar" aria-hidden="true">
                <div
                  class="ch-desk-bar-fill"
                  :style="{ width: `${Math.min(100, (currentFocus.progress / currentFocus.target) * 100)}%` }"
                />
              </div>
              <div class="ch-desk-bar-label">
                {{ $t('chat.exchanges_of', { n: currentFocus.progress, total: currentFocus.target }) }}
              </div>
            </template>
            <p v-else class="ch-desk-empty">{{ $t('chat.focus_default') }}</p>
          </div>

          <div class="ch-desk-section">
            <div class="eyebrow-sm eyebrow-kohaku">{{ $t('chat.running_errata') }}</div>
            <p v-if="corrections.length === 0" class="ch-desk-empty">
              {{ $t('chat.empty_errata') }}
            </p>
            <ul v-else class="ch-desk-errata">
              <li v-for="(c, i) in corrections" :key="i">
                <div class="ch-desk-errata-line">
                  <span class="ch-corr-strike" lang="ja">{{ c.original }}</span>
                  <span lang="ja">{{ c.corrected }}</span>
                </div>
                <div class="ch-desk-errata-note">{{ c.explanation }}</div>
              </li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  </main>
</template>

<style scoped>
/* --------------------------------------------------------------
   Shell — pinned height so chat header stays visible while only
   the message stream scrolls. App.vue's main has pt-16 (64px).
-------------------------------------------------------------- */
/* Top nav is pt-16 (4rem). TheFooter is fixed to the bottom of the
   viewport at ~45px tall (see TheFooter.vue); the workspace shrinks
   to clear it so the composer/disclaimer aren't hidden underneath. */
.chat-shell {
  min-height: calc(100vh - 4rem);
  padding-bottom: 3rem;
  background-image: linear-gradient(
    180deg,
    var(--background) 0%,
    var(--surface-container-low) 100%
  );
}

.ch-workspace-page {
  height: calc(100dvh - 4rem - 3rem);
  max-width: 1260px;
  width: 100%;
  margin: 0 auto;
  padding: 0 48px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
@media (max-width: 900px) {
  .ch-workspace-page { padding: 0 20px; height: auto; min-height: calc(100vh - 4rem - 3rem); }
}

/* Header ------------------------------------------------------ */
.ch-header {
  flex: 0 0 auto;
  padding: 22px 0 14px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: end;
  gap: 36px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
}
.ch-header-lede { min-width: 0; }
.ch-header-lede .eyebrow-sm { margin-bottom: 8px; }
.ch-h1 {
  font-family: var(--font-serif);
  font-size: clamp(1.6rem, 1.5vw + 0.9rem, 2.2rem);
  line-height: 1.15;
  margin: 0;
  font-weight: 500;
  letter-spacing: -0.005em;
}

.ch-header-focus {
  min-width: 0;
  padding-left: 28px;
  padding-bottom: 4px;
  border-left: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
}
.ch-header-focus--empty { border-left: none; }
.ch-header-focus-row {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
}

.focus-tag {
  font-family: var(--font-serif);
  font-size: 1.25rem;
  color: var(--primary);
  font-weight: 500;
}
.focus-progress {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}
.focus-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: transparent;
  border: 1px solid color-mix(in oklab, var(--foreground) 15%, transparent);
  transition: background 180ms ease, border-color 180ms ease;
}
.focus-dot.is-on { background: var(--secondary); border-color: var(--secondary); }
.focus-count {
  font-family: var(--font-sans);
  font-size: 0.68rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  margin-left: 6px;
}

.ch-header-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  padding-bottom: 4px;
}
.ch-header-date {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.92rem;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
}
.ch-header-count {
  font-family: var(--font-sans);
  font-size: 0.62rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}
.ch-settings-btn {
  margin-top: 4px;
  background: none;
  border: none;
  padding: 4px;
  cursor: pointer;
  color: color-mix(in oklab, var(--foreground) 45%, transparent);
  transition: color 160ms ease;
}
.ch-settings-btn:hover { color: var(--primary); }

@media (max-width: 900px) {
  .ch-header {
    grid-template-columns: 1fr;
    gap: 14px;
    padding: 20px 0 14px;
  }
  .ch-header-focus {
    padding-left: 0;
    border-left: none;
    border-top: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
    padding-top: 14px;
  }
  .ch-header-meta { flex-direction: row; align-items: center; gap: 16px; }
}

/* Workspace --------------------------------------------------- */
.ch-workspace {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.ch-workspace-desk {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 48px;
  min-height: 0;
}
.ch-workspace-main {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
@media (max-width: 900px) {
  .ch-workspace-desk { grid-template-columns: 1fr; gap: 28px; }
}

/* Stream ------------------------------------------------------ */
.ch-stream {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
  /* soft fade at top/bottom so messages dissolve into chrome */
  mask-image: linear-gradient(to bottom, transparent 0, black 18px, black calc(100% - 24px), transparent 100%);
  -webkit-mask-image: linear-gradient(to bottom, transparent 0, black 18px, black calc(100% - 24px), transparent 100%);
}
.ch-stream-inner { padding: 10px 2px 28px; }

.ch-empty {
  padding: 60px 0;
  text-align: center;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 1rem;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  max-width: 32em;
  margin: 0 auto;
}

/* Row + bubbles ----------------------------------------------- */
.ch-row {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 0 18px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 7%, transparent);
}
.ch-row:last-child { border-bottom: none; }
.ch-row.is-user { align-items: flex-end; }
.ch-row.is-assistant { align-items: flex-start; }

.ch-bubble {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 40em;
  min-width: 0;
}
.ch-bubble.is-user { text-align: right; align-items: flex-end; }
.ch-bubble.is-assistant { align-items: flex-start; }

.ch-bubble-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-family: var(--font-sans);
}
.ch-bubble.is-user .ch-bubble-head { justify-content: flex-end; flex-direction: row-reverse; }
.ch-bubble-role {
  font-size: 0.62rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  font-weight: 500;
}
.ch-bubble.is-user .ch-bubble-role { color: var(--secondary); }
.ch-bubble.is-assistant .ch-bubble-role { color: var(--primary); }
.ch-bubble-time {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.78rem;
  color: color-mix(in oklab, var(--foreground) 45%, transparent);
}
.ch-bubble-body {
  font-family: var(--font-serif);
  font-size: 1.15rem;
  line-height: 1.85;
  color: var(--foreground);
  word-break: auto-phrase;
  padding: 6px 0;
}
.ch-bubble.is-user .ch-bubble-body {
  border-right: 2px solid var(--secondary);
  padding-right: 14px;
}
.ch-bubble.is-assistant .ch-bubble-body {
  border-left: 2px solid var(--primary);
  padding-left: 14px;
}

.ch-bubble.is-loading .ch-loading-dots {
  padding: 10px 14px;
  border-left: 2px solid var(--primary);
  display: flex;
  gap: 4px;
  align-items: center;
  min-height: 28px;
}
.ch-bubble.is-loading .ch-loading-dots span {
  width: 4px; height: 4px; border-radius: 50%;
  background: color-mix(in oklab, var(--foreground) 35%, transparent);
  animation: ch-dot 1.2s ease-in-out infinite;
}
.ch-bubble.is-loading .ch-loading-dots span:nth-child(2) { animation-delay: 0.15s; }
.ch-bubble.is-loading .ch-loading-dots span:nth-child(3) { animation-delay: 0.3s; }
@keyframes ch-dot {
  0%, 80%, 100% { opacity: 0.3; }
  40% { opacity: 1; }
}

/* Inline feedback --------------------------------------------- */
.ch-inline-feedback-wrap {
  margin-top: 4px;
  max-width: 40em;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-self: flex-end; /* align with user bubble */
}
.ch-feedback-toggle {
  align-self: flex-end;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-sans);
  font-size: 0.62rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 60%, transparent);
  background: none;
  border: none;
  padding: 4px 0;
  cursor: pointer;
  border-bottom: 1px solid transparent;
  transition: color 160ms ease, border-color 160ms ease;
}
.ch-feedback-toggle:hover { color: var(--primary); border-bottom-color: var(--secondary); }
.ch-feedback-toggle-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: color-mix(in oklab, var(--foreground) 25%, transparent);
}
.ch-feedback-toggle-dot.has-errors { background: var(--secondary); }

.ch-inline-feedback {
  padding: 14px 18px;
  background: var(--surface-container-low);
  border-left: 2px solid var(--secondary);
  border-radius: 0 3px 3px 0;
  font-family: var(--font-serif);
  font-size: 0.95rem;
  line-height: 1.7;
  color: color-mix(in oklab, var(--foreground) 82%, transparent);
  text-align: left;
  animation: ch-feedback-in 240ms ease both;
}
@keyframes ch-feedback-in {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
.ch-margin-eyebrow {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.6rem;
  color: var(--secondary);
  font-weight: 500;
  margin-bottom: 8px;
}
.ch-margin-overall {
  margin: 0 0 12px;
  font-style: italic;
}
.ch-margin-empty {
  font-style: italic;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  font-size: 0.9rem;
}
.ch-margin-corrections {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ch-margin-corrections li {
  padding-bottom: 10px;
  border-bottom: 1px dotted color-mix(in oklab, var(--foreground) 9%, transparent);
}
.ch-margin-corrections li:last-child { border-bottom: none; padding-bottom: 0; }

.ch-corr-line {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.ch-corr-strike {
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  text-decoration: line-through;
  text-decoration-color: var(--secondary);
  text-decoration-thickness: 1.5px;
}
.ch-corr-arrow {
  color: var(--secondary);
  font-family: var(--font-serif);
  font-style: italic;
}
.ch-corr-right {
  color: var(--primary);
  font-weight: 500;
}
.ch-corr-note {
  font-size: 0.85rem;
  font-style: italic;
  color: color-mix(in oklab, var(--foreground) 65%, transparent);
  line-height: 1.65;
}

/* Composer ---------------------------------------------------- */
.ch-composer {
  flex: 0 0 auto;
  padding: 16px 0 18px;
  border-top: 1px solid var(--foreground);
  background: var(--background);
}
.ch-composer-eyebrow {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 16px;
  margin-bottom: 10px;
}
.ch-composer-eyebrow .eyebrow-sm {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.62rem;
  font-weight: 500;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}
.ch-composer-hint {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.8rem;
  color: color-mix(in oklab, var(--foreground) 50%, transparent);
}
.ch-composer-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 14px;
  align-items: end;
}
.ch-composer-input {
  font-family: var(--font-serif);
  font-size: 1.05rem;
  line-height: 1.7;
  resize: vertical;
  min-height: 58px;
  max-height: 180px;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--input);
  padding: 8px 0;
  color: var(--foreground);
  outline: none;
  transition: border-color 180ms ease;
}
.ch-composer-input:focus { border-bottom-color: var(--primary); border-bottom-width: 2px; }
.ch-composer-input::placeholder {
  color: color-mix(in oklab, var(--foreground) 35%, transparent);
  font-style: italic;
}
.ch-send {
  font-family: var(--font-sans);
  font-size: 0.72rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  background: var(--primary);
  color: var(--background);
  border: none;
  padding: 12px 22px;
  border-radius: 2px;
  cursor: pointer;
  font-weight: 500;
  transition: background 180ms ease, opacity 180ms ease;
}
.ch-send:hover:not(:disabled) { background: var(--primary-container); }
.ch-send:disabled { opacity: 0.45; cursor: not-allowed; }
.ch-disclaimer {
  margin: 8px 0 0;
  font-family: var(--font-sans);
  font-size: 0.68rem;
  color: color-mix(in oklab, var(--foreground) 45%, transparent);
  text-align: center;
}

/* Desk rail --------------------------------------------------- */
.ch-desk {
  align-self: stretch;
  max-height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 22px 24px;
  background: var(--surface-container-low);
  border-radius: 4px;
  border: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
}
.ch-desk-section:not(:last-child) {
  padding-bottom: 22px;
  border-bottom: 1px solid color-mix(in oklab, var(--foreground) 9%, transparent);
}
.ch-desk-focus-tag {
  font-family: var(--font-serif);
  font-size: 1.5rem;
  color: var(--primary);
  margin-top: 10px;
  margin-bottom: 14px;
}
.ch-desk-bar {
  height: 3px;
  background: color-mix(in oklab, var(--foreground) 9%, transparent);
  overflow: hidden;
}
.ch-desk-bar-fill {
  height: 100%;
  background: var(--secondary);
  transition: width 260ms ease;
}
.ch-desk-bar-label {
  margin-top: 8px;
  font-family: var(--font-sans);
  font-size: 0.62rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}
.ch-desk-empty {
  margin: 10px 0 0;
  font-family: var(--font-serif);
  font-style: italic;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
  font-size: 0.9rem;
  line-height: 1.55;
}
.ch-desk-errata {
  list-style: none;
  padding: 0;
  margin: 10px 0 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.ch-desk-errata li {
  padding-bottom: 12px;
  border-bottom: 1px dotted color-mix(in oklab, var(--foreground) 9%, transparent);
}
.ch-desk-errata li:last-child { border-bottom: none; padding-bottom: 0; }
.ch-desk-errata-line {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  font-family: var(--font-serif);
  font-size: 1rem;
  margin-bottom: 4px;
}
.ch-desk-errata-line [lang="ja"]:not(.ch-corr-strike) {
  color: var(--primary);
  font-weight: 500;
}
.ch-desk-errata-note {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 0.82rem;
  color: color-mix(in oklab, var(--foreground) 62%, transparent);
  line-height: 1.6;
}

/* Eyebrow helpers — scoped versions matching design mock ------ */
.eyebrow-sm {
  font-family: var(--font-sans);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.62rem;
  font-weight: 500;
  color: color-mix(in oklab, var(--foreground) 55%, transparent);
}
.eyebrow-kohaku { color: var(--secondary); }
</style>
