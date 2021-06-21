import express from 'express';
import common from './common/common.js';
import routes from './routes/routes.js';

// Express is a factory function. When it is run, it returns a HTTP request
// handler function that receives (req, res) objects
const app = express();

// Route according to the request URI
app.use(routes);

// Start listening for connections, HTTP requests, and manage them
console.log(`${common.appName} listening on port ${common.port}...`);
app.listen(common.port);
