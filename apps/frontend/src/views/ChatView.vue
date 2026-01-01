<script setup lang="ts">
import { ref, nextTick, onMounted, watch, computed } from 'vue';
import { useI18n } from 'vue-i18n';

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
    feedback?: Feedback; // Only for assistant
    showFeedback?: boolean; // UI state
}

import LearningFocusCard from '../components/LearningFocusCard.vue';
import { useAuthStore } from '../stores/auth';

const { t, locale } = useI18n();
const authStore = useAuthStore();
const messages = ref<Message[]>([]);
const inputMessage = ref('');
const isLoading = ref(false);
const chatContainer = ref<HTMLElement | null>(null);
const learnerProfile = ref<any>(null);
const currentFocus = computed(() => {
    return learnerProfile.value?.current_focus || null;
});

// Load history from localStorage if available (Optional, but good for UX)
const LOCAL_STORAGE_KEY = 'japanese_agent_chat_history';

onMounted(async () => {
    // History
    const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (saved) {
        try {
            messages.value = JSON.parse(saved);
            scrollToBottom();
        } catch (e) {
            console.error("Failed to load chat history", e);
        }
    }

    // Fetch Profile
    if (authStore.user_id) {
        try {
            const res = await fetch(`${import.meta.env.VITE_API_BASE_URL || '/api'}/learner/profile/${authStore.user_id}`);
            if (res.ok) {
                learnerProfile.value = await res.json();
            }
        } catch (e) {
            console.error("Failed to fetch learner profile", e);
        }
    }
});

watch(messages, (newVal) => {
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(newVal));
}, { deep: true });

const scrollToBottom = async () => {
    await nextTick();
    if (chatContainer.value) {
        chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
    }
};

