const https = require('https');

const data = JSON.stringify({clearCache: 'clear'});
const options = {
  hostname: 'api.render.com',
  path: '/v1/services/srv-d916j377f7vs73d6h240/deploys',
  method: 'POST',
  headers: {
    'Authorization': 'Bearer rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt',
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(data)
  }
};

const req = https.request(options, (res) => {
  let body = '';
  res.on('data', (chunk) => { body += chunk; });
  res.on('end', () => {
    try {
      const result = JSON.parse(body);
      console.log('Success!');
      console.log('Deploy ID:', result.id);
      console.log('Status:', result.status);
      console.log('Created:', result.createdAt);
    } catch (e) {
      console.log('Response:', body);
    }
  });
});

req.on('error', (e) => {
  console.error('Error:', e.message);
});

req.write(data);
req.end();
console.log('Deploy request sent. Check https://dashboard.render.com for progress');
