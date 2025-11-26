class CourseManager {
  static main() {
    // const preferences = new CourseManager();
    // preferences.setup();
    CourseManager.setup();
  }

  static setup() {
    const progressElements = document.querySelectorAll('.progress');
    progressElements.forEach((element) => {
      const value = window.localStorage.getItem(element.id);
      if (value) {
        element.textContent = value;
      }
    });
  }
}

window.addEventListener('load', CourseManager.main);
