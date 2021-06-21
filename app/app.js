import express from 'express';
import * as common from './common/common.js';

// Express is a factory function. When it is run, it returns a HTTP request
// handler function that receives (req, res) objects
const app = express();

// Log each HTTP request
app.use((req, res, next) => {
  console.log(`${req.method} ${req.url}`);
  next();
});

app.get('/', (req, res, next) => {
  res.send(`${common.appName} web app`);
});

// Start listening for connections, HTTP requests, and manage them
console.log(`${common.appName} listening on port ${common.port}...`);
app.listen(common.port);
