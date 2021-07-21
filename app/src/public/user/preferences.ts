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
    // TODO: Replace confirm by a custom dialog
    if (!window.confirm('Do you want to delete your account?\nThis action can be undone only by an active administrator')) {
      event.preventDefault();
    }
  }
}

window.addEventListener('load', Preferences.main);
