const path = require('path');
const fs = require('fs');
const express = require('express');
const { checkStatus, processRow } = require('./lib/bsale-automation');

const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8'));

const app = express();
app.use(express.json({ limit: '2mb' }));
app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/status', async (req, res) => {
  const status = await checkStatus(cfg);
  res.json({ ...status, batchSize: cfg.batchSize });
});

app.post('/api/send', async (req, res) => {
  const rows = Array.isArray(req.body.rows) ? req.body.rows : [];

  res.writeHead(200, {
    'Content-Type': 'application/x-ndjson; charset=utf-8',
    'Transfer-Encoding': 'chunked',
    'Cache-Control': 'no-cache',
  });

  for (const row of rows) {
    let result;
    try {
      result = await processRow(cfg, row.sku, row.cantidad);
    } catch (err) {
      result = { ok: false, error: err.message };
    }
    res.write(JSON.stringify({ id: row.id, ...result }) + '\n');
  }

  res.end();
});

const PORT = process.env.PORT || 4127;
app.listen(PORT, () => {
  console.log(`Bsale bulk tool escuchando en http://localhost:${PORT}`);
  console.log(`Conectando a Chrome via CDP en ${cfg.cdpUrl}`);
});
