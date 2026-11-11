# VygOJ frontend client (vanilla HTML/CSS/JavaScript)

Static files served by the Flask frontend at the site root (`static_url_path=''`), so
`static/js/site.js` is requested as `/js/site.js`. There is no bundler, transpiler, or framework:
browsers load these files as they are. The parent `frontend/CLAUDE.md` also applies here.

## Layout

- `js/vyg.js`: client copy of the shared model (see "Shared model" in the root `CLAUDE.md`).
- `js/site.js`: behavior common to all pages (loaded from `base.html`).
- `js/<page>/<page>.js`: one module per page (`problem/`, `course/`, `user/`).
- `css/site.css`: global layout and variables; `css/<page>.css` for page-specific styles.
  Tables of data take the `data_table` class of `site.css` (headers of columns with the color
  of the site, headers of rows marked with `<th scope="row">`, rows of alternate background),
  which problem statements share for the tables of their authors.
- `img/`, `icon/`: images and SVG icons. `json/`: static data.
- `initial/`: default code of each language (`solution.c`, `Solution.java`...). The server reads
  it (`ProblemLoader.default_code()`) and sends it in the `initialCodeFor` of problems without
  initial code for an enabled language.
- The code editor and diff view use Monaco through the `<monaco-editor>` element in
  `js/components/monaco-editor.js`, which imports Monaco from the esm.sh CDN. Monaco does not
  know Alecci: `js/components/alecci-language.js` registers its highlighting (a Monarch port of
  the grammar of its VS Code extension).
- Formulas in problem statements (Asciidoctor `stem`) are typeset by MathJax from the jsDelivr
  CDN, configured in `js/problem/mathjax-config.js`.
- The `<editor-toolbar for="code_editor">` element in `js/components/editor-toolbar.js` adds the
  editor buttons (cut, copy, paste, undo, redo, clear, revert, fullscreen). `problem.html` places
  the layout menu and the language list inside it. Icons come from the Material Symbols font.

## Commands

Run from `frontend/`. `make lint-static` installs the tools if needed (`make dev`, which runs
`npm i`) and runs ESLint and Stylelint; it fails if either reports a problem. `make lint` also runs
Pylint on the Python code first. To run them separately:

```sh
npx eslint static/js                        # lint JavaScript (AirBnB config in .eslintrc.cjs)
npx eslint --fix static/js                  # auto-fix what is safe to fix
npx stylelint 'static/css/**/*.css'         # lint CSS (standard config in .stylelintrc.json)
npx stylelint --fix 'static/css/**/*.css'
```

`npm run lint` runs the first command and `npm run stylelint` the third. Always pass the folder:
with ESLint 8, `npx eslint` alone lints no files and exits cleanly. To see changes, run the frontend
(`make` in `frontend/`) and reload the page with the cache disabled; check the browser console for
errors and the layout at phone and desktop widths.

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
- Show and hide elements with their `hidden` property (`element.hidden = true`), and keep other
  states in attributes (`aria-current`, `data-status`...) that CSS selects; do not write inline
  styles or toggle classes.

### Security

- Never insert untrusted strings with `innerHTML`, `outerHTML`, `insertAdjacentHTML`, or
  `document.write`. Use `textContent`, `createElement`, and attribute setters. Program output,
  test case data, and anything from the server or `localStorage` count as untrusted.
- Never use `eval`, `new Function`, or string arguments to `setTimeout`/`setInterval`.
- Do not store secrets or personal data in `localStorage`; it only holds UI preferences and drafts.
- Send state-changing requests with POST and the CSRF token that the page provides (the
  `X-CSRFToken` header, as `ProblemManager.createMessage()` does).
- Pages are served with a CSP without `'unsafe-inline'` for scripts: no inline `<script>` blocks
  or event handler attributes; put the code in a module under `js/`.
- Handle failed or slow `fetch` calls (network errors, non-2xx status, malformed JSON) and keep the
  UI usable; re-enable buttons that were disabled while waiting.
- External scripts and styles may only come from hosts allowed by the CSP in
  `frontend/src/main.py`; pin the major version (e.g. `mathjax@4`), so compatible updates
  arrive automatically and breaking ones do not.

### HTML

- Markup generated from JavaScript must be semantic too: real `button` elements for actions,
  `label`s for inputs, lists for lists, headings in order, accessible names for icon controls.

### CSS

- Responsive by default: mobile-first rules, `@media (width >= ...)` breakpoints to enhance
  for larger screens (match existing breakpoints such as `640px` when adjusting old rules),
  flexbox/grid that wraps, relative units (`rem`, `%`, `fr`, `ch`), and no fixed widths that
  overflow a phone screen. Images use `max-width: 100%`.
- Reuse the custom properties declared in `:root` of `site.css` (`--success`, `--error`...)
  instead of hard-coding colors; add new ones there.
- Semantic HTML with native CSS nesting, without a naming methodology such as BEM:
  - Each component has one class in snake_case (`flash_messages`, `layout_menu`) or is a custom
    element (`editor-toolbar`). Its rules are nested in one block of its CSS file, with a comment
    that says what the component is.
  - Its parts are selected by element and structure in nested rules (`& > header`, `& li`). Use
    `>` where the structure matters, and keep nesting shallow.
  - Name the role of the parts with a short class (or an `id` if unique), also when no CSS or JS
    uses it yet: every part that repeats among its siblings (`td class="deadline"`, `fieldset
    class="password"`) and every part whose role the element does not tell (`details
    class="solution"`). Every `div` and `span` has a class or an `id`. Before a class, look for a
    more specific semantic element: `dl` for pairs of names and values
    (`<dt>Code</dt><dd>test101</dd>`, laid out with a grid of two columns), `ul` for lists (also of
    cards), `figure`/`figcaption`, `output`, `time`, `address`. CSS and JS prefer these names over
    positions (`.progress`, not `td:last-child`). Select a part class only inside its component
    (`.course .contents`), never alone, and do not use names that Asciidoctor or Markdown generate
    (`title`, `content`, `paragraph`...): statements keep their classes, so they would get those
    styles.
  - States are standard or `data-*`/`aria-*` attributes, not classes: `hidden`, `disabled`,
    `open`, `aria-expanded`, `aria-current="true"`, `data-status="passed"`,
    `data-category="error"`.
  - The shared variants of buttons are the only extra classes: `button` (a link that looks like a
    button), `small`, and the colors `confirm`, `reject`, `danger`, and `action` (`form.css`).
  - Kebab-case only for classes of external libraries (`material-symbols-outlined`).
  - Avoid styling by `id` and avoid `!important`.
- Stylelint (`no-descending-specificity`) asks for the less specific selectors first. When it
  complains about selectors that never match the same element, reorder the components instead of
  splitting them; a rule that must win over another should do it by specificity, not by order.
- Each animation (`@keyframes`, `transition`) goes in the CSS of the component it animates;
  only animations shared by several pages go in `site.css`. The `prefers-reduced-motion` rule of
  `site.css` stops all of them for users who ask their OS to reduce motion (it is the only place
  that needs `!important`), so do not repeat it per animation.
- Keep sufficient color contrast and visible focus styles for keyboard users.
