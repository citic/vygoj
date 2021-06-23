import express from 'express';
import common from '../common/common.js';

// Create an express router that communicates with app object and provides
// functions to help with routing of URIs
const router = express.Router();

// Log each HTTP request
router.use((req, res, next) => {
  console.log(`${req.method} ${req.url}`);
  // Define a res.xhtml() method that renders xhtml content-type used by vygot
  res.xhtml = function() {
    return this.contentType('application/xhtml+xml');
  };
  next();
});

// Homepage
router.get('/', (req, res) => {
  res.xhtml().render('index', {
    title: 'Vygoj: Vygotsky Online Judge',
  });
});

// 404 not found error page
router.use((req, res) => {
  res.status(404).xhtml().render('not_found', {
    title: 'Page not found',
  });
});

export default router;
