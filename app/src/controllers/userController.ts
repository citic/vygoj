import { Request, Response } from 'express';

/**
 * Manages users, login, logout, preferences
 */
class UserController {
  // eslint-disable-next-line class-methods-use-this
  getUserLogin(req: Request, res: Response) {
    res.contentType('application/xhtml+xml').render('user/login', {
      title: 'User login',
      stylesheet: 'user',
    });
  }
}

// Export the singleton controller
const userController = new UserController();
export default userController;
