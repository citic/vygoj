import { fold, searchWords, setupPageFilter } from '../filter.js';

// Shows the progress of each problem as a percentage and a bar. The grade stored in the database
// for the logged user wins; otherwise the one that the problem page saved in localStorage is used.
// Sections and the whole course show the average of the problems they contain
class CourseManager {
  static main() {
    const course = { element: document.getElementById('course_progress'), level: 1, scores: [] };
    const groups = [course];
    // Sections that contain the current row, from the course to the innermost one
    const open = [course];
    document.querySelectorAll('.course tbody tr').forEach((row) => {
      const level = Number(row.dataset.level);
      while (open.at(-1).level >= level) {
        open.pop();
      }
      // Indentation of the row, the same for level 6 and deeper as their titles stay <h6>
      row.style.setProperty('--depth', Math.min(level, 6) - 3);
      const element = row.querySelector('.progress');
      if (row.dataset.type === 'section') {
        const section = { element, level, scores: [] };
        groups.push(section);
        open.push(section);
      } else if (element.dataset.problem) {
        // Anonymous users have no grade in the database, so they keep their local progress.
        // localStorage can be edited by anyone, so accept only integers from 0 to 100
        const { grade, problem } = element.dataset;
        const stored = grade ?? window.localStorage.getItem(problem);
        const saved = Math.round(Number(stored));
        const score = Math.min(Math.max(saved || 0, 0), 100);
        open.forEach((group) => group.scores.push(score));
        CourseManager.show(element, score);
      }
    });
    groups.forEach(({ element, scores }) => {
      const sum = scores.reduce((total, score) => total + score, 0);
      CourseManager.show(element, scores.length ? Math.round(sum / scores.length) : 0);
    });
    CourseManager.restore();
    CourseManager.scrollToProblem();
    document.querySelector('.course .contents').addEventListener('click', CourseManager.toggle);
    document.getElementById('toggle_all').addEventListener('click', CourseManager.toggleAll);
    CourseManager.setupSearch();
  }

  // The filter of the contents applies while the user types (filter.js)
  static setupSearch() {
    setupPageFilter(document.querySelector('.course .list_search'), CourseManager.filter);
  }

  // The folded words of the search of the contents, none if there is no search
  static words() {
    return searchWords(document.querySelector('.course .list_search'));
  }

  // Shows only the rows whose number and title contain every word of the search, ignoring case and
  // accents, with the sections that contain them, and every row of a section whose title matches.
  // A search starts with every section expanded, and the sections that the user collapses during
  // it hide their rows of the search, without saving it. An empty search shows the contents again
  // with the sections that the user had collapsed
  static filter() {
    const words = CourseManager.words();
    const rows = document.querySelectorAll('.course tbody tr');
    const buttons = document.querySelectorAll('[data-type="section"] button');
    // The X is shown while there is a search, so a hidden X means that this search is new
    const clearLink = document.querySelector('.course .list_search .clear');
    if (clearLink.hidden || words.length === 0) {
      buttons.forEach((button) => button.setAttribute('aria-expanded', true));
    }
    clearLink.hidden = words.length === 0;
    document.getElementById('contents_empty').hidden = true;
    if (words.length === 0) {
      rows.forEach((row) => { row.hidden = false; });
      CourseManager.restore();
      return;
    }
    // Sections that contain the current row, as { row, level, matched, inside, closed }: inside if
    // a section around it is collapsed, and closed if it is collapsed or inside
    const open = [];
    let found = false;
    rows.forEach((row) => {
      const level = Number(row.dataset.level);
      while (open.at(-1)?.level >= level) {
        open.pop();
      }
      const title = fold(row.querySelector('.name').textContent);
      const matched = open.some((section) => section.matched)
        || words.every((word) => title.includes(word));
      const inside = open.at(-1)?.closed ?? false;
      row.hidden = !matched || inside;
      if (matched) {
        open.forEach((section) => { section.row.hidden = section.inside; });
        found = true;
      }
      if (row.dataset.type === 'section') {
        const collapsed = row.querySelector('button').getAttribute('aria-expanded') === 'false';
        open.push({
          row, level, matched, inside, closed: inside || collapsed,
        });
      }
    });
    document.getElementById('contents_empty').hidden = found;
    CourseManager.showToggleAll();
  }

