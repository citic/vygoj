// Shows the progress of each problem as a percentage and a bar. The grade stored in the database
// for the logged user wins; otherwise the one that the problem page saved in localStorage is used.
// Sections and the whole course show the average of the problems they contain
class CourseManager {
  static main() {
    const course = { element: document.getElementById('course_progress'), level: 1, scores: [] };
    const groups = [course];
    // Sections that contain the current row, from the course to the innermost one
    const open = [course];
    document.querySelectorAll('.course__contents tbody tr').forEach((row) => {
      const level = Number(row.dataset.level);
      while (open.at(-1).level >= level) {
        open.pop();
      }
      // Indentation of the row, the same for level 6 and deeper as their titles stay <h6>
      row.style.setProperty('--depth', Math.min(level, 6) - 2);
      const element = row.querySelector('.course__progress');
      if (row.classList.contains('course__section')) {
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
    document.querySelector('.course__contents').addEventListener('click', CourseManager.toggle);
    document.getElementById('toggle_all').addEventListener('click', CourseManager.toggleAll);
  }

  // Clicking a section title hides or shows every row inside that section
  static toggle({ target }) {
    const button = target.closest('.course__section button');
    if (button) {
      CourseManager.expand(button, button.getAttribute('aria-expanded') === 'false');
      CourseManager.save();
    }
  }

  // Clicking the Contents title collapses every section when one at least is expanded,
  // otherwise expands them all
  static toggleAll() {
    const buttons = document.querySelectorAll('.course__section[data-level="2"] button');
    const expanded = ![...buttons].some((button) => button.getAttribute('aria-expanded') === 'true');
    buttons.forEach((button) => CourseManager.expand(button, expanded));
    CourseManager.save();
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

  // The titles of the collapsed sections are kept in localStorage, one per line, by course
  static save() {
    const collapsed = document.querySelectorAll('.course__section [aria-expanded="false"]');
    const titles = [...collapsed].map((button) => button.textContent);
    window.localStorage.setItem(CourseManager.key(), titles.join('\n'));
    // The Contents title shows its arrow expanded while any section is expanded
    const expanded = document.querySelector('.course__section [aria-expanded="true"]') !== null;
    document.getElementById('toggle_all').setAttribute('aria-expanded', expanded);
  }

  static restore() {
    const titles = (window.localStorage.getItem(CourseManager.key()) ?? '').split('\n');
    const buttons = [...document.querySelectorAll('.course__section button')];
    buttons.filter((button) => titles.includes(button.textContent))
      .forEach((button) => CourseManager.expand(button, false));
    CourseManager.save();
  }

  static key() {
    return `${document.querySelector('.course__contents').dataset.course}/collapsed`;
  }

  static show(element, score) {
    element.textContent = `${score}%`;
    element.style.setProperty('--progress', `${score}%`);
  }
}

window.addEventListener('load', CourseManager.main);
