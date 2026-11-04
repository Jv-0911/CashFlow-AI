import { defineConfig } from '@playwright/test';
import { randomUUID } from 'node:crypto';
const run = process.env.CASHFLOW_E2E_RUN_ID ?? randomUUID();
process.env.CASHFLOW_E2E_RUN_ID = run;
const python = process.env.CASHFLOW_TEST_PYTHON ?? 'python';
export default defineConfig({
  testDir:'./e2e', fullyParallel:false, workers:1, timeout:60000,
  use:{baseURL:'http://127.0.0.1:8766',channel:process.env.CASHFLOW_BROWSER_CHANNEL || undefined,trace:'retain-on-failure'},
  webServer:[
    {command:`${python} -m tests.e2e.serve --port 8766 --run-id ${run} --authenticated`,cwd:'..',url:'http://127.0.0.1:8766/health',reuseExistingServer:false,timeout:120000},
    {command:`${python} -m tests.e2e.serve --port 8767 --run-id ${run}`,cwd:'..',url:'http://127.0.0.1:8767/health',reuseExistingServer:false,timeout:120000},
  ],
});
