import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useToastStore = defineStore('toast', () => {
    const show = ref(false);
    const message = ref('');
    const type = ref<'error' | 'success' | 'info'>('info');

    function trigger(msg: string, t: 'error' | 'success' | 'info' = 'info') {
        message.value = msg;
        type.value = t;
        show.value = true;
    }

    function close() {
        show.value = false;
    }

    return {
        show,
        message,
        type,
        trigger,
        close
    };
});
