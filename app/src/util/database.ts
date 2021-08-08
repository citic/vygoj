import { MongoClient, Db } from 'mongodb';
import config from './config.js';

// Manages the connection with the database
class Database {
  // The client connection to the database.
  database: Db | null = null;

  // Establish the connection with the database
  // Call this function before using the database object
  async connect() {
    const client = await MongoClient.connect(config.getDatabase());
    this.database = client.db();
    return this.database;
  }

  // Get a reference to the database
  get() {
    if (this.database) {
      return this.database;
    }
    throw new Error('Must call database.connect() before getting it');
  }

  // Get a collection
  collection(name: string) {
    return this.get().collection(name);
  }

  // Get application-wide specific collections
  // Get the users collection
  users() { return this.collection('users'); }

  // Get the courses collection
  courses() { return this.collection('courses'); }
}

// Exports the Singleton Database instance
const database = new Database();
export default database;
