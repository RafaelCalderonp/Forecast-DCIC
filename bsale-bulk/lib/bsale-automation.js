const { chromium } = require('playwright-core');

let browserPromise = null;

function escapeRegex(str) {
  return String(str).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

async function getBrowser(cfg) {
  if (!browserPromise) {
    browserPromise = chromium.connectOverCDP(cfg.cdpUrl).then((browser) => {
      browser.on('disconnected', () => {
        browserPromise = null;
      });
      return browser;
    }).catch((err) => {
      browserPromise = null;
      throw err;
    });
  }
  return browserPromise;
}

async function getBsalePage(cfg) {
  const browser = await getBrowser(cfg);
  const contexts = browser.contexts();
  const needle = cfg.bsaleUrlContains.toLowerCase();

  for (const ctx of contexts) {
    for (const pg of ctx.pages()) {
      if (pg.url().toLowerCase().includes(needle)) {
        return pg;
      }
    }
  }

  // fallback: last page of the last context (best-effort)
  for (let i = contexts.length - 1; i >= 0; i--) {
    const pages = contexts[i].pages();
    if (pages.length) return pages[pages.length - 1];
  }

  throw new Error(
    'No se encontro ninguna pestana abierta en Chrome (puerto de depuracion). ' +
    'Verifica que Chrome este corriendo con --remote-debugging-port y que Bsale este abierto.'
  );
}

async function checkStatus(cfg) {
  try {
    const browser = await getBrowser(cfg);
    const contexts = browser.contexts();
    const allPages = contexts.flatMap((c) => c.pages());
    let bsalePage = null;
    const needle = cfg.bsaleUrlContains.toLowerCase();
    for (const pg of allPages) {
      if (pg.url().toLowerCase().includes(needle)) {
        bsalePage = pg;
        break;
      }
    }
    return {
      connected: true,
      totalTabs: allPages.length,
      bsaleFound: !!bsalePage,
      bsaleUrl: bsalePage ? bsalePage.url() : null,
      bsaleTitle: bsalePage ? await bsalePage.title().catch(() => null) : null,
    };
  } catch (err) {
    return { connected: false, error: err.message };
  }
}

async function processRow(cfg, sku, cantidad) {
  const page = await getBsalePage(cfg);
  const { selectors, timing } = cfg;

  try {
    const searchInput = page.getByPlaceholder(selectors.searchInputPlaceholder).first();
    await searchInput.click({ timeout: 5000 });
    await searchInput.fill('');
    await searchInput.type(String(sku), { delay: timing.typeDelayMs });
    await page.waitForTimeout(timing.afterTypeMs);

    const skuRegex = new RegExp('SKU:\\s*' + escapeRegex(sku), 'i');
    const candidateLocators = [
      page.getByRole('option', { name: skuRegex }).first(),
      page.getByText(skuRegex).first(),
    ];

    let clicked = false;
    for (const loc of candidateLocators) {
      const count = await loc.count().catch(() => 0);
      if (count > 0) {
        await loc.click({ timeout: 3000 });
        clicked = true;
        break;
      }
    }

    if (!clicked) {
      throw new Error(`No aparecio ninguna sugerencia para el SKU "${sku}" (revisar SKU o selectores).`);
    }

    await page.waitForTimeout(timing.afterSelectMs);

    const cantidadInput = page.getByPlaceholder(selectors.cantidadPlaceholder).first();
    await cantidadInput.click({ timeout: 3000 });
    await cantidadInput.fill('');
    await cantidadInput.type(String(cantidad), { delay: timing.typeDelayMs });

    const agregarBtn = page.getByRole('button', { name: new RegExp(selectors.agregarButtonText, 'i') }).first();
    await agregarBtn.click({ timeout: 3000 });
    await page.waitForTimeout(timing.afterAgregarMs);

    return { ok: true };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

module.exports = { checkStatus, processRow };
