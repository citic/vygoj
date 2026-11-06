// Preview the color scheme as soon as the user chooses it (in preferences); Save stores it
const root = document.documentElement;
document.querySelector('.preferences')?.addEventListener('change', ({ target }) => {
  if (target.value === 'default') {
    delete root.dataset.colorScheme;
  } else {
    root.dataset.colorScheme = target.value;
  }
});
