import database from '../util/database.js';

export const enum Role {
  unknown = 'unknown',
  admin = 'admin',
  professor = 'professor',
  student = 'student',
  assistant = 'assistant',
}

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

export class User {
  // Creates class attributes using parameter properties
  constructor(public id: number,
    public role: Role = Role.unknown,
    public name: string = '',
    public email: string = '',
    public password = '',
    public preferences: Preferences = Preferences.default()) {
  }

  async save() {
    return await database.get().collection('users').insertOne(this);
  }
}
