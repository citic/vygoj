// Translations of the texts written by JavaScript, in the language of the page (<html lang>). The
// server sends them from the catalogs of the templates (translations/ of the frontend), so make
// update-translations collects the texts marked with _() here too

// Milliseconds to wait for the translations, the texts are shown in English after it
const TRANSLATIONS_TIMEOUT = 10000;

// URL of the translations of the language of the page, e.g. /translations/es.json
const url = `/translations/${encodeURIComponent(document.documentElement.lang)}.json`;
// Object with the English texts as keys and their translations as values. It is empty for English
// and when the request fails, so the texts are shown in English
const messages = await fetch(url, { signal: AbortSignal.timeout(TRANSLATIONS_TIMEOUT) })
  .then((response) => (response.ok ? response.json() : {}))
  .catch(() => ({}));

// Return the translation of the text, with its %(name)s placeholders replaced by the given values,
// e.g. _('Test case %(number)s', { number: 2 })
export default function _(text, values = {}) {
  const translation = Object.hasOwn(messages, text) ? messages[text] : text;
  return translation.replace(/%\((\w+)\)s/g, (placeholder, name) => String(values[name] ?? placeholder));
}
