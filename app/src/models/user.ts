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
    this.email = email.toLowerCase();
  }

  async save() {
    return await database.users().insertOne(this);
  }

  // Find a user in DB by email, returns an array of objects
  static async findByEmail(email: string) {
    // Build a query object having email in lowercase
    const query = { email: email.toLowerCase() };
    // Get all users with this email in database
    const users = await database.users().find(query).toArray() as User[];
    // Only one user must have this email (i.e unique key)
    if (users.length > 1) {
      throw new Error(`dberror: several users with email ${email}`);
    }
    // If found return this user. If not-found, array is empty, return undefined
    return users.length === 1 ? users[0] : undefined;
  }
}
