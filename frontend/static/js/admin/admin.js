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

// Listened in the document, so the forms of the rows that a search brings ask too (site.js)
document.addEventListener('submit', (event) => {
  const form = event.target;
  const text = form.method === 'post' ? confirmationOf(form) : null;
  // eslint-disable-next-line no-alert -- a native dialog is enough for a rare admin action
  if (text && !window.confirm(text)) {
    event.preventDefault();
  }
});

// The file of users to import: Import is enabled when a file is chosen, and the fieldset also
// takes a file dropped on it. The disabled state is set here, so the form works without scripts
const usersFile = document.getElementById('users_file');
if (usersFile) {
  const importButton = usersFile.form.querySelector('button[type="submit"]');
  const enableImport = () => {
    importButton.disabled = usersFile.files.length === 0;
  };
  const dropZone = usersFile.closest('fieldset');
  dropZone.addEventListener('dragover', (event) => event.preventDefault());
  dropZone.addEventListener('drop', (event) => {
    event.preventDefault();
    usersFile.files = event.dataTransfer.files;
    enableImport();
  });
  usersFile.addEventListener('change', enableImport);
  enableImport();
}
