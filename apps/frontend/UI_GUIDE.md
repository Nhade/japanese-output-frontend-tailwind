# Shiori Frontend — UI Guide

This is the working manual for future agents touching the Shiori frontend.
The design direction is **Editorial Intelligence** — the full philosophy
lives in [`shiori-design-system.md`](../../shiori-design-system.md) at the
repo root. **Read that first.** This document is the how-it-actually-lives-
in-code companion.

---

## 1. File layout

```
apps/frontend/src/
├── App.vue                 # Shell: header + <main> + footer
├── main.ts
├── style.css               # Tailwind + editorial.css + auth.css imports
├── styles/
│   ├── editorial.css       # Shared primitives (see §3)
│   └── auth.css            # Shared auth form primitives
├── router/index.ts         # Route meta.hideChrome controls chrome visibility
├── components/
│   ├── TheHeader.vue       # Fixed editorial top-nav
│   ├── TheFooter.vue       # Static colophon (height locked to --footer-h)
│   ├── AuthLayout.vue      # Two-column editorial split for auth views
│   ├── SettingsModal.vue   # Custom glass-overlay dialog (not Modal.vue)
│   ├── Modal.vue           # Legacy modal — only ExerciseView uses it now
│   └── exercise/           # Exercise-specific primitives (HankoSeal, MarginNote…)
└── views/
    ├── NewsListView.vue        # Editorial front page ("Today's Edition")
    ├── NewsReaderView.vue      # Article spread w/ margin actions
    ├── VideoListView.vue       # Listening Index (import row + schedule)
    ├── VideoStudyView.vue      # Libretto layout (transcript + player + deck)
    ├── ChatView.vue            # Tutor's Desk workspace
    ├── MistakesView.vue        # Practice notebook (errata spread)
    ├── ExerciseView.vue        # Pre-existing two-page spread
    ├── StatisticsView.vue      # Not yet redesigned
    ├── LoginView.vue           # Uses AuthLayout
    └── RegisterView.vue        # Uses AuthLayout
```

---

## 2. Design tokens

All warm EI tokens are declared in `style.css:root`. Reference them via
CSS vars — **do not reintroduce Tailwind colour utilities** (no
`bg-zinc-*`, `text-emerald-*`, etc.) on redesigned surfaces.

| Token | Use for |
| :--- | :--- |
| `--background` | Default page paper (Shironeri) |
| `--surface-container-lowest` → `--surface-dim` | Warm tonal layering |
| `--primary` (Ai Indigo) | CTAs, active nav, primary rules |
| `--secondary` (Kohaku Amber) | Eyebrows, active underlines, progress, rule-on-focus |
| `--destructive` (Beni Red) | Hanko seal, wrong/error state only |
| `--foreground` + `color-mix(in oklab, …)` | Tonal greys (never flat `#888`) |
| `--font-serif` | Shippori Mincho — all headlines, Japanese display, prose |
| `--font-sans` | Inter — eyebrows, buttons, small-caps meta |

### Chrome heights

```
--topnav-h: 4rem;    /* TheHeader fixed height */
--footer-h: 3.5rem;  /* TheFooter locked height */
--app-chrome-h: calc(var(--topnav-h) + var(--footer-h));
```

Every full-page view shell sets
`min-height: calc(100vh - var(--app-chrome-h))` so single-screen layouts
fit without pushing the static footer past the fold.

---

## 3. Shared primitives — `styles/editorial.css`

Promote any pattern that appears in ≥3 views to this file. Current contents:

| Class | Purpose |
| :--- | :--- |
| `.ei-shell-bg` | Warm vertical gradient for the outer `<main>` of a view |
| `.eyebrow`, `.eyebrow-sm` | Small-caps tracked label; pair with `.eyebrow-kohaku` / `.eyebrow-indigo` for colour |
| `.filter-bar`, `.filter-group`, `.filter-label`, `.filter-clear` | Editorial filter row |
| `.chip-row`, `.chip`, `.chip.is-active` | Category chips with kohaku underline |
| `.section-title-row`, `.section-title`, `.section-count` | Serif section header + eyebrow count |
| `.reader-back` | Back link with arrow (news reader, video study) |
| `.empty-state` | Italic serif centred empty copy |

