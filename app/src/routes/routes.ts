// Library imports
import express from 'express';
import session from 'express-session';
import path from 'path';

// Vygot imports
import courseController from '../controllers/courseController.js';
import errorController from '../controllers/errorController.js';
import log from '../controllers/log.js';
import userController from '../controllers/userController.js';

// Create an express router that communicates with app object and provides
// functions to help with routing of URIs
const router = express.Router();

// Log each HTTP request
router.use((req, res, next) => { log.appendHttpRequest(req); next(); });
// Wait for the body of POST HTTP-Requests and parse it as att1=val1&att2=val2
router.use(express.urlencoded({ extended: false }));

// Sessions
router.use(session({
  secret: 'Yes, size matters, longer is much better! (At least for this text)',
  resave: false,
  saveUninitialized: false,
}));

// Homepage
router.get('/', (req, res) => { courseController.getIndex(req, res); });

// Users
router.get('/user/login', (req, res) => {
  userController.getUserLogin(req, res);
});
router.post('/user/login', (req, res) => {
  userController.postUserLogin(req, res);
});
router.get('/user/:userId', (req, res) => {
  userController.getUserPreferences(req, res);
});
router.post('/user/preferences', (req, res) => {
  userController.postUserPreferences(req, res);
});

// Courses
router.get('/course/:courseId', (req, res) => {
  courseController.getCourse(req, res);
});

// Problems
router.get('/status', (req, res) => {
  if (Math.random() < 0.75) {
    res.json({ status: 'online' });
  } else {
    res.json({ status: 'offline' });
  }
});

// Serve static files such as XHTML, CSS, JS, images, sounds, videos
// express.static(path) returns a middleware function that looks for URIs that
// match files into the public/ folder, and serves them setting their content-
// type according to their file extension
router.use(express.static(path.join(process.cwd(), 'public')));
// 404 not found error page
router.use((req, res) => { errorController.getNotFound(req, res); });

// Chain the router using the import/export mechanism
export default router;
