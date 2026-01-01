<script setup lang="ts">
import { watch, computed } from 'vue';

const props = defineProps<{
    show: boolean;
    message: string;
    type?: 'error' | 'success' | 'info';
}>();

const emit = defineEmits<{
    (e: 'close'): void;
}>();

// Auto-close after 4 seconds
watch(() => props.show, (newVal) => {
    if (newVal) {
        setTimeout(() => {
            emit('close');
        }, 4000);
    }
});

const containerClasses = computed(() => {
    const baseClasses = 'fixed top-4 right-4 z-50 flex max-w-sm w-full shadow-lg rounded-xl pointer-events-auto border overflow-hidden transition-all duration-300 backdrop-blur-sm';

    switch (props.type) {
        case 'error':
            return `${baseClasses} bg-rose-50 border-rose-200 text-rose-900 dark:bg-rose-900/10 dark:border-rose-500/30 dark:text-zinc-100 shadow-rose-500/10`;
        case 'success':
            return `${baseClasses} bg-emerald-50 border-emerald-200 text-emerald-900 dark:bg-emerald-900/10 dark:border-emerald-500/30 dark:text-zinc-100 shadow-emerald-500/10`;
        case 'info':
        default:
            return `${baseClasses} bg-white border-zinc-200 text-zinc-900 dark:bg-zinc-900/90 dark:border-zinc-700/50 dark:text-zinc-100 shadow-zinc-500/10`;
    }
});

const iconClasses = computed(() => {
    switch (props.type) {
        case 'error': return 'text-rose-500 dark:text-rose-400';
        case 'success': return 'text-emerald-500 dark:text-emerald-400';
        default: return 'text-indigo-500 dark:text-indigo-400';
    }
});

const closeButtonClasses = computed(() => {
    switch (props.type) {
        case 'error': return 'text-rose-400 hover:text-rose-600 dark:text-zinc-400 dark:hover:text-zinc-200 focus:ring-rose-500';
        case 'success': return 'text-emerald-400 hover:text-emerald-600 dark:text-zinc-400 dark:hover:text-zinc-200 focus:ring-emerald-500';
        default: return 'text-zinc-400 hover:text-zinc-600 dark:text-zinc-400 dark:hover:text-zinc-200 focus:ring-indigo-500';
    }
})
</script>

<template>
    <transition enter-active-class="transition ease-out duration-300 transform"
        enter-from-class="translate-y-2 opacity-0 sm:translate-y-0 sm:translate-x-2"
        enter-to-class="translate-y-0 opacity-100 sm:translate-x-0" leave-active-class="transition ease-in duration-200"
        leave-from-class="opacity-100" leave-to-class="opacity-0">
        <div v-if="show" :class="containerClasses">
            <div class="p-4 flex items-start w-full">
                <div class="shrink-0">
                    <!-- Error Icon -->
                    <svg v-if="type === 'error'" :class="['h-6 w-6', iconClasses]" fill="none" viewBox="0 0 24 24"
                        stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <!-- Success Icon -->
                    <svg v-else-if="type === 'success'" :class="['h-6 w-6', iconClasses]" fill="none"
                        viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <!-- Info Icon -->
                    <svg v-else :class="['h-6 w-6', iconClasses]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                </div>
                <div class="ml-3 w-0 flex-1 pt-0.5">
                    <p class="text-sm font-medium">
                        {{ message }}
                    </p>
                </div>
                <div class="ml-4 shrink-0 flex">
                    <button @click="$emit('close')"
                        :class="['bg-transparent rounded-md inline-flex focus:outline-none focus:ring-2', closeButtonClasses]">
                        <span class="sr-only">Close</span>
                        <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd"
                                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                                clip-rule="evenodd" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    </transition>
</template>
