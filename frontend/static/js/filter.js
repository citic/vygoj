// Searches that filter the rows of a list in the page while the user types, without asking the
// server: a list_search form without action (macros.html), such as the contents of a course and the
// lists of courses of the home page, whose pages have every row. Searches of tables of data split
// in pages are made in the server instead (ListSearch of site.js)

// The text in lowercase and without accents, e.g. 'Introducción' is 'introduccion'
export function fold(text) {
  return text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase();
}

// The folded words of the search field of the form, none if there is no search
export function searchWords(form) {
  const { value } = form.querySelector('input[type="search"]');
  return fold(value).split(/\s+/).filter(Boolean);
}

// Applies the search of the form with filter() while the user types, which also shows or hides the
// X that clears it. Enter sends nothing, and the X clears the search. The form is hidden until this
// script works, since the server does not filter these rows
export function setupPageFilter(form, filter) {
  const input = form.querySelector('input[type="search"]');
  form.addEventListener('input', () => filter());
  form.addEventListener('submit', (event) => event.preventDefault());
  form.querySelector('.clear').addEventListener('click', (event) => {
    event.preventDefault();
    input.value = '';
    input.focus();
    filter();
  });
  form.hidden = false;
}
