import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';

test('Vercel routing fails closed without a valid backend and proxies API before SPA routes', () => {
  for(const value of ['', 'http://api.example.test','https://user:pass@api.example.test','https://api.example.test/path','https://localhost']) {
    const result=spawnSync(process.execPath,['--input-type=module','-e',"await import('./vercel.ts')"],{env:{...process.env,CASHFLOW_BACKEND_URL:value},encoding:'utf8'});
    assert.notEqual(result.status,0);
  }
  const result=spawnSync(process.execPath,['--input-type=module','-e',"console.log(JSON.stringify((await import('./vercel.ts')).config))"],{env:{...process.env,CASHFLOW_BACKEND_URL:'https://api.example.test'},encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
  const config=JSON.parse(result.stdout);
  assert.equal(config.rewrites[0].source,'/api/:path*');
  assert.equal(config.rewrites[0].destination,'https://api.example.test/api/:path*');
  assert.ok(config.headers[0].headers.some((h:{key:string;value:string})=>h.key==='Cache-Control'&&h.value==='no-store'));
});
