<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

interface FocusData {
    tag: string;
    progress: number;
    target: number;
}

const props = defineProps<{
    focus: FocusData;
}>();

const { t } = useI18n();

const progressPercent = computed(() => {
    if (!props.focus.target) return 0;
    return Math.min(100, (props.focus.progress / props.focus.target) * 100);
});

const isComplete = computed(() => {
    return props.focus.progress >= props.focus.target;
});
</script>

<template>
    <div
        class="bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-100 dark:border-indigo-800/30 rounded-lg p-3 w-full">
        <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
                <span class="text-xl">🎯</span>
                <span class="font-bold text-indigo-900 dark:text-indigo-200 text-sm">
                    {{ t('chat.focus_title', '学習重点') }}
                </span>
                <span
                    class="bg-indigo-100 dark:bg-indigo-800 text-indigo-700 dark:text-indigo-300 px-2 py-0.5 rounded text-xs font-semibold">
                    {{ t('pos.' + (props.focus.tag ? props.focus.tag.toLowerCase() : 'general'), props.focus.tag) }}
                </span>
            </div>
            <div v-if="isComplete"
                class="text-xs font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                <span>{{ t('common.complete', 'Complete!') }}</span>
                <span>🎉</span>
            </div>
            <div v-else class="text-xs text-indigo-400 dark:text-indigo-400 font-mono">
                {{ props.focus.progress }} / {{ props.focus.target }}
            </div>
        </div>

        <!-- Progress Bar -->
        <!-- Progress Bar -->
        <div class="h-2 w-full bg-indigo-200 dark:bg-indigo-900/50 rounded-full overflow-hidden">
            <div class="h-full bg-indigo-500 transition-all duration-500 ease-out flex shadow-[0_0_10px_rgba(99,102,241,0.5)]"
                :style="{ width: `${progressPercent}%` }">
                <!-- Striped pattern (optional css tricks usually, keeping simple here) -->
            </div>
        </div>

        <div v-if="isComplete" class="mt-2 text-xs text-center text-indigo-600 dark:text-indigo-300">
            {{ t('chat.focus_complete_msg', 'Great job! Keep practicing or check back later for a new focus.') }}
        </div>
        <div v-else class="mt-2 text-[10px] text-center text-indigo-300 dark:text-indigo-500/50">
            {{ t('chat.focus_explainer', 'This focus is automatically selected based on recent errors.') }}
        </div>
    </div>
</template>
