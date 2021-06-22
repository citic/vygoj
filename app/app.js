import * as eta from 'eta';
import express from 'express';
import path from 'path';
import common from './common/common.js';
import routes from './routes/routes.js';

// Express is a factory function. When it is run, it returns a HTTP request
// handler function that receives (req, res) objects
const app = express();

// Hide the express-powered HTTP header in each response message
app.disable('x-powered-by');

// Set Eta as the template engine
app.engine('eta', eta.renderFile);
app.set('view engine', 'eta');

// Serve static files such as XHTML, CSS, JS, images, sounds, videos
// express.static(path) returns a middleware function that looks for URIs that
// match files into the public/ folder, and serves them setting their content-
// type according to their file extension
app.use(express.static(path.join(process.cwd(), 'public')));

// Route according to the request URI
app.use(routes);

// Start listening for connections, HTTP requests, and manage them
console.log(`${common.appName} listening on port ${common.port}...`);
app.listen(common.port);
