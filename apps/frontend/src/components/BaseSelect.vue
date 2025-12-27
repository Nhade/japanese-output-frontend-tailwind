<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';

interface Option {
    value: string | number;
    label: string;
}

const props = withDefaults(defineProps<{
    modelValue: string | number;
    options: (Option | string)[];
    placeholder?: string;
    bordered?: boolean;
}>(), {
    bordered: true
});

const emit = defineEmits<{
    (e: 'update:modelValue', value: string | number): void;
}>();

const isOpen = ref(false);
const containerRef = ref<HTMLElement | null>(null);

const formattedOptions = computed<Option[]>(() => {
    return props.options.map((opt) => {
        if (typeof opt === 'string') {
            return { value: opt, label: opt };
        }
        return opt;
    });
});

const selectedOption = computed(() => {
    return formattedOptions.value.find((opt) => opt.value === props.modelValue);
});

const toggle = () => {
    isOpen.value = !isOpen.value;
};

const select = (option: Option) => {
    emit('update:modelValue', option.value);
    isOpen.value = false;
};

const closeOnClickOutside = (event: MouseEvent) => {
    if (containerRef.value && !containerRef.value.contains(event.target as Node)) {
        isOpen.value = false;
    }
};

onMounted(() => {
    document.addEventListener('click', closeOnClickOutside);
});

onUnmounted(() => {
    document.removeEventListener('click', closeOnClickOutside);
});
</script>

<template>
    <div class="relative inline-block w-full" ref="containerRef">
        <!-- Trigger Button -->
        <button type="button" @click="toggle"
            class="flex w-full items-center justify-between rounded-lg px-3 py-1.5 text-sm font-medium text-zinc-600 transition-colors focus:outline-none focus:ring-1 focus:ring-emerald-500 dark:text-zinc-200"
            :class="[
                bordered
                    ? 'bg-white dark:bg-zinc-900/50 border border-zinc-200 dark:border-white/10 hover:border-zinc-300 dark:hover:border-white/20'
                    : 'bg-transparent border border-transparent hover:border-zinc-200 dark:hover:border-white/10 hover:text-zinc-900 dark:hover:text-white',
                { 'ring-1 ring-emerald-500 border-emerald-500 dark:border-emerald-500': isOpen }
            ]">
            <div class="flex items-center gap-2 truncate">
                <slot name="prefix"></slot>
                <span class="truncate">{{ selectedOption ? selectedOption.label : placeholder || 'Select' }}</span>
            </div>
            <svg class="ml-2 h-4 w-4 text-zinc-400 transition-transform duration-200" :class="{ 'rotate-180': isOpen }"
                xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd"
                    d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                    clip-rule="evenodd" />
            </svg>
        </button>

        <!-- Dropdown Menu -->
        <transition enter-active-class="transition duration-100 ease-out"
            enter-from-class="transform scale-95 opacity-0" enter-to-class="transform scale-100 opacity-100"
            leave-active-class="transition duration-75 ease-in" leave-from-class="transform scale-100 opacity-100"
            leave-to-class="transform scale-95 opacity-0">
            <div v-if="isOpen"
                class="absolute right-0 z-50 mt-1 max-h-60 w-full min-w-max overflow-auto rounded-lg bg-white py-1 shadow-lg ring-1 ring-zinc-200 ring-opacity-100 focus:outline-none dark:bg-zinc-800 dark:ring-white/10 custom-scrollbar">
                <ul class="py-1">
                    <li v-for="option in formattedOptions" :key="option.value" @click="select(option)"
                        class="relative cursor-pointer select-none px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-100 dark:text-zinc-200 dark:hover:bg-zinc-700/50"
                        :class="{ 'text-emerald-600 dark:text-emerald-400 font-medium bg-emerald-50/50 dark:bg-emerald-500/10': modelValue === option.value }">
                        <span class="block truncate whitespace-nowrap">{{ option.label }}</span>
                    </li>
                </ul>
            </div>
        </transition>
    </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
    width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
    background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
    background-color: rgba(161, 161, 170, 0.3);
    /* zinc-400 with opacity */
    border-radius: 3px;
}

.dark .custom-scrollbar::-webkit-scrollbar-thumb {
    background-color: rgba(255, 255, 255, 0.2);
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
    background-color: rgba(161, 161, 170, 0.5);
}

.dark .custom-scrollbar::-webkit-scrollbar-thumb:hover {
    background-color: rgba(255, 255, 255, 0.3);
}
</style>
