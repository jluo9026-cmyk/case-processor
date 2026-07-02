const https = require('https');

function getUrl(url) {
  return new Promise((resolve, reject) => {
    https.get(url, res => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => resolve(body));
    }).on('error', reject);
  });
}

async function main() {
  // Check if new code is deployed
  const js = await getUrl('https://case-processor.onrender.com/tools/report_generate/report_generate.js');
  if (js.includes('openOcrDetails')) {
    console.log('NEW VERSION DEPLOYED - openOcrDetails found');
  } else {
    console.log('OLD VERSION - openOcrDetails not found, triggering deploy...');
    // Trigger deploy
    const data = JSON.stringify({ clearCache: 'clear' });
    const result = await new Promise((resolve, reject) => {
      const req = https.request({
        hostname: 'api.render.com',
        path: '/v1/services/srv-d916j377f7vs73d6h240/deploys',
        method: 'POST',
        headers: {
          'Authorization': 'Bearer rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt',
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(data)
        }
      }, res => {
        let b = '';
        res.on('data', c => b += c);
        res.on('end', () => resolve(JSON.parse(b)));
      });
      req.on('error', reject);
      req.write(data);
      req.end();
    });
    console.log('Deploy triggered!');
    console.log('ID:', result.id);
    console.log('Status:', result.status);
    console.log('Wait 2-3 min, then check https://case-processor.onrender.com');
  }
}

main();
