import { test, expect, type Page, type BrowserContext } from '@playwright/test';

// Keep a disposable fixture session in memory so this larger suite does not
// exceed the application's real five-login-per-minute limit.
let authenticatedCookies: Awaited<ReturnType<BrowserContext['cookies']>> | undefined;

async function signIn(page:Page) {
  if (authenticatedCookies) {
    await page.context().addCookies(authenticatedCookies);
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/dashboard$/);
    return;
  }
  await page.goto('/login');
  await page.getByLabel('Email Address').fill('owner@example.test');
  await page.locator('#password-input').fill(`e2e-only-${process.env.CASHFLOW_E2E_RUN_ID}`);
  await page.locator('form button[type=submit]').click();
  await expect(page).toHaveURL(/\/dashboard$/);
  authenticatedCookies = await page.context().cookies();
}
test('Member 4 screens use the existing engines and preserve customization', async ({page}) => {
  const errors:string[]=[]; page.on('pageerror',error=>errors.push(error.message));
  await signIn(page);
  for(const [route,heading] of [['forecast','Cash-Flow Forecast'],['rescue','AI Rescue Suite'],['scenarios','Scenario Simulation'],['analytics','Analytics'],['settings','Settings']]) {
    await page.goto(`/dashboard/${route}`);
    await expect(page.locator('.dashboard-main')).toBeVisible();
    await expect(page.getByText(heading,{exact:false}).first()).toBeVisible();
    await expect(page.locator('.rescue-error-card, .scenario-error-card, .analytics-error-card')).toHaveCount(0);
  }
  await page.goto('/dashboard/scenarios');
  await expect(page.getByRole('heading',{name:'Scenario Simulation',exact:true})).toBeVisible();
  await expect(page.locator('.scenario-comparison-card')).toBeVisible();
  const changed=page.waitForResponse(r=>r.url().endsWith('/api/v1/scenario') && r.request().method()==='POST');
  await page.getByRole('button',{name:/Vendor Cost Hike/}).click();
  expect((await changed).status()).toBe(200);
  await expect(page.locator('.scenario-comparison-card')).toBeVisible();
  await page.getByTestId('customize-dashboard-btn').click();
  await expect(page.getByRole('toolbar',{name:'Dashboard customization toolbar'})).toBeVisible();
  await page.getByTestId('save-layout-btn').click();
  await expect(page.getByRole('toolbar',{name:'Dashboard customization toolbar'})).toHaveCount(0);
  await page.screenshot({path:'test-results/member4-desktop.png',fullPage:true});
  expect(errors).toEqual([]);
});
test('proposal, explicit approval, invoice and fresh verification through the existing ledger drawer', async ({page}) => {
  await signIn(page);
  await page.goto('/dashboard/payments');
  await page.locator('#recovery-source').selectOption('receivable_northstar');
  await page.getByRole('button',{name:'Record proposal',exact:true}).click();
  const inspect=()=>page.locator('.inspect-btn').first().click();
  await inspect();
  await expect(page.getByRole('button',{name:'Record human approval'})).toBeDisabled();
  await page.getByRole('checkbox',{name:/I approve/}).check();
  await page.getByRole('button',{name:'Record human approval'}).click();
  await inspect(); await page.getByRole('button',{name:'Create invoice draft'}).click();
  await inspect(); await page.getByRole('button',{name:'Send approved invoice'}).click();
  await inspect(); await page.getByRole('button',{name:'Verify with PayPal'}).click();
  await expect(page.locator('.ledger-row')).toContainText('Pending Verification');
  await inspect(); await page.getByRole('button',{name:'Verify with PayPal'}).click();
  await expect(page.locator('.ledger-row')).toContainText('Verified Completed');
  const data=await (await page.request.get('/api/v1/ledger')).json();
  expect(data.recovered_cash).toEqual([{currency:'USD',amount_cents:320000}]);
  expect(data.entries).toHaveLength(1);
});
test('local storage cannot bypass login; outages show errors without fixture payments', async ({page}) => {
  await page.goto('/login');
  await page.evaluate(()=>localStorage.setItem('cashflow_ai_user',JSON.stringify({name:'Forged',email:'forged@example.test'})));
  await page.goto('/dashboard/payments');
  await expect(page).toHaveURL(/\/login$/);
  await signIn(page);
  await page.route('**/api/v1/ledger', route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{message:'Ledger temporarily unavailable'}})}));
  await page.goto('/dashboard/payments');
  await expect(page.getByText('Ledger temporarily unavailable')).toBeVisible();
  await expect(page.locator('.ledger-row')).toHaveCount(0);
});
test('read-only demo works without credentials and private payments remain inaccessible', async ({page}) => {
  await page.goto('http://127.0.0.1:8767/dashboard/forecast');
  await expect(page.locator('.dashboard-main')).toBeVisible();
  await page.goto('http://127.0.0.1:8767/dashboard/payments');
  await expect(page.getByText(/administrator access is required for the private payment ledger/).first()).toBeVisible();
  await expect(page.getByRole('button',{name:'Record proposal'})).toHaveCount(0);
  expect((await page.request.get('http://127.0.0.1:8767/api/v1/ledger')).status()).toBe(401);
});

test('Member 4 mobile layout keeps navigation and forecast usable', async ({page}) => {
  await page.setViewportSize({width:390,height:844});
  await signIn(page);
  await page.getByRole('button',{name:'Toggle Navigation Menu'}).click();
  await page.getByRole('link',{name:'Forecast',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Cash-Flow Forecast'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2)).toBe(true);
  await page.screenshot({path:'test-results/member4-mobile.png',fullPage:true});
});

test('reset to baseline clears scenario changes instead of retaining a receipt delay', async ({page}) => {
  await signIn(page);
  await page.goto('/dashboard/scenarios');
  await expect(page.locator('.scenario-comparison-card')).toBeVisible();
  const reset = page.waitForResponse(r=>r.url().endsWith('/api/v1/scenario') && r.request().method()==='POST');
  await page.getByRole('button',{name:'Reset to Baseline',exact:true}).click();
  const response = await reset;
  expect(response.request().postDataJSON().modifiers.delayed_receivables_days).toBe(0);
  expect((await response.json()).comparison.net_variance_cents).toBe(0);
});

test('reconciliation warning remains visible after the ledger refresh', async ({page}) => {
  await signIn(page);
  await page.goto('/dashboard/payments');
  await page.route('**/api/v1/payments/reconcile', route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({results:[{entry_id:'fixture',status:'UNRESOLVED',error_code:'PAYPAL_TIMEOUT'}]})}));
  const refreshed = page.waitForResponse(r=>r.url().endsWith('/api/v1/ledger'));
  await page.getByRole('button',{name:'Reconcile uncertain invoices'}).click();
  await refreshed;
  await expect(page.getByText('Some invoices remain unresolved. Refresh their status before retrying.')).toBeVisible();
});
