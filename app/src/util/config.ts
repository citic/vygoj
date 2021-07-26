import fs from 'fs';
import path from 'path';

interface ConfigJson {
  // MongoDB database connection string
  database: string;
  // The network port wher app is listening for connections
  port: number;
  // The connection string to the judge backend service
  backend: string;
  // Milliseconds the judge backend service is checked
  backendStatusInterval: number;
}

// Singleton Config object
// Manages the application configuration made by IT professionals, such as
// databases, max users allowed and so on. The configuration file is located
// at 'config/config.json' under the application folder
class Config {
  public config: ConfigJson;

  constructor() {
    // Config file is in config/config.json file
    const filename = path.join(process.cwd(), 'config', 'config.json');
    // Read the entire contents of the file as a string
    const contents = fs.readFileSync(filename, 'utf-8');
    if (contents) {
      this.config = JSON.parse(contents);
    } else {
      throw new Error(`could not load configuration from ${filename}`);
    }
  }

  // Get the value of each configuration key. Be sure to call load() before
  // calling any of these methods
  getDatabase() { return this.config.database; }

  // Network port where Vygoj app will listen
  getPort() { return this.config.port; }

  // The connection string to the judge backend service
  getBackend() { return this.config.backend; }

  // Milliseconds the judge backend service is checked
  getBackendStatusInterval() { return this.config.backendStatusInterval; }
}

// Singleton
const config = new Config();
export default config;
