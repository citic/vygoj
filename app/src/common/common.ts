import http from 'http';

// This object contains the global consts
export default {
  // This application name
  appName: 'vygoj',
};

// Simulates a browser fetch() function
// TODO: replace usages by node-fetch module
export function fetch(url: string) {
  return new Promise((resolve, reject) => {
    http.get(url, (response) => {
      let data = '';

      // A data chunk has been received from server
      response.on('data', (chunk) => {
        data += chunk;
      });

      // Server reported the transfer is complete
      response.on('end', () => {
        resolve(data);
      });
    }).on('error', (error) => {
      reject(error);
    });
  });
}

export async function fetchJson(url: string) {
  const data = await fetch(url) as string;
  return JSON.parse(data);
}

export function serverEncode(text: string) {
  // See https://stackoverflow.com/a/69992416
  return Buffer.from(text, 'utf8').toString('base64');
}

export function serverDecode(data: string) {
  // See https://stackoverflow.com/a/69992416
  return Buffer.from(data, 'base64').toString('utf8');
}
