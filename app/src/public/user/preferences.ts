class Preferences {
  static main() {
    const preferences = new Preferences();
    preferences.setup();
  }

  setup() {
    const deleteButton = document.getElementById('delete_button') as HTMLButtonElement;
    deleteButton.addEventListener('click', (event) => { this.deleteUser(event); });
  }

  // eslint-disable-next-line class-methods-use-this
  deleteUser(event: Event) {
    // TODO: Use real email in a hidden field. User may easily change this
    const email = document.getElementById('email') as HTMLInputElement;
    const message = 'Please confirm that you want to delete your account by entering your email. This action can be undone only by an active administrator';
    // TODO: Replace confirm by a custom dialog
    if (window.prompt(message) !== email.value) {
      event.preventDefault();
    }
  }
}

window.addEventListener('load', Preferences.main);