  // Clicking a section title hides or shows every row inside that section
  static toggle({ target }) {
    const button = target.closest('[data-type="section"] button');
    if (!button) {
      return;
    }
    const expanded = button.getAttribute('aria-expanded') === 'false';
    if (CourseManager.words().length) {
      // During a search, the section shows or hides only its rows of the search
      button.setAttribute('aria-expanded', expanded);
      CourseManager.filter();
    } else {
      CourseManager.expand(button, expanded);
      CourseManager.save();
    }
  }

  // Clicking the Contents title collapses every section when one at least is expanded,
  // otherwise expands them all
  static toggleAll() {
    const buttons = document.querySelectorAll('[data-type="section"][data-level="3"] button');
    const expanded = ![...buttons].some((button) => button.getAttribute('aria-expanded') === 'true');
    if (CourseManager.words().length) {
      buttons.forEach((button) => button.setAttribute('aria-expanded', expanded));
      CourseManager.filter();
    } else {
      buttons.forEach((button) => CourseManager.expand(button, expanded));
      CourseManager.save();
    }
  }

  static expand(button, expanded) {
    const header = button.closest('tr');
    const level = Number(header.dataset.level);
    button.setAttribute('aria-expanded', expanded);
    for (let row = header.nextElementSibling; row && Number(row.dataset.level) > level;
      row = row.nextElementSibling) {
      row.hidden = !expanded;
      row.querySelector('button')?.setAttribute('aria-expanded', expanded);
    }
  }

  // Scrolls to the problem of the link that the user followed (#name, e.g. Return to the course
  // of a problem page), or else to the problem where the user ran new code last. The sections that
  // hide it are expanded. Names are compared as text, never used as selectors
  static scrollToProblem() {
    const { lastProblem } = document.querySelector('.course .contents').dataset;
    const name = window.location.hash.slice(1) || lastProblem;
    const cell = [...document.querySelectorAll('.course .progress[data-problem]')]
      .find((element) => element.dataset.problem === name);
    if (!cell) {
      return;
    }
    const row = cell.closest('tr');
    // Sections before the row with a lower level contain it. Expanding the outermost collapsed
    // one shows every row inside it
    let level = Number(row.dataset.level);
    let collapsed = null;
    for (let header = row.previousElementSibling; header && level > 3;
      header = header.previousElementSibling) {
      if (Number(header.dataset.level) < level) {
        level = Number(header.dataset.level);
        const button = header.querySelector('button');
        if (button.getAttribute('aria-expanded') === 'false') {
          collapsed = button;
        }
      }
    }
    if (collapsed) {
      CourseManager.expand(collapsed, true);
      CourseManager.save();
    }
    row.scrollIntoView({ block: 'center' });
  }

  // The titles of the collapsed sections are kept in localStorage, one per line, by course
  static save() {
    const collapsed = document.querySelectorAll('[data-type="section"] [aria-expanded="false"]');
    const titles = [...collapsed].map((button) => button.textContent);
    window.localStorage.setItem(CourseManager.key(), titles.join('\n'));
    CourseManager.showToggleAll();
  }

  // The Contents title shows its arrow expanded while any section is expanded
  static showToggleAll() {
    const expanded = document.querySelector('[data-type="section"] [aria-expanded="true"]') !== null;
    document.getElementById('toggle_all').setAttribute('aria-expanded', expanded);
  }

  static restore() {
    const titles = (window.localStorage.getItem(CourseManager.key()) ?? '').split('\n');
    const buttons = [...document.querySelectorAll('[data-type="section"] button')];
    buttons.filter((button) => titles.includes(button.textContent))
      .forEach((button) => CourseManager.expand(button, false));
    CourseManager.save();
  }

  static key() {
    return `${document.querySelector('.course .contents').dataset.course}/collapsed`;
  }

  static show(element, score) {
    element.textContent = `${score}%`;
    element.style.setProperty('--progress', `${score}%`);
  }
}

window.addEventListener('load', CourseManager.main);
