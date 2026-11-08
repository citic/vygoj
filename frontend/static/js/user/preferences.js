// Preview the color scheme and the font as soon as the user chooses them (in preferences); Save
// stores them
const root = document.documentElement;
document.querySelector('.user_preferences form')?.addEventListener('change', ({ target }) => {
  if (target.name === 'font') {
    root.dataset.font = target.value;
  } else if (target.name === 'color_scheme' && target.value === 'default') {
    delete root.dataset.colorScheme;
  } else if (target.name === 'color_scheme') {
    root.dataset.colorScheme = target.value;
  }
});
