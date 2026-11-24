// Requires Playwright and a running `python -m tests.browser_fixture`.
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const browser = await chromium.launch({headless:true, ...(process.env.BROWSER_EXECUTABLE ? {executablePath:process.env.BROWSER_EXECUTABLE} : {})});
  const page = await browser.newPage({viewport:{width:1440,height:1100}});
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  page.on('dialog', d => d.accept());
  try {
    await page.goto('http://127.0.0.1:8012');
    await page.getByText('Working RDF connected', {exact:false}).waitFor();
    await page.getByRole('button',{name:'Load example'}).click();
    await page.getByRole('button',{name:'Extract & match'}).click();
    await page.locator('.entity-card').nth(1).waitFor();
    let existing = page.locator('.entity-card').nth(0);
    await existing.getByRole('button',{name:'Confirm this match'}).click();
    await existing.getByText('Now editing on Q1', {exact:true}).waitFor();
    const width = existing.locator('.claim').filter({has:page.locator('.prop-title').filter({hasText:'width'})});
    await width.getByLabel('Value',{exact:true}).fill('81');
    await existing.getByRole('button',{name:'Search and confirm value entity'}).click();
    await existing.getByRole('button',{name:'Confirm Maker (Q2)'}).click();
    await existing.getByRole('button',{name:'Apply changes to QLever'}).click();
    await page.getByText('✓ Changes applied and verified in QLever · Q1',{exact:true}).waitFor();
    await page.locator('.entity-card').nth(0).getByRole('button',{name:'Query saved values'}).click();
    await page.locator('#verify-results table').waitFor();
    assert((await page.locator('#verify-results').textContent()).includes('81'));

    let fresh = page.locator('.entity-card').nth(1);
    await fresh.getByRole('button',{name:'Confirm this is a new entity'}).click();
    await fresh.getByRole('button',{name:'+ Add property'}).click();
    await fresh.locator('.add-property-row select').selectOption('price');
    fresh = page.locator('.entity-card').nth(1);
    const price = fresh.locator('.claim').filter({has:page.locator('.prop-title').filter({hasText:'price'})});
    await price.getByLabel('Value',{exact:true}).fill('500');
    await fresh.getByRole('button',{name:'Create entity in QLever'}).click();
    await fresh.getByText('choose a unit from DKK', {exact:false}).waitFor();
    await price.getByLabel('Currency (required when price entered)').selectOption('EUR');
    await fresh.getByRole('button',{name:'Create entity in QLever'}).click();
    await page.locator('.entity-card').nth(1).getByText('Changes applied and verified in QLever', {exact:false}).waitFor();
    await page.locator('.entity-card').nth(1).getByRole('button',{name:'Query saved values'}).click();
    await page.waitForFunction(() => document.querySelector('#verify-results')?.textContent.includes('500'));
    assert.equal(errors.length,0,errors.join('\n'));
    if (process.env.SMOKE_SCREENSHOT) await page.screenshot({path:process.env.SMOKE_SCREENSHOT,fullPage:true});
    console.log('Browser smoke passed: confirmation, replacement, value entity matching, new entity, + property, currency enforcement, save and RDF query.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
