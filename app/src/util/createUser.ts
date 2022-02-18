import database from './database.js';
import { User, Role } from '../models/user.js';

// The default users database
const users = [
  new User(Role.admin, 'Admin', 'admin@vygoj.com', 'adminvyg'),
  // new User(Role.professor, 'Professor', 'prof@vygoj.com', 'profvyg'),
  // new User(Role.student, 'Student', 'student@vygoj.com', 'studvyg'),
  // new User(Role.assistant, 'Assistant', 'assistant@vygoj.com', 'assistvyg'),
];

/**
 * Creates the admin user in the database using default values. This procedure
 * must be done when the app is installed for first time or after zapping the
 * database. The app must be configured before, i.e. setting the database in
 * config.json file After creating the admin user, it ca be used to log in by
 * using a web browser and change the password by a secure one.
 */
async function createUser() {
  // Connect to the database before creating the admin user
  await database.connect();
  // TODO: Receive role, name, email, and password by CLI arguments
  // TODO: If there is a least an admin user, stop unless -f is given
  // TODO: If user already exists raise an error
  // Insert the user into the database
  for (let index = 0; index < users.length; ++index) {
    const user = users[index];
    await database.users().insertOne(user);
    // Start listening for connections, HTTP requests, and manage them
    console.log(`${user.role} user ${user.name} <${user.email}> created with password ${user.password}`);
    console.log();
    console.log('Log in with this user using a web browser and change its password.');
    console.log('Then you can create more users using the web interface.');
  }
  process.exit(0);
}

try {
  await createUser();
} catch (error) {
  console.error(`Error: ${error.message}`);
}
