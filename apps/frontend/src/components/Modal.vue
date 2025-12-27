<script setup>
import { onMounted, onUnmounted } from 'vue';

const props = defineProps({
  show: {
    type: Boolean,
    required: true,
  },
  title: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['close']);

function close() {
  emit('close');
}

function handleKeydown(e) {
  if (e.key === 'Escape' && props.show) {
    close();
  }
}

onMounted(() => window.addEventListener('keydown', handleKeydown));
onUnmounted(() => window.removeEventListener('keydown', handleKeydown));
</script>

<template>
  <transition name="modal-entry">
    <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center p-4" aria-modal="true" role="dialog">
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/50 backdrop-blur-sm dark:bg-black/60 backdrop transition-opacity"
        @click="close"></div>

      <!-- Modal Card -->
      <div class="relative w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden rounded-2xl
               bg-white border border-zinc-200 shadow-2xl shadow-black/10
               dark:bg-zinc-900 dark:ring-1 dark:ring-emerald-400/20 dark:border-white/10 dark:shadow-black/50
               modal-card transition-all" @click.stop>
        <!-- Header -->
        <div class="flex items-center justify-between px-6 py-4 border-b sticky top-0 z-10
                    border-zinc-200 bg-white/90
                    dark:border-white/10 dark:bg-zinc-900/60">
          <h2 class="text-lg font-semibold text-zinc-900 dark:text-zinc-100">{{ title }}</h2>
          <button @click="close"
            class="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 transition-colors
                   dark:text-zinc-400 dark:hover:bg-white/7 dark:hover:text-white
                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400/40 dark:focus-visible:ring-white/20">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Scrollable Content -->
        <div class="flex-1 overflow-y-auto px-6 py-6 custom-scrollbar">
          <slot></slot>
        </div>

        <!-- Footer (Optional) -->
        <div v-if="$slots.footer" class="border-t px-6 py-4 border-zinc-200 bg-zinc-50
                 dark:border-white/10 dark:bg-white/5">
          <slot name="footer"></slot>
        </div>
      </div>
    </div>
  </transition>
</template>


<style scoped>
/* Root Transition: controls existence */
.modal-entry-enter-active,
.modal-entry-leave-active {
  transition: opacity 0.3s ease;
}

/* 
  Nested Transitions 
  We target inner elements when the ROOT is in entering/leaving state.
*/

/* 1. Backdrop Fade */
.modal-entry-enter-from .backdrop,
.modal-entry-leave-to .backdrop {
  opacity: 0;
}

.modal-entry-enter-to .backdrop,
.modal-entry-leave-from .backdrop {
  opacity: 1;
}

/* 2. Modal Card Pop/Scale */
.modal-entry-enter-active .modal-card {
  transition: opacity 0.3s ease, transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-entry-leave-active .modal-card {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.modal-entry-enter-from .modal-card {
  opacity: 0;
  transform: translateY(8px) scale(0.96);
}

.modal-entry-enter-to .modal-card {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.modal-entry-leave-from .modal-card {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.modal-entry-leave-to .modal-card {
  opacity: 0;
  transform: translateY(4px) scale(0.98);
}


/* Custom Scrollbar */
.custom-scrollbar::-webkit-scrollbar {
  width: 8px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.04);
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 4px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.25);
}

/* Dark mode override */
:global(.dark) .custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.03);
}

:global(.dark) .custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.18);
}

:global(.dark) .custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
