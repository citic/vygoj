// Form of a section of a course (section.html): enables its button when the required fields are
// filled, suggests the weeks of each duration, pads the section numbers with zeros (003 005 006),
// estimates the end and archive dates, remembers its values for the next new section, and
// asks before Cancel leaves it changed. The server checks every field again

// Key of localStorage with the values of the last section saved in this browser
const STORAGE_KEY = 'section:values';
// Fields that are never remembered: the token of the form and the password of the section
const NOT_REMEMBERED = ['csrf_token', 'new_password', 'remove_password'];
// Largest number of a section
const MAX_NUMBER = 999;
// Milliseconds that the copy button of the password says that it was copied
const COPIED_TIME = 2000;

/**
 * Return the date of the ISO text (yyyy-mm-dd) plus the given days, as ISO text
 * @param {string} text
 * @param {number} days
 * @returns {string}
 */
function addDays(text, days) {
  const date = new Date(`${text}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

class SectionFormManager {
  // The form of the section, HTMLFormElement
  form;

  // Weeks of each duration, as {duration: weeks}, Object
  weeks;

  // Fields of the dates, the duration, its weeks, and the section numbers, HTMLInputElement and
  // HTMLSelectElement
  start;

  end;

  archive;

  duration;

  weeksField;

  number;

  // Button that estimates the end and archive dates, HTMLButtonElement
  estimateButton;

  // Button that sends the form (Offer or Save), HTMLInputElement
  saveButton;

  // Checkboxes of the methods of enrollment, at least one is required, HTMLInputElement[]
  methods;

  // True if the professor wrote the end or archive date, so they are not estimated again without
  // asking, boolean
  customDates = false;

  // Values of the form when the page was ready, to know if Cancel loses changes, string
  initialValues = '';

  // Field of the password, and its icon buttons that show it and copy it, HTMLInputElement and
  // HTMLButtonElement
  password;

  showButton;

  copyButton;

  constructor(form) {
    this.form = form;
    this.weeks = JSON.parse(form.dataset.weeks);
    this.start = form.elements.start_date;
    this.end = form.elements.end_date;
    this.archive = form.elements.archive_date;
    this.duration = form.elements.duration;
    this.weeksField = form.elements.weeks;
    this.number = form.elements.number;
    this.estimateButton = form.querySelector('.estimate');
    this.saveButton = form.querySelector('input[type="submit"]');
    this.methods = [form.elements.self_enroll, form.elements.manual_enroll];
    if ('new' in form.dataset) {
      this.restoreValues();
    }
    this.weeksField.disabled = !this.weeks[this.duration.value];
    this.customDates = this.hasCustomDates();
    this.initialValues = this.currentValues();
    this.addListeners();
    this.setupPassword();
    this.updateSaveButton();
  }

  // The buttons of the password work only with scripts, so they are shown here. Copy is enabled
  // while the field has a password
  setupPassword() {
    this.password = this.form.elements.new_password;
    this.showButton = this.form.querySelector('.show_password');
    this.copyButton = this.form.querySelector('.copy_password');
    this.showButton.hidden = false;
    this.copyButton.hidden = false;
    const updateCopy = () => {
      this.copyButton.disabled = this.password.value === '';
    };
    updateCopy();
    this.password.addEventListener('input', updateCopy);
    this.showButton.addEventListener('click', () => this.togglePassword());
    this.copyButton.addEventListener('click', () => this.copyPassword());
  }

  // Show the password as text, or hide it again, with the icon and name of the next action
  togglePassword() {
    const shown = this.password.type === 'password';
    this.password.type = shown ? 'text' : 'password';
    this.showButton.textContent = shown ? 'visibility_off' : 'visibility';
    this.showButton.setAttribute('aria-pressed', String(shown));
    const label = shown ? this.showButton.dataset.hide : this.showButton.dataset.show;
    this.showButton.setAttribute('aria-label', label);
    this.showButton.title = label;
  }

  // Copy the password to the clipboard, and say so in the button for a moment. If the browser
  // refuses (e.g. an http:// address), the password is selected for the professor to copy it
  async copyPassword() {
    const label = this.copyButton.getAttribute('aria-label');
    try {
      await navigator.clipboard.writeText(this.password.value);
      this.copyButton.textContent = 'check';
      this.copyButton.setAttribute('aria-label', this.copyButton.dataset.done);
      this.copyButton.title = this.copyButton.dataset.done;
      setTimeout(() => {
        this.copyButton.textContent = 'content_copy';
        this.copyButton.setAttribute('aria-label', label);
        this.copyButton.title = label;
      }, COPIED_TIME);
    } catch {
      this.password.focus();
      this.password.select();
    }
  }

  addListeners() {
    this.form.addEventListener('input', () => this.updateSaveButton());
    this.form.addEventListener('change', () => this.updateSaveButton());
    this.duration.addEventListener('change', () => this.durationChanged());
    [this.start, this.weeksField].forEach((field) => {
      field.addEventListener('change', () => this.periodChanged());
    });
    this.number.addEventListener('change', () => this.padNumbers());
    [this.end, this.archive].forEach((field) => {
      field.addEventListener('input', () => {
        this.customDates = true;
      });
    });
    this.estimateButton.addEventListener('click', () => {
      this.customDates = false;
      this.applyEstimate();
    });
    this.form.addEventListener('submit', () => this.rememberValues());
    const cancel = this.form.querySelector('.cancel');
    cancel.addEventListener('click', (event) => {
      // eslint-disable-next-line no-alert -- a native dialog is enough to confirm leaving a form
      if (this.currentValues() !== this.initialValues && !window.confirm(cancel.dataset.confirm)) {
        event.preventDefault();
      }
    });
  }

  // The button is enabled when the required fields are valid and a method of enrollment is chosen
  updateSaveButton() {
    const method = this.methods.some((checkbox) => checkbox.checked);
    this.saveButton.disabled = !method || !this.form.checkValidity();
  }

  // The duration changed: its weeks are suggested, the longest of its range, and an indefinite
  // section has none
  durationChanged() {
    const weeks = this.weeks[this.duration.value];
    this.weeksField.value = weeks ? String(weeks) : '';
    this.weeksField.disabled = !weeks;
    this.periodChanged();
  }

  // Write each section number with 3 digits, separated by one space (3  5 → 003 005). Texts that
  // are not numbers are left as they are, so the field shows them invalid
  padNumbers() {
    const parts = this.number.value.trim().split(/\s+/).filter((part) => part !== '');
    if (parts.every((part) => /^[0-9]{1,3}$/.test(part))) {
      this.number.value = parts.map((part) => part.padStart(3, '0')).join(' ');
      this.updateSaveButton();
    }
  }

  // The start date or the weeks changed: the dates are estimated again, unless the professor
  // wrote them, who gets the button to estimate them
  periodChanged() {
    if (this.customDates) {
      this.estimateButton.hidden = this.estimate() === null;
    } else {
      this.applyEstimate();
    }
  }

  /**
   * Return the end and archive dates estimated from the start date and the weeks (the archive
   * date after twice them), or null without start date or weeks (e.g. indefinite)
   * @returns {{end: string, archive: string}|null}
   */
  estimate() {
    const weeks = Number.parseInt(this.weeksField.value, 10);
    if (!this.start.value || this.weeksField.disabled || !(weeks > 0)) {
      return null;
    }
    return {
      end: addDays(this.start.value, weeks * 7),
      archive: addDays(this.start.value, weeks * 14),
    };
  }

  // Write the estimated dates, or empty them if there is no estimate
  applyEstimate() {
    const dates = this.estimate();
    this.end.value = dates ? dates.end : '';
    this.archive.value = dates ? dates.archive : '';
    this.estimateButton.hidden = true;
    this.updateSaveButton();
  }

  /**
   * True if the end or archive date has a value that is not the estimate
   * @returns {boolean}
   */
  hasCustomDates() {
    const dates = this.estimate();
    return (this.end.value !== '' && this.end.value !== dates?.end)
      || (this.archive.value !== '' && this.archive.value !== dates?.archive);
  }

  /**
   * Return the fields of the form that are remembered
   * @returns {Array<HTMLInputElement|HTMLSelectElement>}
   */
  rememberedFields() {
    return [...this.form.elements].filter((field) => field.name
      && !NOT_REMEMBERED.includes(field.name) && field.type !== 'submit');
  }

  /**
   * Return the values of the remembered fields, as JSON, to compare them
   * @returns {string}
   */
  currentValues() {
    return JSON.stringify(Object.fromEntries(this.rememberedFields().map((field) => [field.name,
      field.type === 'checkbox' ? field.checked : field.value])));
  }

  // Keep the values of the section saved, for the next new section of any course
  rememberValues() {
    try {
      window.localStorage.setItem(STORAGE_KEY, this.currentValues());
    } catch {
      // Without storage (e.g. a private window), the next section starts with the defaults
    }
  }

  // Fill a new section with the values of the last one saved, with the number after the largest
  // one it had. Values that
  // are not valid anymore (e.g. a currency that the server removed) are skipped
  restoreValues() {
    let values;
    try {
      values = JSON.parse(window.localStorage.getItem(STORAGE_KEY));
    } catch {
      return;
    }
    if (!values || typeof values !== 'object') {
      return;
    }
    this.rememberedFields().forEach((field) => {
      const value = values[field.name];
      if (field.type === 'checkbox' && typeof value === 'boolean') {
        field.checked = value;
      } else if (typeof value === 'string' && (field.tagName !== 'SELECT'
          || [...field.options].some((option) => option.value === value))) {
        field.value = value;
      }
    });
    const numbers = this.number.value.trim().split(/\s+/).map((part) => Number.parseInt(part, 10));
    const last = Math.max(...numbers);
    if (Number.isInteger(last) && last < MAX_NUMBER) {
      this.number.value = String(last + 1).padStart(3, '0');
    }
  }
}

const form = document.getElementById('section_form');
if (form) {
  // eslint-disable-next-line no-new -- the manager listens to the form
  new SectionFormManager(form);
}
