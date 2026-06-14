// Exam practice bank — loads the 1142 final-exam MCQ set shipped as a
// normalized JSON under /data/exam. Generated from the 完全マスター N4 green-book
// scans (study_pack/build.py); answers verified against the printed keys
// (p.284 / p.295) and the student's handwritten answers.
//
// Stays entirely client-side, like lib/practice.ts — not wired to the AI
// exercise log.

export type ExamSection = 'a' | 'b' | 'c';

// One gap in a question. `correct` is a 0-based index into `options`.
export interface ExamBlank {
  label: string;          // '' for single/classify, '①'/'②' for multi-blank
  options: string[];
  correct: number;
}

export interface ExamQuestion {
  id: string;
  section: ExamSection;
  section_label: string;  // Japanese label, e.g. 使役受け身・総合
  unit: string;
  block: string;          // 問題1 / 練習 / II 助詞 …
  q_no: string;
  page: number;
  kind: 'single' | 'multi' | 'classify';
  prompt: string;         // contains （　） / （　①　）（　②　） blank markers
  blanks: ExamBlank[];
  answer_display: string; // human-readable answer, e.g. ①やめさせて ②やめられる
  grammar_point: string;
  explanation_zh: string;
  source: string;         // e.g. key p.284
  confidence: string;     // high | check
}

interface ExamBankFile {
  questions: ExamQuestion[];
}

export const EXAM_SECTIONS: readonly ExamSection[] = ['a', 'b', 'c'];

// Where a question comes from: the textbook (verified against the printed
// answer keys) or the AI-generated extra-practice set. Generated items carry a
// `gen-` id prefix and confidence "generated".
export type ExamOrigin = 'textbook' | 'generated';

export function questionOrigin(q: ExamQuestion): ExamOrigin {
  return q.id.startsWith('gen-') || q.confidence === 'generated' ? 'generated' : 'textbook';
}

let cache: Promise<ExamQuestion[]> | null = null;

export async function loadExamBank(): Promise<ExamQuestion[]> {
  if (cache) return cache;
  cache = (async () => {
    const res = await fetch(`${import.meta.env.BASE_URL}data/exam/combined_bank.json`);
    if (!res.ok) throw new Error(`Failed to load exam bank: ${res.status}`);
    const data = (await res.json()) as ExamBankFile;
    return data.questions ?? [];
  })();
  return cache;
}

// ---- Prompt segmentation --------------------------------------------------
// Blank markers are full-width parens holding only spaces and an optional
// circled index: （　）, （　①　）, （　②　）.
const BLANK_RE = /（[\s　]*([①②③④⑤]?)[\s　]*）/g;

export interface PromptSegment {
  kind: 'text' | 'blank';
  text: string;
  /** Index into `question.blanks` this marker maps to (blank segments only). */
  blankIndex?: number;
}

// Split a prompt into text / blank segments. For multi-blank questions each
// marker maps to its own blank in order; for single-blank questions every
// marker maps to blanks[0] (e.g. 本（①）ノート（②）… where one chosen particle
// fills both gaps).
export function segmentPrompt(q: ExamQuestion): PromptSegment[] {
  const out: PromptSegment[] = [];
  let last = 0;
  let markerIdx = 0;
  let m: RegExpExecArray | null;
  BLANK_RE.lastIndex = 0;
  while ((m = BLANK_RE.exec(q.prompt)) !== null) {
    if (m.index > last) out.push({ kind: 'text', text: q.prompt.slice(last, m.index) });
    const blankIndex = q.kind === 'multi' ? Math.min(markerIdx, q.blanks.length - 1) : 0;
    out.push({ kind: 'blank', text: m[1], blankIndex });
    markerIdx++;
    last = m.index + m[0].length;
  }
  if (last < q.prompt.length) out.push({ kind: 'text', text: q.prompt.slice(last) });
  return out;
}

// ---- Shuffling ------------------------------------------------------------
export function shuffle<T>(arr: readonly T[]): T[] {
  const out = arr.slice();
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}
