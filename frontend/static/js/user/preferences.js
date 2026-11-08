// Preview the color scheme and the font as soon as the user chooses them (in preferences); Save
// stores them
const root = document.documentElement;
document.querySelectorAll('.preferences').forEach((fieldset) => {
  fieldset.addEventListener('change', ({ target }) => {
    if (target.name === 'font') {
      root.dataset.font = target.value;
    } else if (target.value === 'default') {
      delete root.dataset.colorScheme;
    } else {
      root.dataset.colorScheme = target.value;
    }
  });
});