**Auth primitives** live in `styles/auth.css`: `.auth-heading`,
`.auth-sub`, `.auth-form`, `.auth-field*`, `.auth-cta`, `.auth-divider*`,
`.auth-toggle*`. Only LoginView / RegisterView need them.

### How to use them

1. Keep the **base class name** when rendering. All primitives here live in
   *global* CSS, not Vue `<style scoped>`.
2. For a view-specific variant, add a modifier class in the view's scoped
   style (e.g. `.chip-jp` for the Japanese chip variant in NewsListView).
3. If a rule would be useful in ≥3 views, promote it here instead of
   duplicating scoped copies.

---

## 4. Per-view naming conventions

Each redesigned view uses a **class-name prefix** so its scoped styles
stay self-contained:

| Prefix | Owner view |
| :--- | :--- |
| `.ch-*` | ChatView (Tutor's Desk) |
| `.vs-*` | VideoStudyView (Libretto dossier) |
| `.vid-*` | VideoListView (Listening Index) |
| `.paragraph*`, `.reader-*`, `.translation`, `.hanko-seal`, `.next-article` | NewsReaderView |
| `.lead-*`, `.article-*`, `.masthead*` | NewsListView |
| `.errata-*`, `.practice-*`, `.review-*`, `.correction-*`, `.pstat*` | MistakesView |
| `.settings-*` | SettingsModal |
| `.auth-cover-*`, `.brand-*`, `.auth-form-col`, `.auth-eyebrow*` | AuthLayout |

When adding a new view, pick a 2–3 letter prefix (e.g. `.st-*` for
Statistics) and keep all its chrome scoped to it.

---

## 5. Shell layout pattern

Every data view follows the same outer skeleton:

```vue
<template>
  <main class="{view}-shell ei-shell-bg text-foreground">
    <div class="{inner-wrapper}">
      <!-- view content -->
    </div>
  </main>
</template>

<style scoped>
.{view}-shell {
  min-height: calc(100vh - var(--app-chrome-h));
  /* paper gradient comes from the global .ei-shell-bg utility */
}
</style>
```

For fixed-height workspaces (Chat) use
`height: calc(100dvh - var(--app-chrome-h))` on the inner page so the
composer + header pin without producing scroll.

---

## 6. Chrome visibility

Global header + footer render everywhere **except** routes tagged with
`meta.hideChrome: true` in `router/index.ts`. Currently:

- `/login` and `/register` hide chrome so `AuthLayout` can go full-bleed.

To add another bare route, set `meta.hideChrome: true` on its route entry;
`App.vue` reads `route.meta.hideChrome` to decide.

---

## 7. i18n

- Strings live in `src/locales/{en,ja,zh-tw}.json`, organized by view
  namespace (`news.*`, `video.*`, `chat.*`, `mistakes.*`, `auth.*`).
- **Always add new chrome in all three locales.** Missing keys fall back
  to English silently — easy to miss in review.
- UI chrome in English; **Japanese strings are reserved for content**
  (actual Japanese the learner reads). Japanese accents (e.g. 栞, 了) are
  fine as display glyphs, but don't mix them with English UI labels.
- Use `Intl.DateTimeFormat` with a locale-aware helper for dates —
  never hardcode date strings. Example pattern lives in NewsListView.

---

## 8. Don't mock what the backend doesn't return

When a design mock includes metadata the backend doesn't expose (JLPT on
the news list, per-video saved-words count, per-article pull-quote),
**drop the element or derive from available data**. Never hardcode a
placeholder that looks real.

Precedents:
- News list: dropped JLPT tag + read minutes on cards (backend doesn't
  return paragraphs for the list view).
- Videos: dropped saved-words stat and per-video JLPT.
- Mistakes: dropped relative date and JLPT filter.
- Auth: dropped "Forgot passphrase?" and "Keep me signed in" (no backend).

---

## 9. When in doubt

- Reread `shiori-design-system.md` §1–§6 before making colour / shape /
  type decisions.
- Check existing views for the closest precedent — chances are a prefix
  or primitive already exists.
- If a mock feels off-system (e.g. decorative editorial chrome like
  "Vol. 04 / 2026" or orphan kanji that don't earn their weight), flag it
  to the user before implementing rather than after.
- The paper metaphor is **load-bearing**. Rounded corners > 12px, pure
  greys, glass on persistent surfaces, and emerald/neon accents all break
  it — and you will be asked to revert them.
