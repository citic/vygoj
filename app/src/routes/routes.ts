// Library imports
import express from 'express';
import session from 'express-session';
import path from 'path';

// Vygot imports
import backendController from '../controllers/backendController.js';
import courseController from '../controllers/courseController.js';
import errorController from '../controllers/errorController.js';
import log from '../controllers/log.js';
import userController from '../controllers/userController.js';

// Create an express router that communicates with app object and provides
// functions to help with routing of URIs
const router = express.Router();

// General -------------------------------------------------------------------
// Log each HTTP request
router.use((req, res, next) => {
  log.appendHttpRequest(req); next();
});
// Wait for the body of POST HTTP-Requests and parse it as att1=val1&att2=val2
router.use(express.urlencoded({ extended: false }));

// Sessions -------------------------------------------------------------------
router.use(session({
  secret: 'Yes, size matters, longer is much better! (At least for this text)',
  resave: false,
  saveUninitialized: false,
}));
// Change database user by a User instance object
router.use((req, res, next) => {
  userController.setRequestUser(req, res, next);
});

// Homepage -------------------------------------------------------------------
// List enrolled courses and available courses for this user
router.get('/', (req, res) => {
  courseController.getIndex(req, res);
});

// Users ----------------------------------------------------------------------
// Get login dialog
router.get('/user/login', (req, res) => {
  userController.getUserLogin(req, res);
});
// User provided credentials for logging in
router.post('/user/login', (req, res) => {
  userController.postUserLogin(req, res);
});
// Get user preferences screen
router.get('/user/:userId', (req, res) => {
  userController.getUserPreferences(req, res);
});
// User changed his/her preferences
router.post('/user/preferences', (req, res) => {
  userController.postUserPreferences(req, res);
});

// Courses --------------------------------------------------------------------
// Professors admin their courses
router.get('/course/admin', (req, res) => {
  courseController.getAdminCourse(req, res);
});
// Professor added/changed a repository or enabled/disabled a course
router.post('/course/admin', (req, res) => {
  courseController.postAdminCourse(req, res);
});
// User clicked a course
router.get('/course/:courseId', (req, res) => {
  courseController.getCourse(req, res);
});

// Problems: judge0 backend status web service
router.get('/status', (req, res) => {
  backendController.getStatus(req, res);
});

// Misc -----------------------------------------------------------------------
// Serve static files such as XHTML, CSS, JS, images, sounds, videos
// express.static(path) returns a middleware function that looks for URIs that
// match files into the public/ folder, and serves them setting their content-
// type according to their file extension
router.use(express.static(path.join(process.cwd(), 'public')));
// 404 not found error page
router.use((req, res) => {
  errorController.getNotFound(req, res);
});

// Chain the router using the import/export mechanism
export default router;
