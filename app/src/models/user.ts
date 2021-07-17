import { Preferences } from './preferences.js';
import database from '../util/database.js';
import { ObjectId } from 'mongodb';

export const enum Role {
  unknown = 'unknown',
  admin = 'admin',
  professor = 'professor',
  student = 'student',
  assistant = 'assistant',
}

export class User {
  public _id: ObjectId;
  // Creates class attributes using parameter properties
  constructor(public role: Role = Role.unknown,
    public name: string = '',
    public email: string = '',
    public password = '',
    public preferences: Preferences = Preferences.default()) {
    this._id = new ObjectId();
    this.email = email.toLowerCase();
  }

  async save() {
    await database.users().insertOne(this);
  }

  // Find a user in DB by email, returns the found user object
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

  // Find a user in DB by ID
  static async findById(id: string) {
    // Build a query converting the string to a valid MongoDB ObjectId
    const query = { _id: new ObjectId(id) };
    // Get the user, next() returns a promise to the last object of the results
    const user = await database.users().find(query).next() as User;
    // Return the result. It may be undefined
    return user;
  }
}
