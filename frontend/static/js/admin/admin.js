// Pages of the administration. Forms that delete data ask for confirmation first, with the text of
// their data-confirm attribute
document.querySelectorAll('form[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    // eslint-disable-next-line no-alert -- a native dialog is enough for a rare admin action
    if (!window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
});
