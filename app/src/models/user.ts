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
  mode: ThemeMode;

  constructor(mode: ThemeMode = ThemeMode.light) {
    this.mode = mode;
  }

  static default() {
    return new Preferences();
  }
}

export class User {
  id: number = 0;
  role: Role = Role.unknown;
  name: string = '';
  email: string = '';
  password: string = '';
  preferences: Preferences = Preferences.default();

  constructor(id: number
    , role: Role = Role.unknown
    , name: string = ''
    , email: string = ''
    , password = ''
    , preferences: Preferences = Preferences.default()) {
    this.id = id;
    this.role = role;
    this.name = name;
    this.email = email;
    this.password = password;
  }

  async save() {
    return await database.get().collection('users').insertOne(this);
  }
}