const sendMessage = async () => {
    if (!inputMessage.value.trim() || isLoading.value) return;

    const userMsg = inputMessage.value.trim();
    inputMessage.value = '';

    // Add user message
    messages.value.push({ role: 'user', content: userMsg });
    scrollToBottom();
    isLoading.value = true;

    try {
        // Prepare history for API (excluding feedback and UI state)
        const historyPayload = messages.value.map(m => ({
            role: m.role,
            content: m.content
        }));

        const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || '/api'}/chat/send`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: userMsg,
                history: historyPayload,
                locale: locale.value, // Send current locale
                user_id: authStore.user_id
            })
        });

        if (!response.ok) {
            throw new Error('Network response was not ok');
        }

        const data = await response.json();

        // Add assistant message
        messages.value.push({
            role: 'assistant',
            content: data.response || "Error: No response",
            feedback: data.feedback,
            showFeedback: false
        });

    } catch (error) {
        console.error("Chat error:", error);
        messages.value.push({
            role: 'assistant',
            content: t('chat.error_response')
        });
    } finally {
        isLoading.value = false;
        scrollToBottom();
    }
};

const toggleFeedback = (index: number) => {
    if (messages.value[index].role === 'assistant') {
        messages.value[index].showFeedback = !messages.value[index].showFeedback;
    }
};
</script>

<template>
    <div class="container mx-auto px-4 max-w-4xl h-[calc(100vh-6rem)] flex flex-col">
        <!-- Header -->
        <div class="py-4 border-b border-zinc-200 dark:border-zinc-800 shrink-0">
            <h1 class="text-2xl font-bold bg-linear-to-r from-emerald-600 to-teal-500 bg-clip-text text-transparent">
                {{ t('chat.title') }}
            </h1>
            <p class="text-zinc-500 dark:text-zinc-400 text-sm">
                {{ t('chat.subtitle') }}
            </p>
        </div>

        <!-- Personalized Hint / Learning Focus -->
        <div v-if="currentFocus && currentFocus.tag" class="py-2 shrink-0">
            <LearningFocusCard :focus="currentFocus" />
        </div>
        <div v-else-if="learnerProfile" class="py-2 shrink-0">
            <!-- Fallback if no focus (shouldn't happen with P2 logic but safe to keep) -->
            <div
                class="bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-lg px-4 py-2 text-sm text-zinc-500 dark:text-zinc-400">
                {{ t('chat.focus_default', 'Chat freely to build your profile.') }}
            </div>
        </div>

        <!-- Chat Area -->
        <div ref="chatContainer" class="flex-1 overflow-y-auto py-6 space-y-6 scroll-smooth">
            <div v-if="messages.length === 0" class="text-center text-zinc-400 py-20">
                <div class="mb-4 text-6xl">👋</div>
                <p>{{ t('chat.welcome') }}</p>
            </div>

            <div v-for="(msg, index) in messages" :key="index"
                :class="['flex w-full', msg.role === 'user' ? 'justify-end' : 'justify-start']">

                <!-- Assistant Avatar (Optional) -->
                <div v-if="msg.role === 'assistant'" class="mr-3 shrink-0">
                    <div
                        class="w-8 h-8 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
                        🤖
                    </div>
                </div>

                <div class="max-w-[85%] sm:max-w-[75%] space-y-2">
                    <!-- Message Bubble -->
                    <div lang="ja" :class="[
                        'p-4 rounded-2xl shadow-sm text-base leading-relaxed whitespace-pre-wrap font-ja',
                        msg.role === 'user'
                            ? 'bg-emerald-600 text-white rounded-tr-sm'
                            : 'bg-white dark:bg-zinc-800 text-zinc-800 dark:text-zinc-100 border border-zinc-100 dark:border-zinc-700/50 rounded-tl-sm'
                    ]">
                        {{ msg.content }}
                    </div>

                    <!-- Feedback Section (Assistant Only) -->
                    <div v-if="msg.role === 'assistant' && msg.feedback" class="flex flex-col items-start gap-2">
                        <!-- Toggle Button -->
                        <button @click="toggleFeedback(index)"
                            class="text-xs flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-100 dark:bg-zinc-800/50 hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors text-zinc-500 dark:text-zinc-400">
                            <span v-if="msg.showFeedback">{{ t('chat.hide_feedback') }}</span>
                            <span v-else>{{ t('chat.show_feedback') }}</span>
                            <svg v-if="!msg.showFeedback" xmlns="http://www.w3.org/2000/svg" width="14" height="14"
                                viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                                stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-lightbulb">
                                <path
                                    d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5" />
                                <path d="M9 18h6" />
                                <path d="M10 22h4" />
                            </svg>
                        </button>

                        <!-- Feedback Content -->
                        <transition enter-active-class="transition-all duration-300 ease-out"
                            enter-from-class="opacity-0 -translate-y-2" enter-to-class="opacity-100 translate-y-0"
                            leave-active-class="transition-all duration-200 ease-in"
                            leave-from-class="opacity-100 translate-y-0" leave-to-class="opacity-0 -translate-y-2">
                            <div v-if="msg.showFeedback" lang="zh-Hant"
                                class="w-full bg-amber-50 dark:bg-amber-950/20 border border-amber-100 dark:border-amber-900/30 rounded-xl p-4 text-sm text-zinc-700 dark:text-zinc-300">
                                <div
                                    class="mb-3 font-medium text-amber-700 dark:text-amber-500 flex items-center gap-2">
                                    <span>📝 {{ t('chat.analysis') }}</span>
                                    <span v-if="msg.feedback.retry_count && msg.feedback.retry_count > 0"
                                        class="text-xs bg-amber-100 text-amber-900 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/15 px-2 py-0.5 rounded border uppercase tracking-wider ml-auto">
                                        Retried: {{ msg.feedback.retry_count }}
                                    </span>
                                </div>

                                <p class="mb-3 italic">{{ msg.feedback.overall }}</p>

                                <div v-if="msg.feedback.corrections && msg.feedback.corrections.length > 0"
                                    class="space-y-3">
                                    <div v-for="(correction, cIndex) in msg.feedback.corrections" :key="cIndex"
                                        class="bg-white/50 dark:bg-black/20 p-3 rounded-lg">
                                        <div class="flex items-start gap-2 mb-1">
                                            <span class="text-red-500 font-mono text-xs mt-0.5">✖</span>
                                            <span class="line-through opacity-60" lang="ja">{{ correction.original
                                                }}</span>
                                        </div>
                                        <div class="flex items-start gap-2 mb-2">
                                            <span class="text-green-500 font-mono text-xs mt-0.5">✔</span>
                                            <span class="font-bold text-emerald-700 dark:text-emerald-400" lang="ja">{{
                                                correction.corrected }}</span>
                                        </div>
                                        <div class="text-xs text-zinc-500 dark:text-zinc-400 pl-5">
                                            💡 {{ correction.explanation }}
                                        </div>
                                    </div>
                                </div>
                                <div v-else class="text-zinc-400 text-xs pl-1">
                                    {{ t('chat.no_errors') }}
                                </div>
                            </div>
                        </transition>
                    </div>
                </div>
            </div>

            <!-- Loading Indicator -->
            <div v-if="isLoading" class="flex justify-start">
                <div class="mr-3 shrink-0">
                    <div
                        class="w-8 h-8 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
                        🤖
                    </div>
                </div>
                <div
                    class="bg-white dark:bg-zinc-800 p-4 rounded-2xl rounded-tl-sm border border-zinc-100 dark:border-zinc-700/50 shadow-sm flex items-center gap-2">
                    <div class="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style="animation-delay: 0s"></div>
                    <div class="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
                    <div class="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
                </div>
            </div>
        </div>

        <!-- Input Area -->
        <div class="py-4 shrink-0">
            <div
                class="relative flex items-end gap-2 bg-white dark:bg-zinc-900 shadow-lg border border-zinc-200 dark:border-zinc-800 rounded-2xl p-2 focus-within:ring-2 focus-within:ring-emerald-500/50 transition-shadow">
                <textarea v-model="inputMessage" @keydown.enter.prevent="sendMessage"
                    :placeholder="t('chat.placeholder')"
                    class="w-full bg-transparent border-0 focus:ring-0 outline-none focus:outline-none resize-none max-h-32 min-h-[50px] py-3 px-3 text-zinc-800 dark:text-zinc-100 placeholder-zinc-400"
                    rows="1"></textarea>
                <button @click="sendMessage" :disabled="!inputMessage.trim() || isLoading"
                    class="mb-1 p-3 rounded-xl bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md active:scale-95">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                        class="lucide lucide-send">
                        <path d="m22 2-7 20-4-9-9-4Z" />
                        <path d="M22 2 11 13" />
                    </svg>
                </button>
            </div>
            <p class="text-center text-xs text-zinc-400 mt-2">
                {{ t('chat.disclaimer') }}
            </p>
        </div>
    </div>
</template>

<style scoped>
/* Custom scrollbar for better blend */
::-webkit-scrollbar {
    width: 6px;
}

::-webkit-scrollbar-track {
    background: transparent;
}

::-webkit-scrollbar-thumb {
    background-color: rgba(156, 163, 175, 0.3);
    border-radius: 20px;
}

.dark ::-webkit-scrollbar-thumb {
    background-color: rgba(71, 85, 105, 0.5);
}
</style>
