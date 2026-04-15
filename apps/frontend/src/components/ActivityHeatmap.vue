<template>
  <div class="overflow-x-auto">
    <div class="inline-flex gap-[3px]">
      <!-- Day-of-week labels -->
      <div class="flex flex-col gap-[3px] pr-1">
        <div class="h-[15px]"></div>
        <div v-for="(label, i) in dayLabels" :key="i"
          class="h-[13px] text-[10px] leading-[13px] text-zinc-400 dark:text-zinc-500 select-none">
          {{ label }}
        </div>
      </div>

      <!-- Grid area -->
      <div class="flex flex-col gap-[3px]">
        <!-- Month labels row -->
        <div class="flex gap-[3px] h-[15px]">
          <div v-for="wi in weeks.length" :key="wi - 1"
            class="w-[13px] text-[10px] leading-[15px] text-zinc-400 dark:text-zinc-500 select-none">
            {{ monthLabels[wi - 1] || '' }}
          </div>
        </div>

        <!-- Heatmap grid (transposed: 7 rows x N columns) -->
        <div v-for="dayIndex in 7" :key="dayIndex" class="flex gap-[3px]">
          <template v-for="(week, wi) in weeks" :key="wi">
            <div v-if="week[dayIndex - 1]" class="w-[13px] h-[13px] rounded-sm transition-colors"
              :style="{ backgroundColor: getCellColor(week[dayIndex - 1]!.count) }"
              :title="getCellTooltip(week[dayIndex - 1]!)"></div>
            <div v-else class="w-[13px] h-[13px]"></div>
          </template>
        </div>
      </div>
    </div>

    <!-- Legend -->
    <div class="flex items-center gap-2 mt-3 text-[11px] text-zinc-400 dark:text-zinc-500">
      <span>{{ lessLabel }}</span>
      <div v-for="level in 5" :key="level" class="w-[13px] h-[13px] rounded-sm"
        :style="{ backgroundColor: getCellColor(levelThresholds[level - 1]) }"></div>
      <span>{{ moreLabel }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useThemeStore } from '../stores/theme';
import { useI18n } from 'vue-i18n';

interface DayData {
  date: string;
  total: number;
}

const props = withDefaults(defineProps<{
  data: DayData[];
  lessLabel?: string;
  moreLabel?: string;
  tooltipSuffix?: string;
}>(), {
  lessLabel: 'Less',
  moreLabel: 'More',
  tooltipSuffix: 'exercises',
});

const themeStore = useThemeStore();
const { t, locale } = useI18n();

const lightColors = ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39'];
const darkColors = ['rgba(255,255,255,0.05)', '#0e4429', '#006d32', '#26a641', '#39d353'];

const levelThresholds = [0, 1, 3, 6, 10];

const dayLabels = computed(() => {
  const getDayName = (dayIndex: number) => {
    // 2024-01-01 is Monday (1). 2024-01-01 + dayIndex
    const d = new Date(2024, 0, dayIndex);
    return new Intl.DateTimeFormat(locale.value, { weekday: 'short' }).format(d);
  };
  return ['', getDayName(1), '', getDayName(3), '', getDayName(5), ''];
});

const dataMap = computed(() => {
  const map = new Map<string, number>();
  props.data.forEach(d => map.set(d.date, d.total));
  return map;
});

const weeks = computed(() => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  // Go back ~52 weeks, start from Sunday
  const start = new Date(today);
  start.setDate(start.getDate() - 364);
  // Roll back to Sunday
  start.setDate(start.getDate() - start.getDay());

  const result: ({ dateStr: string; count: number } | null)[][] = [];
  const current = new Date(start);

  while (current <= today) {
    const week: ({ dateStr: string; count: number } | null)[] = [];
    for (let d = 0; d < 7; d++) {
      if (current > today) {
        week.push(null);
      } else {
        const dateStr = formatDate(current);
        week.push({
          dateStr,
          count: dataMap.value.get(dateStr) || 0,
        });
      }
      current.setDate(current.getDate() + 1);
    }
    result.push(week);
  }

  return result;
});

const monthLabels = computed(() => {
  const labels: Record<number, string> = {};
  let lastMonth = -1;

  weeks.value.forEach((week, wi) => {
    // Check the first non-null day in the week
    const firstDay = week.find(d => d !== null);
    if (firstDay) {
      const month = parseInt(firstDay.dateStr.split('-')[1], 10) - 1;
      if (month !== lastMonth) {
        const d = new Date(2024, month, 1);
        labels[wi] = new Intl.DateTimeFormat(locale.value, { month: 'short' }).format(d);
        lastMonth = month;
      }
    }
  });

  return labels;
});

function formatDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function getLevel(count: number): number {
  if (count === 0) return 0;
  if (count <= 2) return 1;
  if (count <= 5) return 2;
  if (count <= 9) return 3;
  return 4;
}

function getCellColor(count: number): string {
  const level = getLevel(count);
  return themeStore.theme === 'dark' ? darkColors[level] : lightColors[level];
}

function getCellTooltip(day: { dateStr: string; count: number }): string {
  if (day.count === 0) {
    return t('statistics.heatmap_tooltip_zero', { date: day.dateStr });
  }
  return t('statistics.heatmap_tooltip', { count: day.count, date: day.dateStr });
}
</script>
