// Library imports
import * as eta from 'eta';
import express from 'express';

// Vygoj imports
import common from './common/common.js';
import config from './util/config.js';
import database from './util/database.js';
import routes from './routes/routes.js';

// Starts the execution of the server
async function main() {
  // Connect to the database before launching the web server
  await database.connect();
  // Express is a factory function. When it is run, it returns a HTTP request
  // handler function that receives (req, res) objects
  const app = express();

  // Hide the express-powered HTTP header in each response message
  app.disable('x-powered-by');
  // Set Eta as the template engine
  app.engine('eta', eta.renderFile);
  app.set('view engine', 'eta');

  // Routing is the most general operation of the application. Routers
  // distribute HTTP requests between Controllers. Controllers fetch from or
  // put data to Models, and results are shown with Views
  app.use(routes);

  // Start listening for connections, HTTP requests, and manage them
  app.listen(config.getPort());
  console.log(`${common.appName} listening on port ${config.getPort()}...`);
}

try {
  await main();
} catch (error: any) {
  console.error(`Error: ${error.message}`);
  process.exit(1);
}
