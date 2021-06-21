import http from 'http';
import express from 'express';

// This application name
const appName = 'vygoj';
// Default internet port where server will be listening for connections
const port = 8080;

// Express is a factory function. When it is run, it returns a HTTP request
// handler function that receives (req, res) objects
const app = express();
// Create a web server using the standard http module
const server = http.createServer(app);
// Start listening for connections, HTTP requests, and manage them
console.log(`${appName} listening on port ${port}...`);
server.listen(port);
