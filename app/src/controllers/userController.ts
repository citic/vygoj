import { Request, Response } from 'express';
import { User } from '../models/user.js';

// Adds the user reference to the session data
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
  // GET /user/login
  // Get the user login form
  // eslint-disable-next-line class-methods-use-this
  getUserLogin(req: Request, res: Response) {
    res.contentType('application/xhtml+xml').render('user/login', {
      title: 'User login',
      stylesheet: 'user',
      user: req.session.user,
    });
  }

  // POST /user/login
  // Called after filling out the login dialog
  // eslint-disable-next-line class-methods-use-this
  async postUserLogin(req: Request, res: Response) {
    // Get data provided by user in the login form
    const email = req.body.email as string;
    const password = req.body.password as string;
    const user = await User.findByEmail(email);
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
  // Called when a logged in user asks for its user profile/preferences
  // eslint-disable-next-line class-methods-use-this
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
  // Called when user saves its preferences
  // eslint-disable-next-line class-methods-use-this
  postUserPreferences(req: Request, res: Response) {
    if (req.body.action === 'update') {
      // TODO: Save user preferences in DB
      res.redirect('/user/preferences');
    } else if (req.body.action === 'logout') {
      req.session.destroy((error) => {
        if (error) {
          console.error(error);
        }
        res.redirect('/user/login');
      });
    } else {
      // Internal error
      res.redirect('/');
    }
  }
}

// Export the singleton controller
const userController = new UserController();
export default userController;
