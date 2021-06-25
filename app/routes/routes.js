// Library imports
import express from 'express';
import path from 'path';

// Vygot imports
import courseController from '../controllers/courseController.js';
import errorController from '../controllers/errorController.js';
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
router.get('/', (req, res, next) => { courseController.getIndex(req, res); });
// Serve static files such as XHTML, CSS, JS, images, sounds, videos
// express.static(path) returns a middleware function that looks for URIs that
// match files into the public/ folder, and serves them setting their content-
// type according to their file extension
router.use(express.static(path.join(process.cwd(), 'public')));
// 404 not found error page
router.use((req, res, next) => { errorController.getNotFound(req, res); });

// Chain the router using the import/export mechanism
export default router;
