// Lists of courses of the home page. Actions that cannot be undone from the page, such as offering
// a prepared course to every user, ask for confirmation first with the text of the data-confirm
// attribute of their form. Listened in the document, so the cards that a search brings ask too
document.addEventListener('submit', (event) => {
  const form = event.target;
  // eslint-disable-next-line no-alert -- a native dialog is enough for a rare action
  if (form.matches('.courses form[data-confirm]') && !window.confirm(form.dataset.confirm)) {
    event.preventDefault();
  }
});
