/** Mimics a judge0 backend */
import express from 'express';

const port = 2358;

function route(app) {
  app.use('/workers', (req, res) => {
    res.json([{
      queue: '1.13.0',
      available: 0,
      failed: 0,
      idle: 0,
      paused: 0,
      size: 0,
      working: 0,
    },
    ]);
  });
  app.use((req, res) => { res.status(404).send(''); });
}

async function main() {
  const app = express();
  app.disable('x-powered-by');
  app.use(express.urlencoded({ extended: false }));
  route(app);
  app.listen(port);
  console.log(`fake0 listening on port ${port}...`);
}

try {
  await main();
} catch (error) {
  console.error(`Error: ${error.message}`);
  process.exit(1);
}
