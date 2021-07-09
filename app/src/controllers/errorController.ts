import { Request, Response } from 'express';

/**
 * Manages errors reported to users
 */
class ErrorController {
  getNotFound(req: Request, res: Response) {
    res.status(404).xhtml().render('not_found', {
      title: 'Page not found',
    });
  }
}

// Export the singleton controller
const errorController = new ErrorController();
export default errorController;
