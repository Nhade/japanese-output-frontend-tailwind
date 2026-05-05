// Static practice tool — loads CSV datasets shipped under /data/lessons.
// Stays entirely client-side; not wired to /api/exercises or the mistakes log.

export type LessonId = 'L34' | 'L35' | 'L36' | 'L37' | 'L38';

export const LESSON_IDS: readonly LessonId[] = ['L34', 'L35', 'L36', 'L37', 'L38'];

// Per the PM brief: skip vocab quiz on L34 / L38.
export const VOCAB_DISABLED_LESSONS = new Set<LessonId>(['L34', 'L38']);

// Section prefixes excluded from vocab quizzes — `読み物語彙` (reading-passage
// glossary) and `会話語彙` (dialogue glossary) are reference lists rather than
// active vocabulary the learner is expected to drill.
const VOCAB_SECTION_EXCLUDE_PREFIXES = ['読み物', '会話'];

export function isVocabSectionDrilled(section: string): boolean {
  return !VOCAB_SECTION_EXCLUDE_PREFIXES.some(p => section.startsWith(p));
}

export interface FillBlankItem {
  lesson: LessonId;
  source_section: string;
  source_subsection: string;
  item_no: string;
  source_page: string;
  grammar_point_id: string;
  target_form: string;
  cue: string;
  cue_form: string;
  prompt: string;
  answer: string;
  full_answer_sentence: string;
  notes: string;
  source_locator: string;
}

export interface VocabItem {
  lesson: LessonId;
  source_section: string;
  item_no: string;
  japanese: string;
  kana: string;
  word_type: string;
  chinese_meaning: string;
  usage_note: string;
  source_locator: string;
}

export interface GrammarPoint {
  lesson: LessonId;
  grammar_point_id: string;
  grammar_point: string;
  target_form: string;
  rule_summary: string;
  usage_note: string;
  source_locator: string;
}

// ---- Tiny RFC-4180-ish CSV parser (handles quoted fields with embedded commas / newlines) ----
function parseCSV(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = '';
  let inQuotes = false;
  // Strip BOM if present.
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else { inQuotes = false; }
      } else {
        field += ch;
      }
    } else {
      if (ch === '"') {
        inQuotes = true;
      } else if (ch === ',') {
        row.push(field); field = '';
      } else if (ch === '\n' || ch === '\r') {
        // Handle CRLF: skip the \n that follows \r.
        if (ch === '\r' && text[i + 1] === '\n') i++;
        row.push(field); field = '';
        // Skip empty trailing line at EOF.
        if (row.length > 1 || row[0] !== '') rows.push(row);
        row = [];
      } else {
        field += ch;
      }
    }
  }
  // Flush last field/row if no trailing newline.
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    if (row.length > 1 || row[0] !== '') rows.push(row);
  }
  return rows;
}

function rowsToObjects<T extends Record<string, string>>(rows: string[][]): T[] {
  if (rows.length < 2) return [];
  const [header, ...body] = rows;
  return body.map(r => {
    const obj: Record<string, string> = {};
    header.forEach((key, i) => {
      obj[key] = (r[i] ?? '').trim();
    });
    return obj as T;
  });
}

const cache = new Map<string, Promise<unknown>>();

