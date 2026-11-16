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
