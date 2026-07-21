const STORAGE_KEY = 'bsaleBulkQueue';
let BATCH_SIZE = 20;
let queue = loadQueue();
let sending = false;
let nextId = queue.reduce((max, r) => Math.max(max, r.id), 0) + 1;

const el = {
  statusDot: document.getElementById('statusDot'),
  statusText: document.getElementById('statusText'),
  btnCheckStatus: document.getElementById('btnCheckStatus'),
  skuInput: document.getElementById('skuInput'),
  cantidadInput: document.getElementById('cantidadInput'),
  btnCargar: document.getElementById('btnCargar'),
  loadCounters: document.getElementById('loadCounters'),
  tableWrap: document.getElementById('tableWrap'),
  btnEnviar: document.getElementById('btnEnviar'),
  btnValidadas: document.getElementById('btnValidadas'),
  btnLimpiar: document.getElementById('btnLimpiar'),
  queueCounters: document.getElementById('queueCounters'),
  logPanel: document.getElementById('logPanel'),
};

function loadQueue() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveQueue() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
}

function log(message, kind) {
  const line = document.createElement('p');
  line.className = 'line' + (kind ? ' ' + kind : '');
  const ts = new Date().toLocaleTimeString('es-CL');
  line.textContent = `[${ts}] ${message}`;
  el.logPanel.appendChild(line);
  el.logPanel.scrollTop = el.logPanel.scrollHeight;
}

function currentBatch() {
  return queue.slice(0, BATCH_SIZE);
}

function render() {
  const batch = currentBatch();
  el.queueCounters.textContent = `En cola: ${queue.length} | En este lote: ${batch.length}`;

  if (!batch.length) {
    el.tableWrap.innerHTML = '<p class="empty">Aún no hay filas cargadas.</p>';
    return;
  }

  const rows = batch.map((r, i) => `
    <tr>
      <td class="num">${i + 1}</td>
      <td>${escapeHtml(r.sku)}</td>
      <td>${escapeHtml(r.cantidad)}</td>
      <td><span class="badge ${r.status}">${labelForStatus(r)}</span></td>
      <td class="ticket"><input type="checkbox" data-id="${r.id}" ${r.ticket ? 'checked' : ''} /></td>
    </tr>
  `).join('');

  el.tableWrap.innerHTML = `
    <table>
      <thead>
        <tr><th>#</th><th>SKU</th><th>Cantidad</th><th>Estado</th><th>Ticket</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;

  el.tableWrap.querySelectorAll('input[type=checkbox]').forEach((cb) => {
    cb.addEventListener('change', () => {
      const id = Number(cb.dataset.id);
      const row = queue.find((r) => r.id === id);
      if (row) {
        row.ticket = cb.checked;
        saveQueue();
      }
    });
  });
}

function labelForStatus(r) {
  if (r.status === 'error') return r.error ? `Error: ${r.error}` : 'Error';
  if (r.status === 'enviado') return 'Enviado';
  return 'Pendiente';
}

function escapeHtml(v) {
  return String(v).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function parseLines(text) {
  return text.split(/\r?\n/).map((s) => s.trim()).filter((s) => s.length > 0);
}

el.btnCargar.addEventListener('click', () => {
  const skus = parseLines(el.skuInput.value);
  const cantidades = parseLines(el.cantidadInput.value);

  if (!skus.length) {
    log('No hay SKUs para cargar.', 'err');
    return;
  }
  if (skus.length !== cantidades.length) {
    log(`Aviso: ${skus.length} SKUs vs ${cantidades.length} cantidades. Se emparejarán solo las primeras ${Math.min(skus.length, cantidades.length)}.`, 'err');
  }

  const n = Math.min(skus.length, cantidades.length);
  for (let i = 0; i < n; i++) {
    queue.push({ id: nextId++, sku: skus[i], cantidad: cantidades[i], status: 'pendiente', ticket: false, error: null });
  }
  saveQueue();
  el.skuInput.value = '';
  el.cantidadInput.value = '';
  el.loadCounters.textContent = `${n} filas agregadas a la cola.`;
  log(`${n} filas agregadas a la cola (total en cola: ${queue.length}).`);
  render();
});

el.btnEnviar.addEventListener('click', async () => {
  if (sending) return;
  const batch = currentBatch();
  const toSend = batch.filter((r) => r.status === 'pendiente' || r.status === 'error');

  if (!toSend.length) {
    log('No hay filas pendientes ni con error en este lote para enviar.');
    return;
  }

  sending = true;
  el.btnEnviar.disabled = true;
  log(`Enviando ${toSend.length} filas a Bsale...`);

  try {
    const resp = await fetch('/api/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rows: toSend.map((r) => ({ id: r.id, sku: r.sku, cantidad: r.cantidad })) }),
    });

    if (!resp.ok || !resp.body) {
      throw new Error(`Respuesta HTTP ${resp.status}`);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        handleResult(JSON.parse(line));
      }
    }
    if (buffer.trim()) handleResult(JSON.parse(buffer));
  } catch (err) {
    log(`Error de conexión al enviar: ${err.message}`, 'err');
  } finally {
    sending = false;
    el.btnEnviar.disabled = false;
    saveQueue();
    render();
  }
});

function handleResult(result) {
  const row = queue.find((r) => r.id === result.id);
  if (!row) return;
  if (result.ok) {
    row.status = 'enviado';
    row.error = null;
    log(`Fila SKU ${row.sku} agregada en Bsale.`, 'ok');
  } else {
    row.status = 'error';
    row.error = result.error || 'error desconocido';
    log(`Fila SKU ${row.sku}: ${row.error}`, 'err');
  }
  saveQueue();
  render();
}

el.btnValidadas.addEventListener('click', () => {
  const batch = currentBatch();
  const ticked = batch.filter((r) => r.ticket);
  if (!ticked.length) {
    log('No hay filas marcadas con ticket para validar.');
    return;
  }
  const tickedIds = new Set(ticked.map((r) => r.id));
  queue = queue.filter((r) => !tickedIds.has(r.id));
  saveQueue();
  log(`${ticked.length} filas validadas y quitadas de la cola (quedan ${queue.length}).`);
  render();
});

el.btnLimpiar.addEventListener('click', () => {
  if (!confirm('¿Vaciar toda la cola? Esta acción no se puede deshacer.')) return;
  queue = [];
  saveQueue();
  log('Cola vaciada.');
  render();
});

el.btnCheckStatus.addEventListener('click', checkStatus);

async function checkStatus() {
  el.statusText.textContent = 'Verificando...';
  el.statusDot.className = 'status-dot';
  try {
    const resp = await fetch('/api/status');
    const data = await resp.json();
    BATCH_SIZE = data.batchSize || BATCH_SIZE;
    if (data.connected && data.bsaleFound) {
      el.statusDot.className = 'status-dot ok';
      el.statusText.textContent = `Conectado. Pestaña Bsale: ${data.bsaleTitle || data.bsaleUrl}`;
    } else if (data.connected) {
      el.statusDot.className = 'status-dot err';
      el.statusText.textContent = `Conectado a Chrome (${data.totalTabs} pestañas) pero no se encontró una pestaña de Bsale.`;
    } else {
      el.statusDot.className = 'status-dot err';
      el.statusText.textContent = `Sin conexión a Chrome: ${data.error || 'desconocido'}`;
    }
  } catch (err) {
    el.statusDot.className = 'status-dot err';
    el.statusText.textContent = `Error al verificar: ${err.message}`;
  }
}

render();
checkStatus();
