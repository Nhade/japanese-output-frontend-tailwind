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
    <div ref="containerRef" class="ed-select" :class="{ 'is-open': isOpen, 'is-ghost': !bordered }">
        <button
            type="button"
            class="ed-select-trigger"
            :class="{ 'is-bordered': bordered }"
            @click="toggle"
        >
            <span class="ed-select-value">
                <slot name="prefix" />
                <span class="ed-select-label">
                    {{ selectedOption ? selectedOption.label : placeholder || 'Select' }}
                </span>
            </span>
            <svg
                class="ed-select-chevron"
                :class="{ 'is-open': isOpen }"
                width="12"
                height="12"
                viewBox="0 0 20 20"
                aria-hidden="true"
            >
                <path
                    d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                    fill="currentColor"
                    fill-rule="evenodd"
                    clip-rule="evenodd"
                />
            </svg>
        </button>

        <transition
            enter-active-class="ed-fade-in"
            leave-active-class="ed-fade-out"
        >
            <div v-if="isOpen" class="ed-select-menu" role="listbox">
                <ul>
                    <li
                        v-for="option in formattedOptions"
                        :key="option.value"
                        role="option"
                        class="ed-select-option"
                        :class="{ 'is-selected': modelValue === option.value }"
                        :aria-selected="modelValue === option.value"
                        @click="select(option)"
                    >
                        {{ option.label }}
                    </li>
                </ul>
            </div>
        </transition>
    </div>
</template>

<style scoped>
/* Editorial select — warm paper surface, serif labels, kohaku underline
   on hover/selection. Uses the shared editorial tokens so it matches the
   Shiori shell everywhere it appears (header language toggle, filter UI). */
.ed-select {
    position: relative;
    display: inline-block;
    width: 100%;
}

.ed-select-trigger {
    display: flex;
    width: 100%;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 6px 10px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 2px;
    font-family: var(--font-sans);
    font-size: 0.82rem;
    letter-spacing: 0.08em;
    color: color-mix(in oklab, var(--foreground) 70%, transparent);
    cursor: pointer;
    transition: color 160ms ease, border-color 160ms ease, background 160ms ease;
}
.ed-select-trigger.is-bordered {
    background: var(--background);
    border-color: color-mix(in oklab, var(--foreground) 14%, transparent);
}
.ed-select-trigger:hover {
    color: var(--foreground);
    border-color: color-mix(in oklab, var(--foreground) 28%, transparent);
}
.ed-select-trigger:focus-visible {
    outline: none;
    border-color: var(--secondary);
    box-shadow: 0 1px 0 0 var(--secondary);
}
.ed-select.is-open .ed-select-trigger {
    color: var(--foreground);
    border-color: var(--secondary);
}

.ed-select-value {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
}
.ed-select-label {
    font-family: var(--font-serif);
    font-size: 0.95rem;
    letter-spacing: 0;
    color: inherit;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.ed-select-chevron {
    flex-shrink: 0;
    color: color-mix(in oklab, var(--foreground) 45%, transparent);
    transition: transform 180ms ease;
}
.ed-select-chevron.is-open { transform: rotate(180deg); }

/* Menu ------------------------------------------------------ */
.ed-select-menu {
    position: absolute;
    right: 0;
    top: calc(100% + 4px);
    z-index: 50;
    min-width: 100%;
    background: var(--background);
    border: 1px solid color-mix(in oklab, var(--foreground) 12%, transparent);
    border-radius: 2px;
    box-shadow: 0 6px 20px color-mix(in oklab, var(--foreground) 10%, transparent);
    overflow: hidden;
}
.ed-select-menu ul {
    list-style: none;
    margin: 0;
    padding: 4px 0;
    max-height: 260px;
    overflow-y: auto;
}
.ed-select-option {
    padding: 8px 14px;
    font-family: var(--font-serif);
    font-size: 0.95rem;
    color: color-mix(in oklab, var(--foreground) 78%, transparent);
    cursor: pointer;
    white-space: nowrap;
    border-left: 2px solid transparent;
    transition: color 140ms ease, background 140ms ease, border-color 140ms ease;
}
.ed-select-option:hover {
    color: var(--foreground);
    background: color-mix(in oklab, var(--foreground) 4%, transparent);
}
.ed-select-option.is-selected {
    color: var(--foreground);
    font-style: italic;
    background: color-mix(in oklab, var(--secondary) 10%, transparent);
    border-left-color: var(--secondary);
}
.ed-select-option.is-selected:hover {
    background: color-mix(in oklab, var(--secondary) 16%, transparent);
}

/* Transitions ---------------------------------------------- */
.ed-fade-in {
    animation: ed-select-in 120ms ease-out;
}
.ed-fade-out {
    animation: ed-select-out 80ms ease-in forwards;
}
@keyframes ed-select-in {
    from { opacity: 0; transform: translateY(-2px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes ed-select-out {
    from { opacity: 1; transform: translateY(0); }
    to   { opacity: 0; transform: translateY(-2px); }
}
</style>
