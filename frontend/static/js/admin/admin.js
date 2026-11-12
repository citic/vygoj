// Pages of the administration. Actions that change or delete data ask for confirmation first:
// forms with the text of their data-confirm attribute, and forms whose chosen option (e.g. the
// status of a user) has a data-confirm attribute and differs from the option they came with

/**
 * Return the text to confirm before sending the form, or null if it needs no confirmation
 * @param {HTMLFormElement} form
 * @returns {string|null}
 */
function confirmationOf(form) {
  if (form.dataset.confirm) {
    return form.dataset.confirm;
  }
  const changed = [...form.querySelectorAll('input[type="radio"][data-confirm]')]
    .find((input) => input.checked && !input.defaultChecked);
  return changed ? changed.dataset.confirm : null;
}

document.querySelectorAll('form[method="post"]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    const text = confirmationOf(form);
    // eslint-disable-next-line no-alert -- a native dialog is enough for a rare admin action
    if (text && !window.confirm(text)) {
      event.preventDefault();
    }
  });
});
