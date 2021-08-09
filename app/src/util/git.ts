import simpleGit, { SimpleGit, SimpleGitOptions } from 'simple-git';
// import config from './config.js';

const options: Partial<SimpleGitOptions> = {
  baseDir: `${process.cwd()}/data`,
  binary: 'git',
  maxConcurrentProcesses: 6, // config.gitMaxProcess
};

// Manages the git client
class Git {
  gitClient: SimpleGit;

  constructor() {
    this.gitClient = simpleGit(options);
  }
}

// Exports the Singleton Database instance
const git = new Git();
export default git;
