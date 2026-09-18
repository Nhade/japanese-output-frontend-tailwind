// Single source of truth for the About page and the tour's "Learn more"
// drawer. Copy lives in the locale files under `about.sections.<id>.*`
// (title, lede, b1..bN, note); this file only lists the sections, their
// order, and where "Try it" points.

export interface AboutSectionDef {
  id: string;
  /** Route the "Try it" link opens; omit for sections without a page of their own. */
  tryTo?: string;
  /** Number of how-it-works bullets (`about.sections.<id>.b1` … `bN`). */
  bullets: number;
}

export const ABOUT_SECTIONS: readonly AboutSectionDef[] = [
  { id: 'overview', bullets: 3 },
  { id: 'exercise', tryTo: '/study/exercise', bullets: 3 },
  { id: 'tutor', tryTo: '/chat', bullets: 3 },
  { id: 'safety', tryTo: '/chat', bullets: 3 },
  { id: 'review', tryTo: '/mistakes', bullets: 3 },
  { id: 'memory', tryTo: '/statistics', bullets: 3 },
  { id: 'reading', tryTo: '/news', bullets: 3 },
  { id: 'video', tryTo: '/videos', bullets: 2 },
  { id: 'practice', tryTo: '/practice', bullets: 3 },
  { id: 'models', bullets: 3 },
  { id: 'preview', tryTo: '/preview', bullets: 3 },
];

export const GITHUB_URL = 'https://github.com/Nhade/japanese-output-frontend-tailwind';

export function aboutKey(id: string, field: string): string {
  return `about.sections.${id}.${field}`;
}
