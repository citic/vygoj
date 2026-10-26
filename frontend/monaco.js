// Monaco editor with only the C and C++ languages. npm run build bundles it into static/dist/
// ESLint cannot follow the "exports" paths of monaco-editor/package.json, but esbuild does
/* eslint-disable import/no-unresolved */
import 'monaco-editor/features/register.all';
import 'monaco-editor/languages/definitions/cpp/register';

// Diffs and other slow tasks run in a worker, bundled as editor.worker.js
window.MonacoEnvironment = {
  getWorker: () => new Worker(new URL('editor.worker.js', import.meta.url), { type: 'module' }),
};
// Styles of the editor, bundled as monaco.css
document.head.insertAdjacentHTML('beforeend', `<link rel="stylesheet" href="${new URL('monaco.css', import.meta.url)}">`);

export * from 'monaco-editor/editor';
