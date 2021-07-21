export const enum ThemeMode {
  light = 'light',
  dark = 'dark',
}

export class Preferences {
  constructor(public mode: ThemeMode = ThemeMode.light) {
  }

  static default() {
    return new Preferences();
  }

  static mapMode(text: string) {
    switch (text) {
      case 'dark':
        return ThemeMode.dark;

      case 'light':
      default:
        return ThemeMode.light;
    }
  }
}
