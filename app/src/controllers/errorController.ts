import { Request, Response } from 'express';

/**
 * Manages errors reported to users
 */
class ErrorController {
  getNotFound(req: Request, res: Response) {
    res.status(404).contentType('application/xhtml+xml').render('not_found', {
      title: 'Page not found',
    });
  }
}

// Export the singleton controller
const errorController = new ErrorController();
export default errorController;
