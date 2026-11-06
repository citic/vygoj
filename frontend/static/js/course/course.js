// Shows the progress that each problem page saved in localStorage, as a percentage and a bar.
// Sections and the whole course show the average of the problems they contain
class CourseManager {
  static main() {
    const course = { element: document.getElementById('course_progress'), level: 1, scores: [] };
    const groups = [course];
    // Sections that contain the current row, from the course to the innermost one
    const open = [course];
    for (const row of document.querySelectorAll('.course__contents tbody tr')) {
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
        // localStorage can be edited by anyone, so accept only integers from 0 to 100
        const saved = Math.round(Number(window.localStorage.getItem(element.dataset.problem)));
        const score = Math.min(Math.max(saved || 0, 0), 100);
        open.forEach((group) => group.scores.push(score));
        CourseManager.show(element, score);
      }
    }
    for (const { element, scores } of groups) {
      const sum = scores.reduce((total, score) => total + score, 0);
      CourseManager.show(element, scores.length ? Math.round(sum / scores.length) : 0);
    }
    document.querySelector('.course__contents').addEventListener('click', CourseManager.toggle);
  }

  // Clicking a section title hides or shows every row inside that section
  static toggle({ target }) {
    const button = target.closest('.course__section button');
    if (!button) {
      return;
    }
    const expanded = button.getAttribute('aria-expanded') === 'false';
    let row = button.closest('tr');
    const level = Number(row.dataset.level);
    button.setAttribute('aria-expanded', expanded);
    while ((row = row.nextElementSibling) && Number(row.dataset.level) > level) {
      row.hidden = !expanded;
      row.querySelector('button')?.setAttribute('aria-expanded', expanded);
    }
  }

  static show(element, score) {
    element.textContent = `${score}%`;
    element.style.setProperty('--progress', `${score}%`);
  }
}

window.addEventListener('load', CourseManager.main);
