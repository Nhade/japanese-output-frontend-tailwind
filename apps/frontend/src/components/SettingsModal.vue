<script setup lang="ts">
import { ref, watch } from 'vue';
import Modal from './Modal.vue';
import { useAuthStore } from '../stores/auth';
import { useToastStore } from '../stores/toast';
import { useI18n } from 'vue-i18n';

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
const feedbackPref = ref('gentle');

const jlptOptions = ['N5', 'N4', 'N3', 'N2', 'N1'];
const prefOptions = [
    { value: 'gentle', label: 'settings.pref_gentle' },
    { value: 'normal', label: 'settings.pref_normal' },
    { value: 'strict', label: 'settings.pref_strict' },
];


watch(() => props.show, async (newVal) => {
    if (newVal && auth.user_id) {
        try {
            const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/learner/profile/${auth.user_id}`);
            if (res.ok) {
                const data = await res.json();
                if (data.level_est) jlptLevel.value = data.level_est;
                if (data.feedback_preference) feedbackPref.value = data.feedback_preference;
            }
        } catch (e) {
            console.error(e);
        }
    }
});

const saveSettings = async () => {
    if (!auth.user_id) return;
    isLoading.value = true;

    try {
        const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/users/profile`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: auth.user_id,
                settings: {
                    level_est: jlptLevel.value,
                    feedback_preference: feedbackPref.value
                }
            })
        });

        if (res.ok) {
            toast.trigger(t('settings.saved_success'), 'success');
            emit('updated');
            emit('close');
        } else {
            toast.trigger(t('auth.error_generic'), 'error');
        }
    } catch (e) {
        toast.trigger(t('exercise.network_error'), 'error');
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <Modal :show="show" :title="t('settings.title')" @close="emit('close')">
        <div class="space-y-6">

            <!-- JLPT Level -->
            <div>
                <label class="block text-sm font-medium mb-2 text-zinc-700 dark:text-zinc-300">
                    {{ t('settings.jlpt_level') }}
                </label>
                <div class="flex gap-2">
                    <button v-for="level in jlptOptions" :key="level" @click="jlptLevel = level"
                        :class="['px-4 py-2 rounded-lg text-sm font-medium transition-all border',
                            jlptLevel === level
                                ? 'bg-emerald-500 text-white border-emerald-500 shadow-emerald-500/30 shadow-sm'
                                : 'bg-white text-zinc-600 border-zinc-200 hover:bg-zinc-50 dark:bg-zinc-800 dark:border-white/10 dark:text-zinc-400 dark:hover:bg-zinc-700']">
                        {{ level }}
                    </button>
                </div>
            </div>

            <!-- Feedback Preference -->
            <div>
                <label class="block text-sm font-medium mb-2 text-zinc-700 dark:text-zinc-300">
                    {{ t('settings.feedback_preference') }}
                </label>
                <div class="grid grid-cols-1 gap-2">
                    <button v-for="opt in prefOptions" :key="opt.value" @click="feedbackPref = opt.value"
                        :class="['px-4 py-3 rounded-lg text-left text-sm transition-all border flex items-center justify-between',
                            feedbackPref === opt.value
                                ? 'bg-indigo-50 border-indigo-500 text-indigo-700 ring-1 ring-indigo-500/50 dark:bg-indigo-500/20 dark:text-indigo-200'
                                : 'bg-white border-zinc-200 text-zinc-700 hover:border-zinc-300 dark:bg-zinc-800 dark:border-white/10 dark:text-zinc-300 dark:hover:border-zinc-600']">
                        <span>{{ t(opt.label) }}</span>
                        <span v-if="feedbackPref === opt.value">✓</span>
                    </button>
                </div>
            </div>

            <!-- Save Button -->
            <div class="pt-2">
                <button @click="saveSettings" :disabled="isLoading"
                    class="w-full rounded-xl py-3 font-medium text-white shadow-lg transition-all active:scale-[0.98] bg-gradient-to-br from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 shadow-indigo-500/25 dark:shadow-indigo-900/40 disabled:opacity-70 disabled:cursor-not-allowed">
                    <span v-if="isLoading">Saving...</span>
                    <span v-else>{{ t('settings.save') }}</span>
                </button>
            </div>

        </div>
    </Modal>
</template>
