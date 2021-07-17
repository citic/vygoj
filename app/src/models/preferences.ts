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
}
