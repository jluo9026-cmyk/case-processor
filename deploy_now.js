const https = require('https');

const TOKEN = 'rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt';
const SERVICE = 'srv-d916j377f7vs73d6h240';

function triggerDeploy() {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({ clearCache: 'clear' });
    const options = {
      hostname: 'api.render.com',
      path: '/v1/services/' + SERVICE + '/deploys',
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + TOKEN,
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data)
      }
    };
    const req = https.request(options, res => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try {
          const result = JSON.parse(body);
          console.log('Deploy triggered!');
          console.log('ID:', result.id);
          console.log('Status:', result.status);
          resolve(result);
        } catch(e) {
          console.log('Response:', body);
          reject(e);
        }
      });
    });
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

async function main() {
  console.log('Triggering Render Deploy...');
  try {
    await triggerDeploy();
    console.log('Check: https://dashboard.render.com/web/' + SERVICE);
    console.log('Site: https://case-processor.onrender.com');
  } catch(e) {
    console.error('Error:', e.message);
  }
}

main();
