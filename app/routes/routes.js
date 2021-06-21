import express from 'express';
import path from 'path';
import common from '../common/common.js';

// Create an express router that communicates with app object and provides
// functions to help with routing of URIs
const router = express.Router();

// Log each HTTP request
router.use((req, res, next) => {
  console.log(`${req.method} ${req.url}`);
  next();
});

// Homepage
router.get('/', (req, res) => {
  res.send(`${common.appName} web app`);
});

// 404 not found error page
router.use((req, res) => {
  res.status(404).sendFile(path.join(process.cwd(), 'views/not_found.xhtml'));
});

export default router;