async function fetchCSV<T extends Record<string, string>>(url: string): Promise<T[]> {
  const hit = cache.get(url);
  if (hit) return hit as Promise<T[]>;
  const p = (async () => {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Failed to load ${url}: ${res.status}`);
    const text = await res.text();
    return rowsToObjects<T>(parseCSV(text));
  })();
  cache.set(url, p);
  return p;
}

export async function loadFillBlanks(lesson: LessonId): Promise<FillBlankItem[]> {
  return fetchCSV<FillBlankItem>(
    `${import.meta.env.BASE_URL}data/lessons/${lesson}_dataset_csv/${lesson}_fill_blanks.csv`,
  );
}

export async function loadVocab(lesson: LessonId): Promise<VocabItem[]> {
  return fetchCSV<VocabItem>(
    `${import.meta.env.BASE_URL}data/lessons/${lesson}_dataset_csv/${lesson}_vocab.csv`,
  );
}

export async function loadGrammarPoints(lesson: LessonId): Promise<GrammarPoint[]> {
  return fetchCSV<GrammarPoint>(
    `${import.meta.env.BASE_URL}data/lessons/${lesson}_dataset_csv/${lesson}_grammar_points.csv`,
  );
}

// ---- Answer helpers --------------------------------------------------------

// The fill-blank dataset stores some answers as alternates separated by `｜`
// (e.g. `短ければ｜短い` for ……ば……ほど patterns). Treat any one as correct.
export function fillBlankAnswerVariants(answer: string): string[] {
  return answer.split('｜').map(s => s.trim()).filter(Boolean);
}

// Convert katakana (U+30A1–U+30F6, plus ヴ at U+30F4) to its hiragana
// counterpart by shifting the codepoint down 0x60. Long-vowel mark ー and
// non-kana characters are left untouched so kanji answers still compare.
function katakanaToHiragana(s: string): string {
  return s.replace(/[ァ-ヶ]/g, ch => String.fromCharCode(ch.charCodeAt(0) - 0x60));
}

// Loose match: ignore whitespace differences and treat hiragana ↔ katakana as
// equivalent so the user can answer スポーツ as すぽーつ. Other characters
// (kanji, punctuation) are left intact — this is a study tool, not a
// typo-tolerant grading system.
export function normalizeAnswer(s: string): string {
  return katakanaToHiragana(s.replace(/\s+/g, '').trim());
}

// Multi-answer prompts (e.g. ～ば～ほど or two-blank 「のが／のは」 sentences)
// store their expected pieces joined by `｜` in the CSV. The user is asked to
// produce all of them, separated by whitespace, half/full-width comma, slash,
// or pipe.
const ANSWER_SEPARATOR_RE = /[\s,，、､｜|／/]+/;

export function splitUserAnswers(userInput: string): string[] {
  return userInput.split(ANSWER_SEPARATOR_RE).map(s => s.trim()).filter(Boolean);
}

// Walk both strings from the right, matching identical characters. The shared
// trailing run is the okurigana / inflection that survives substitution; the
// preceding chunks are the kanji root vs. its kana reading.
function splitKanjiKanaRoots(kanji: string, kana: string): { kanjiRoot: string; kanaRoot: string } | null {
  if (!kanji || !kana || kanji === kana) return null;
  let i = 0;
  while (i < kanji.length && i < kana.length && kanji[kanji.length - 1 - i] === kana[kana.length - 1 - i]) {
    i++;
  }
  const kanjiRoot = kanji.slice(0, kanji.length - i);
  const kanaRoot = kana.slice(0, kana.length - i);
  if (!kanjiRoot || kanjiRoot === kanaRoot) return null;
  return { kanjiRoot, kanaRoot };
}

// Build an alternate, fully-kana reading of `answer` by swapping the kanji
// portion of the cue's vocab entry for its kana reading. Returns null when no
// substitution is possible (no matching vocab entry, no kanji in the cue, or
// the answer doesn't begin with the cue's kanji root).
//
// The cue lookup tries the exact cue first, then a few stripped variants —
// the fill-blank dataset stores cues like `短いです` (i-adjective + copula)
// while the vocab table only carries `短い`. Stripping the trailing copula /
// auxiliary makes those lookups succeed.
const CUE_TRIM_SUFFIXES = ['です', 'ます', 'だ'];

function findVocabForCue(cue: string, pool: readonly VocabItem[]): VocabItem | null {
  const direct = pool.find(x => x.japanese === cue);
  if (direct) return direct;
  for (const sfx of CUE_TRIM_SUFFIXES) {
    if (cue.endsWith(sfx)) {
      const trimmed = cue.slice(0, -sfx.length);
      if (trimmed) {
        const hit = pool.find(x => x.japanese === trimmed);
        if (hit) return hit;
      }
    }
  }
  return null;
}

export function kanaifyAnswer(answer: string, cue: string, pool: readonly VocabItem[]): string | null {
  const v = findVocabForCue(cue, pool);
  if (!v) return null;
  const split = splitKanjiKanaRoots(v.japanese, v.kana);
  if (!split) return null;
  if (!answer.startsWith(split.kanjiRoot)) return null;
  return split.kanaRoot + answer.slice(split.kanjiRoot.length);
}

function tokenMatches(token: string, variant: string, cue: string, pool: readonly VocabItem[]): boolean {
  const u = normalizeAnswer(token);
  if (!u) return false;
  if (u === normalizeAnswer(variant)) return true;
  const kana = kanaifyAnswer(variant, cue, pool);
  if (kana && u === normalizeAnswer(kana)) return true;
  return false;
}

export function isFillBlankCorrect(
  userInput: string,
  item: FillBlankItem,
  vocabPool: readonly VocabItem[] = [],
): boolean {
  const variants = fillBlankAnswerVariants(item.answer);
  if (variants.length === 0) return false;

  if (variants.length === 1) {
    return tokenMatches(userInput, variants[0], item.cue, vocabPool);
  }

  // Multi-answer: every CSV variant must appear, in the order the prompt lists
  // its blanks. Order matches the dataset's `｜`-joined order.
  const tokens = splitUserAnswers(userInput);
  if (tokens.length !== variants.length) return false;
  return variants.every((v, i) => tokenMatches(tokens[i], v, item.cue, vocabPool));
}

// ---- Shuffling -------------------------------------------------------------

export function shuffle<T>(arr: readonly T[]): T[] {
  const out = arr.slice();
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

// ---- Vocab MCQ generation --------------------------------------------------

export interface VocabChoiceQuestion {
  item: VocabItem;
  choices: string[];
  // Index of the correct choice in `choices`.
  correctIndex: number;
}

// Build a meaning-recognition MCQ: given a Japanese word, pick the Chinese
// meaning. Distractors are sampled from the rest of the lesson's vocab.
export function buildMeaningMCQ(
  item: VocabItem,
  pool: readonly VocabItem[],
  size = 4,
): VocabChoiceQuestion {
  const wrong = pool
    .filter(v => v !== item && v.chinese_meaning && v.chinese_meaning !== item.chinese_meaning);
  const distractors = shuffle(wrong)
    .slice(0, Math.max(0, size - 1))
    .map(v => v.chinese_meaning);
  // Dedup against the correct meaning just in case.
  const uniqDistractors = Array.from(new Set(distractors)).filter(c => c !== item.chinese_meaning);
  const choices = shuffle([item.chinese_meaning, ...uniqDistractors]);
  return {
    item,
    choices,
    correctIndex: choices.indexOf(item.chinese_meaning),
  };
}
