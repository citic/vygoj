import { Request, Response } from 'express';

interface User {
  id: number;
  role: string;
  name: string;
  email: string;
  password: string;
}

// https://stackoverflow.com/a/65696437
declare module 'express-session' {
  interface SessionData {
    user: User;
  }
}

/**
 * Manages users, login, logout, preferences
 */
class UserController {
  // The users database
  users:User[] = [
    { id: 1, role: 'admin', name: 'Admin', email: 'admin@vygoj.com', password: 'adminvyg'},
    { id: 2, role: 'professor', name: 'Professor', email: 'prof@vygoj.com', password: 'profvyg'},
    { id: 3, role: 'student', name: 'Student', email: 'student@vygoj.com', password: 'studvyg'},
  ];

  // eslint-disable-next-line class-methods-use-this
  getUserLogin(req: Request, res: Response) {
    res.contentType('application/xhtml+xml').render('user/login', {
      title: 'User login',
      stylesheet: 'user',
      user: req.session.user,
    });
  }

  // POST /user/login
  // Called after filling out the Login dialog
  postUserLogin(req: Request, res: Response) {
    // Get data provided by user in the login form
    const email = req.body.email as string;
    const password = req.body.password as string;
    const user = this.findByEmail(email);
    // If provided credentials are valid
    if (user && user.password === password) {
      // Store user name in the session
      req.session.user = user;
      // Show homepage with user login
      res.redirect('/');
    } else {
      // Show login form again with an error message
      res.contentType('application/xhtml+xml').render('user/login', {
        title: 'User login',
        stylesheet: 'user',
        errorMessage: 'Invalid user or password',
      });
    }
  }

  // GET /user/123
  getUserPreferences(req: Request, res: Response) {
    if (req.session.user) {
      res.contentType('application/xhtml+xml').render('user/preferences', {
        title: 'User preferences',
        stylesheet: 'user',
        user: req.session.user,
      });
    } else {
      // Oops, internal error, may be the cookie is obsolete
      res.redirect('/user/login');
    }
  }

  // POST /user/preferences
  postUserPreferences(req: Request, res: Response) {
    if (req.body.action === 'update') {
      res.redirect('/user/preferences');
    } else if (req.body.action === 'logout') {
      req.session.user = undefined;
      res.redirect('/user/login');
    } else {
      // Internal error
      res.redirect('/');
    }
  }

  // Find a user by email
  findByEmail(email: string) {
    return this.users.find((user) => user.email.toLowerCase() === email.toLowerCase());
  }

  // Find a user by id
  findById(id: number) {
    return this.users.find((user) => user.id === id);
  }
}

// Export the singleton controller
const userController = new UserController();
export default userController;
