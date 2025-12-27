<template>
  <div class="p-6 pt-10 min-h-screen text-zinc-900 dark:text-zinc-100 font-sans pb-24">
    <div class="max-w-7xl mx-auto space-y-8">

      <!-- Header Section -->
      <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1
            class="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-indigo-500 to-violet-500 bg-clip-text text-transparent">
            {{ $t('statistics.title') }}
          </h1>
          <p class="text-zinc-500 dark:text-zinc-400 mt-1">
            {{ $t('statistics.subtitle') }}
          </p>
        </div>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="flex justify-center items-center py-20">
        <LoadingSpinner class="w-10 h-10 text-indigo-500" />
      </div>

      <!-- Main Content -->
      <div v-else-if="hasData" class="space-y-6 animate-fade-in">

        <!-- Summary Cards -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <!-- Total Exercises -->
          <div
            class="bg-white dark:bg-zinc-900/60 p-6 rounded-xl shadow-sm shadow-zinc-200/50 border border-zinc-200 dark:border-white/10 dark:shadow-none flex flex-col items-center text-center hover:scale-[1.02] transition-all duration-300 dark:hover:bg-white/5 dark:hover:border-white/20">
            <div class="text-zinc-500 dark:text-zinc-400 text-sm font-medium mb-1">{{ $t('statistics.total_exercises')
            }}</div>
            <div class="text-3xl font-bold text-zinc-800 dark:text-zinc-100">{{ summaryData.total_exercises }}</div>
          </div>

          <!-- Total Correct -->
          <div
            class="bg-white dark:bg-zinc-900/60 p-6 rounded-xl shadow-sm shadow-zinc-200/50 border border-zinc-200 dark:border-white/10 dark:shadow-none flex flex-col items-center text-center hover:scale-[1.02] transition-all duration-300 dark:hover:bg-white/5 dark:hover:border-white/20">
            <div class="text-zinc-500 dark:text-zinc-400 text-sm font-medium mb-1">{{ $t('statistics.total_correct') }}
            </div>
            <div class="text-3xl font-bold text-emerald-500">{{ summaryData.total_correct }}</div>
          </div>

          <!-- Average Accuracy -->
          <div
            class="bg-white dark:bg-zinc-900/60 p-6 rounded-xl shadow-sm shadow-zinc-200/50 border border-zinc-200 dark:border-white/10 dark:shadow-none flex flex-col items-center text-center hover:scale-[1.02] transition-all duration-300 dark:hover:bg-white/5 dark:hover:border-white/20">
            <div class="text-zinc-500 dark:text-zinc-400 text-sm font-medium mb-1">{{ $t('statistics.average_accuracy')
            }}</div>
            <div class="text-3xl font-bold text-indigo-500">{{ summaryData.average_accuracy.toFixed(1) }}%</div>
          </div>
        </div>

        <!-- Charts Grid -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

          <!-- History Chart -->
          <div
            class="bg-white dark:bg-zinc-900/60 rounded-xl shadow-sm shadow-zinc-200/50 border border-zinc-200 dark:border-white/10 dark:shadow-none p-6 flex flex-col hover:shadow-md dark:hover:shadow-none transition-all duration-300 dark:hover:bg-white/5 dark:hover:border-white/20">
            <h2 class="text-lg font-semibold mb-4 flex items-center gap-2">
              <span class="w-2 h-8 bg-indigo-500 rounded-full"></span>
              {{ $t('statistics.history') }}
            </h2>
            <div class="grow relative h-64 w-full">
              <Line :data="historyChartData" :options="lineChartOptions" />
            </div>
            <p class="text-xs text-center text-zinc-400 mt-4">{{ $t('statistics.history_desc') }}</p>
          </div>

          <!-- PoS Radar Chart -->
          <div
            class="bg-white dark:bg-zinc-900/60 rounded-xl shadow-sm shadow-zinc-200/50 border border-zinc-200 dark:border-white/10 dark:shadow-none p-6 flex flex-col hover:shadow-md dark:hover:shadow-none transition-all duration-300 dark:hover:bg-white/5 dark:hover:border-white/20">
            <h2 class="text-lg font-semibold mb-4 flex items-center gap-2">
              <span class="w-2 h-8 bg-rose-500 rounded-full"></span>
              {{ $t('statistics.accuracy_pos') }}
            </h2>
            <div class="grow relative h-64 w-full flex justify-center items-center">
              <Radar :data="posRadarData" :options="radarOptions" />
            </div>
            <p class="text-xs text-center text-zinc-400 mt-4">{{ $t('statistics.pos_desc') }}</p>
          </div>

          <!-- JLPT Bar Chart -->
          <div
            class="lg:col-span-2 bg-white dark:bg-zinc-900/60 rounded-xl shadow-sm shadow-zinc-200/50 border border-zinc-200 dark:border-white/10 dark:shadow-none p-6 flex flex-col hover:shadow-md dark:hover:shadow-none transition-all duration-300 dark:hover:bg-white/5 dark:hover:border-white/20">
            <h2 class="text-lg font-semibold mb-4 flex items-center gap-2">
              <span class="w-2 h-8 bg-emerald-500 rounded-full"></span>
              {{ $t('statistics.accuracy_jlpt') }}
            </h2>
            <div class="grow relative h-64 w-full">
              <Bar :data="jlptAccuracyData" :options="barOptions" />
            </div>
          </div>

        </div>

      </div>

      <!-- Empty State -->
      <div v-else class="flex flex-col items-center justify-center py-20 text-center space-y-4">
        <div class="bg-zinc-100 dark:bg-zinc-800 p-6 rounded-full">
          <svg class="w-12 h-12 text-zinc-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z">
            </path>
          </svg>
        </div>
        <h3 class="text-xl font-medium text-zinc-900 dark:text-zinc-100">{{ $t('statistics.no_data') }}</h3>
        <p class="text-zinc-500 dark:text-zinc-400 max-w-sm">
          Complete some exercises to see your learning statistics here!
        </p>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useAuthStore } from '../stores/auth';
