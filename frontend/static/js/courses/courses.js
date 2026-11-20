import { fold, searchWords, setupPageFilter } from '../filter.js';

// Lists of courses of the home page. Actions that cannot be undone from the page, such as offering
// a prepared course to every user, ask for confirmation first with the text of the data-confirm
// attribute of their form
document.querySelectorAll('.courses form[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    // eslint-disable-next-line no-alert -- a native dialog is enough for a rare action
    if (!window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
});

// Shows only the courses of the list of the search form whose code, title, description, or authors
// contain every word of its search, ignoring case and accents, or says that none does. The page has
// every course of the lists, so it filters them without asking the server
function filterCourses(form) {
  const words = searchWords(form);
  const list = form.closest('details');
  let found = false;
  list.querySelectorAll('.course_list > li').forEach((item) => {
    const parts = item.querySelectorAll('.course_item > :is(h3, .description, .instructors)');
    const text = fold([...parts].map((part) => part.textContent).join(' '));
    item.hidden = !words.every((word) => text.includes(word));
    found ||= !item.hidden;
  });
  list.querySelector(':scope > .empty').hidden = found;
  form.querySelector('.clear').hidden = words.length === 0;
}

// Each list has its own search. The browser may restore the text of a field when the user goes
// back to the page, so the lists start filtered by it
document.querySelectorAll('.courses .list_search').forEach((form) => {
  setupPageFilter(form, () => filterCourses(form));
  filterCourses(form);
});

// Each section of the home page stays folded or unfolded as the user leaves it, by its id, because
// its title changes with the language of the interface. Sections start unfolded, also when
// localStorage has an invalid value
document.querySelectorAll('.courses > details[id]').forEach((details) => {
  const key = `home:${details.id}`;
  details.open = window.localStorage.getItem(key) !== 'false';
  details.addEventListener('toggle', () => window.localStorage.setItem(key, details.open));
});
