// Library imports
import * as eta from 'eta';
import express from 'express';

// Vygoj imports
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

// Routing is the most general operation of the application. Routers distribute
// HTTP requests between Controllers. Controllers fetch from or put data to
// Models, and results are shown with Views
app.use(routes);

// Start listening for connections, HTTP requests, and manage them
console.log(`${common.appName} listening on port ${common.port}...`);
app.listen(common.port);
