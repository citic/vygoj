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
  getUserPreferences(req: Request, res: Response, errorMessage = '') {
    if (req.session.user) {
      res.contentType('application/xhtml+xml').render('user/preferences', {
        title: 'User preferences',
        stylesheet: 'user',
        user: User.factory(req.session.user),
        errorMessage,
      });
    } else {
      // Oops, internal error, may be the cookie is obsolete
      res.redirect('/user/login');
    }
  }

  // POST /user/preferences
  // Called when user presses a button in its preferences form
  postUserPreferences(req: Request, res: Response) {
    switch (req.body.action) {
      case 'deactivate': return this.deactivateUser(req, res);
      case 'delete': return this.deleteUser(req, res);
      case 'logout': return this.logoutUser(req, res);
      case 'update': return this.updateUser(req, res);
      default: res.redirect('/'); // Internal error
    }
  }

  // eslint-disable-next-line class-methods-use-this
  deactivateUser(req: Request, res: Response) {
    // TODO: set active until date
    res.redirect('/');
  }

  async deleteUser(req: Request, res: Response) {
    // If there is a logged in user
    if (req.session.user) {
      await User.deleteById(req.session.user._id);
    }

    // Show login form
    return this.logoutUser(req, res);
  }

  // eslint-disable-next-line class-methods-use-this
  logoutUser(req: Request, res: Response) {
    req.session.destroy((error) => {
      if (error) {
        console.error(error);
      }
      res.redirect('/user/login');
    });
  }

  // Called when user presses the Update
  async updateUser(req: Request, res: Response) {
    // Get the user object
    const user = User.factory(req.session.user);
    let errorMessage = '';
    // Update its fields
    // TODO: Validate that field values are not empty nor code injection
    user.name = req.body.name;
    user.email = req.body.email;
    user.uiMode = req.body.ui_mode;
    // If user asked to change password
    if (req.body.current_password.length > 0) {
      if (req.body.current_password === user.password) {
        const newPassword = req.body.new_password.trim();
        if (newPassword.length > 0) {
          user.password = newPassword;
        } else {
          errorMessage = 'New password cannot be empty';
        }
      } else {
        errorMessage = 'Invalid password';
      }
    }
    // If no errors, save user preferences in DB
    if (errorMessage === '') {
      // TODO: Manage exceptions try/catch
      await user.update();
      req.session.user = user;
    }
    // Show the preferences form again
    return this.getUserPreferences(req, res, errorMessage);
  }
} // class

// Export the singleton controller
const userController = new UserController();
export default userController;
