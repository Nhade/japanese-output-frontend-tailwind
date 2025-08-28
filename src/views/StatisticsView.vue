<template>
  <div class="p-4 bg-zinc-950 text-zinc-100 pt-10">
    <h1 class="text-xl font-bold my-6">Statistics</h1>
    <div v-if="loading" class="flex justify-center items-center">
      <LoadingSpinner />
    </div>
    <div v-if="!loading && (posAccuracyData.labels.length > 0 || jlptAccuracyData.labels.length > 0)">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <h2 class="text-xl font-semibold mb-2">Accuracy by Part of Speech</h2>
          <Bar :data="posAccuracyData" :options="chartOptions" />
        </div>
        <div>
          <h2 class="text-xl font-semibold mb-2">Accuracy by JLPT Level</h2>
          <Bar :data="jlptAccuracyData" :options="chartOptions" />
        </div>
      </div>
    </div>
    <div v-if="!loading && posAccuracyData.labels.length === 0 && jlptAccuracyData.labels.length === 0" class="text-center text-gray-500">
      <p>No statistics available yet. Complete some exercises to see your progress.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useAuthStore } from '../stores/auth';
import LoadingSpinner from '../components/LoadingSpinner.vue';
import { Bar } from 'vue-chartjs';
import { Chart as ChartJS, Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale } from 'chart.js';

ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale);

const auth = useAuthStore();
const loading = ref(true);

const chartOptions = {
  scales: {
    y: {
      beginAtZero: true,
      max: 100,
    },
  },
  plugins: {
    legend: {
      display: false,
    },
  },
};

const posAccuracyData = ref({
  labels: [] as string[],
  datasets: [
    {
      label: 'Accuracy',
      backgroundColor: '#F18701',
      data: [] as number[],
    },
  ],
});

const jlptAccuracyData = ref({
  labels: [] as string[],
  datasets: [
    {
      label: 'Accuracy',
      backgroundColor: '#DB324D',
      data: [] as number[],
    },
  ],
});

onMounted(async () => {
  if (auth.user_id) {
    try {
      const response = await fetch(`/api/statistics/${auth.user_id}`);
      if (response.ok) {
        const stats = await response.json();
        
        const posLabels = Object.keys(stats.pos_accuracy);
        const posData = Object.values(stats.pos_accuracy);
        posAccuracyData.value = {
          labels: posLabels,
          datasets: [
            {
              label: 'Accuracy',
              backgroundColor: '#F18701',
              data: posData as number[],
            },
          ],
        };

        const jlptLabels = Object.keys(stats.jlpt_level_accuracy);
        const jlptData = Object.values(stats.jlpt_level_accuracy);
        jlptAccuracyData.value = {
          labels: jlptLabels,
          datasets: [
            {
              label: 'Accuracy',
              backgroundColor: '#DB324D',
              data: jlptData as number[],
            },
          ],
        };
      }
    } catch (error) {
      console.error('Error fetching statistics:', error);
    } finally {
      loading.value = false;
    }
  }else{
    console.log("no user");
  }
});
</script>