import LoadingSpinner from '../components/LoadingSpinner.vue';
import { Bar, Radar, Line } from 'vue-chartjs';
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler
} from 'chart.js';

ChartJS.register(
  Title,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler
);

const auth = useAuthStore();
const loading = ref(true);
const hasData = ref(false);

const summaryData = ref({
  total_exercises: 0,
  total_correct: 0,
  average_accuracy: 0
});

// --- Chart Options ---

const commonOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false,
    },
    tooltip: {
      backgroundColor: '#18181b', // zinc-900
      titleColor: '#f4f4f5', // zinc-100
      bodyColor: '#e4e4e7', // zinc-200
      padding: 10,
      cornerRadius: 8,
      displayColors: false,
    }
  },
};

const barOptions = {
  ...commonOptions,
  scales: {
    y: {
      beginAtZero: true,
      max: 100,
      grid: {
        color: '#3f3f46', // zinc-700
        lineWidth: 0.5,
        borderDash: [5, 5],
      },
      ticks: { color: '#a1a1aa' } // zinc-400
    },
    x: {
      grid: { display: false },
      ticks: { color: '#a1a1aa' }
    }
  }
};

const lineOptions = {
  ...commonOptions,
  scales: {
    y: {
      beginAtZero: true,
      max: 100,
      grid: {
        color: 'rgba(63, 63, 70, 0.3)',
        lineWidth: 0.5,
        borderDash: [5, 5],
      },
      ticks: { color: '#a1a1aa' }
    },
    x: {
      grid: { display: false },
      ticks: { color: '#a1a1aa' }
    }
  },
  elements: {
    line: {
      tension: 0.4, // smooth curves
    },
    point: {
      radius: 4,
      hoverRadius: 6,
    }
  }
};

const radarOptions = {
  ...commonOptions,
  scales: {
    r: {
      angleLines: {
        color: 'rgba(161, 161, 170, 0.2)'
      },
      grid: {
        color: 'rgba(161, 161, 170, 0.2)'
      },
      pointLabels: {
        color: '#a1a1aa',
        font: {
          size: 12
        }
      },
      ticks: {
        display: false,
        backdropColor: 'transparent'
      },
      min: 0,
      max: 100,
    }
  }
};

// --- Data Refs ---

const posRadarData = ref({
  labels: [] as string[],
  datasets: [] as any[]
});

const jlptAccuracyData = ref({
  labels: [] as string[],
  datasets: [] as any[]
});

const historyChartData = ref({
  labels: [] as string[],
  datasets: [] as any[]
});


onMounted(async () => {
  if (auth.user_id) {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/statistics/${auth.user_id}`);
      if (response.ok) {
        const stats = await response.json();

        // Check if we have any data to show
        const hasPos = Object.keys(stats.pos_accuracy).length > 0;
        const hasJlpt = Object.keys(stats.jlpt_level_accuracy).length > 0;
        const hasHistory = stats.history && stats.history.length > 0;

        hasData.value = hasPos || hasJlpt || hasHistory;

        if (stats.summary) {
          summaryData.value = stats.summary;
        }

        if (hasData.value) {
          // 1. PoS Radar Data
          const posLabels = Object.keys(stats.pos_accuracy);
          const posValues = Object.values(stats.pos_accuracy);

          posRadarData.value = {
            labels: posLabels,
            datasets: [{
              label: 'Accuracy',
              data: posValues,
              backgroundColor: 'rgba(244, 63, 94, 0.2)', // rose-500 with opacity
              borderColor: '#f43f5e', // rose-500
              borderWidth: 2,
              pointBackgroundColor: '#f43f5e',
              pointBorderColor: '#fff',
            }]
          };

          // 2. JLPT Bar Data
          const jlptLabels = Object.keys(stats.jlpt_level_accuracy);
          const jlptValues = Object.values(stats.jlpt_level_accuracy);

          jlptAccuracyData.value = {
            labels: jlptLabels,
            datasets: [{
              label: 'Accuracy',
              data: jlptValues,
              backgroundColor: '#10b981', // emerald-500
              borderRadius: 6,
              barThickness: 30,
            }]
          };

          // 3. History Line Data
          if (stats.history) {
            const historyLabels = stats.history.map((h: any) => h.date);
            const historyValues = stats.history.map((h: any) => h.accuracy);

            historyChartData.value = {
              labels: historyLabels,
              datasets: [{
                label: 'Daily Accuracy',
                data: historyValues,
                borderColor: '#6366f1', // indigo-500
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                borderWidth: 3,
                fill: true,
              }]
            };
          }
        }
      }
    } catch (error) {
      console.error('Error fetching statistics:', error);
    } finally {
      loading.value = false;
    }
  }
});

// expose options to template
const lineChartOptions = lineOptions;
</script>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.5s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
