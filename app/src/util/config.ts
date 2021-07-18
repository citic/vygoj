import fs from 'fs';
import path from 'path';

// MongoDB database connection string
interface ConfigJson {
  // Allows to have arbitrary properties as any regular object
  [key: string]: string;
}

// Singleton Config object
// Manages the application configuration made by IT professionals, such as
// databases, max users allowed and so on. The configuration file is located
// at 'config/config.json' under the application folder
class Config {
  public config: ConfigJson | null = null;

  load() {
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

  // Get the value of a configuration key. Configuration is a set of key/value
  // pairs loaded from config.json file. Be sure to call load() before calling
  // this method.
  get(key: string) {
    if (this.config && this.config.hasOwnProperty(key)) {
      return this.config[key];
    }
    throw new Error(`load configuration file before using it`);
  }
}

// Singleton
const config = new Config();
export default config;
