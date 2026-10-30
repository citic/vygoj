# VygOJ frontend client (vanilla HTML/CSS/JavaScript)

Static files served by the Flask frontend at the site root (`static_url_path=''`), so
`static/js/site.js` is requested as `/js/site.js`. There is no bundler, transpiler, or framework:
browsers load these files as they are. The parent `frontend/CLAUDE.md` also applies here.

## Layout

- `js/vyg.js`: client copy of the shared model (see "Shared model" in the root `CLAUDE.md`).
- `js/site.js`: behavior common to all pages (loaded from `base.html`).
- `js/<page>/<page>.js`: one module per page (`problem/`, `course/`, `user/`).
- `css/site.css`: global layout and variables; `css/<page>.css` for page-specific styles.
- `img/`, `icon/`: images and SVG icons. `json/`: static data.
- The code editor and diff view use Monaco through the `<monaco-editor>` element in
  `js/components/monaco-editor.js`, which imports Monaco from the esm.sh CDN.
- Formulas in problem statements (Asciidoctor `stem`) are typeset by MathJax from the jsDelivr
  CDN, configured in `js/problem/mathjax-config.js`.
- The `<editor-toolbar for="code_editor">` element in `js/components/editor-toolbar.js` adds the
  editor buttons (cut, copy, paste, undo, redo, clear, revert, fullscreen). `problem.html` places
  the layout menu and the language list inside it. Icons come from the Material Symbols font.

## Commands

Run from `frontend/` after `make dev` (which runs `npm i`):

```sh
npx eslint static/js          # lint JavaScript (AirBnB config in .eslintrc.cjs)
npx eslint --fix static/js    # auto-fix what is safe to fix
npx stylelint 'static/css/**/*.css'
```

Note: `npm run lint` currently points to `src/`, which has no JavaScript; lint `static/js`
directly. To see changes, run the frontend (`make` in `frontend/`) and reload the page with the
cache disabled; check the browser console for errors and the layout at phone and desktop widths.

## Rules

### JavaScript

- Follow the ECMAScript Living Standard and ESLint with the AirBnB style guide
  (`.eslintrc.cjs`). New code must lint cleanly.
- Use `const` by default, `let` only when the binding is reassigned, never `var`.
- ES modules only: `import`/`export` with explicit `.js` extensions; no globals except the ones
  provided by external libraries (e.g. `monaco`).
- Prefer classes for page controllers (e.g. `ProblemManager`), arrow functions for callbacks,
  template literals, destructuring, `async`/`await` with `fetch`, and `===`.
- Comment each class field with its purpose and type (`// HTMLButtonElement`), as existing code
  does. 2-space indentation, single quotes, semicolons, trailing commas (AirBnB).
- Attach behavior with `addEventListener` from the module, not inline attributes.
- Show and hide elements by toggling CSS classes (e.g. `hidden`), not by writing inline styles.

### Security

- Never insert untrusted strings with `innerHTML`, `outerHTML`, `insertAdjacentHTML`, or
  `document.write`. Use `textContent`, `createElement`, and attribute setters. Program output,
  test case data, and anything from the server or `localStorage` count as untrusted.
- Never use `eval`, `new Function`, or string arguments to `setTimeout`/`setInterval`.
- Do not store secrets or personal data in `localStorage`; it only holds UI preferences and drafts.
- Send state-changing requests with POST and the CSRF token that the page provides.
- Handle failed or slow `fetch` calls (network errors, non-2xx status, malformed JSON) and keep the
  UI usable; re-enable buttons that were disabled while waiting.
- External scripts and styles may only come from hosts allowed by the CSP in
  `frontend/src/main.py`; pin the major version (e.g. `mathjax@4`), so compatible updates
  arrive automatically and breaking ones do not.

### HTML

- Markup generated from JavaScript must be semantic too: real `button` elements for actions,
  `label`s for inputs, lists for lists, headings in order, accessible names for icon controls.

### CSS

- Responsive by default: mobile-first rules, `@media (min-width: ...)` breakpoints to enhance
  for larger screens (match existing breakpoints such as `640px` when adjusting old rules),
  flexbox/grid that wraps, relative units (`rem`, `%`, `fr`, `ch`), and no fixed widths that
  overflow a phone screen. Images use `max-width: 100%`.
- Reuse the custom properties declared in `:root` of `site.css` (`--success`, `--error`...)
  instead of hard-coding colors; add new ones there.
- Class names follow the BEM-like underscore convention: `block`, `block__element`,
  `block--modifier`. Avoid styling by `id` and avoid `!important`.
- Keep sufficient color contrast and visible focus styles for keyboard users.
