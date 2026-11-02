// Execute collection JavaScript with a fake pm object. No HTTP or Postman service.
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { test } = require('node:test');
const vm = require('node:vm');
const collection = require('../../app/payments/postman/paypal-sandbox.collection.json');

function execute(index, overrides = {}, { response, url, phase = 'prerequest' } = {}) {
  const values = new Map(Object.entries({
    PAYPAL_MODE: 'sandbox', access_token: randomUUID(),
    ledger_approval_confirmed: 'true', approval_event_id: 'evt_demo', ledger_entry_id: 'entry_demo',
    invoice_id: 'INV2-DEMO-0000-0000-0001', approved_invoice_id: 'INV2-DEMO-0000-0000-0001',
    invoice_number: 'CFDEMO', SANDBOX_PAYER_EMAIL: 'payer@example.test',
    create_request_id: randomUUID(), send_request_id: randomUUID(), ...overrides,
  }));
  let skipped = false;
  const pm = {
    variables: {
      get: key => values.get(key), set: (key, value) => values.set(key, value), unset: key => values.delete(key),
      replaceIn: value => value.replace(/\{\{([^}]+)\}\}/g, (_, key) => values.get(key) ?? ''),
    },
    request: { url: { toString: () => url ?? collection.item[index].request.url } },
    execution: { skipRequest: () => { skipped = true; } },
    test: (_, fn) => fn(),
    response: response && { code: response.code, json: () => response.body,
      to: { have: { status: expected => assert.equal(response.code, expected) } } },
  };
  let error;
  const script = collection.item[index].event.find(e => e.listen === phase).script.exec.join('\n');
  try { vm.runInNewContext(script, { pm }, { timeout: 1000 }); } catch (caught) { error = caught; }
  return { skipped, error, values };
}

test('valid diagnostic inputs pass all pre-request guards', () => {
  for (let index = 0; index < 5; index++) {
    const result = execute(index);
    assert.equal(result.skipped, false);
    assert.equal(result.error, undefined);
  }
});

test('unsafe mode and destinations explicitly skip every request', () => {
  for (let index = 0; index < 5; index++) {
    for (const result of [execute(index, { PAYPAL_MODE: 'live' }),
      execute(index, {}, { url: 'https://api-m.paypal.com/v2/invoicing/invoices' }),
      execute(index, {}, { url: 'https://api-m.sandbox.paypal.com.evil.test/' }),
      execute(index, {}, { url: 'https://api-m.sandbox.paypal.com/v1/other' })]) {
      assert.equal(result.skipped, true);
      assert.ok(result.error);
    }
  }
});

test('create and send require approval attestation and well-formed stable keys', () => {
  for (const index of [1, 2]) {
    for (const overrides of [{ ledger_approval_confirmed: 'false' }, { approval_event_id: '' },
      { ledger_entry_id: '' }, { create_request_id: 'x', send_request_id: 'x' }]) {
      assert.equal(execute(index, overrides).skipped, true);
    }
  }
  assert.equal(execute(2, { approved_invoice_id: 'INV2-DEMO-0000-0000-9999' }).skipped, true);
});

test('identifier and body-variable injection is rejected', () => {
  for (const value of ['../x', 'INV2-DEMO-0000-0000-0001?x=1', 'https://example.test']) {
    for (const index of [2, 3]) assert.equal(execute(index, { invoice_id: value }).skipped, true);
  }
  for (const value of ['payer"@example.test', 'payer\\@example.test', 'payer\n@example.test']) {
    assert.equal(execute(1, { SANDBOX_PAYER_EMAIL: value }).skipped, true);
  }
});

test('OAuth clears stale local tokens and failed responses cannot retain one', () => {
  assert.equal(execute(0).values.has('access_token'), false);
  for (const response of [{ code: 401, body: {} }, { code: 200, body: {} },
    { code: 200, body: { access_token: randomUUID(), token_type: 'Bearer', expires_in: 1 } }]) {
    const result = execute(0, {}, { response, phase: 'test' });
    assert.ok(result.error);
    assert.equal(result.values.has('access_token'), false);
  }
});

test('valid OAuth token stays local and subsequent requests require it', () => {
  const token = randomUUID();
  const result = execute(0, {}, { phase: 'test', response: {
    code: 200, body: { access_token: token, token_type: 'Bearer', expires_in: 3600 },
  } });
  assert.equal(result.error, undefined);
  assert.equal(result.values.get('access_token'), token);
  for (let index = 1; index < 5; index++) assert.equal(execute(index, { access_token: '' }).skipped, true);
});

test('TLS verification is enabled and redirects and cookie jar are disabled', () => {
  assert.deepEqual(collection.protocolProfileBehavior, {
    strictSSL: true, followRedirects: false, disableCookies: true,
  });
});
