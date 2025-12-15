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
  <transition name="modal-fade">
    <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center p-4" aria-modal="true" role="dialog">
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="close"></div>

      <!-- Modal Card -->
      <div class="relative w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden rounded-2xl bg-zinc-900 border border-white/10 shadow-2xl shadow-black/50">
        
        <!-- Header -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-zinc-900/95 sticky top-0 z-10">
          <h2 class="text-lg font-semibold text-zinc-100">{{ title }}</h2>
          <button @click="close" class="rounded-lg p-2 text-zinc-400 hover:bg-white/5 hover:text-white transition-colors">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Scrollable Content -->
        <div class="flex-1 overflow-y-auto px-6 py-6 custom-scrollbar">
          <slot></slot>
        </div>

        <!-- Footer (Optional, can be used for actions) -->
        <div v-if="$slots.footer" class="border-t border-white/5 bg-zinc-900/50 px-6 py-4">
            <slot name="footer"></slot>
        </div>

      </div>
    </div>
  </transition>
</template>

<style scoped>
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
  transform: scale(0.95);
}

.modal-fade-enter-to,
.modal-fade-leave-from {
  opacity: 1;
  transform: scale(1);
}

/* Custom Scrollbar */
.custom-scrollbar::-webkit-scrollbar {
  width: 8px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.02);
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
