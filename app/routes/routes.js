import express from 'express';

import courseController from '../controllers/course.js';
import log from '../controllers/log.js';

// Create an express router that communicates with app object and provides
// functions to help with routing of URIs
const router = express.Router();

// Define a res.xhtml() method that renders xhtml content-type used by vygot
function injectXhtml(req, res, next) {
  res.xhtml = function xhtml() {
    return this.contentType('application/xhtml+xml');
  };
  next();
}

// Inject req.xhtml() method
router.use(injectXhtml);
// Log each HTTP request
router.use((req, res, next) => { log.appendHttpRequest(req); next(); });
// Homepage
router.get('/', courseController.getIndex);

// 404 not found error page
router.use((req, res) => {
  res.status(404).xhtml().render('not_found', {
    title: 'Page not found',
  });
});

export default router;
