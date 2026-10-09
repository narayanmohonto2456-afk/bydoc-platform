const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function loadApi(fetch) {
  const temporaryDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'bydoc-auth-test-'));
  let output;
  try {
    execFileSync(process.execPath, [
      path.resolve(__dirname, '../node_modules/typescript/bin/tsc'),
      path.resolve(__dirname, '../lib/api.ts'),
      '--ignoreConfig',
      '--target', 'es2022', '--module', 'commonjs', '--lib', 'es2022,dom', '--types', 'node',
      '--skipLibCheck', '--outDir', temporaryDirectory,
    ], { cwd: path.resolve(__dirname, '..'), stdio: 'pipe' });
    output = fs.readFileSync(path.join(temporaryDirectory, 'api.js'), 'utf8');
  } finally {
    fs.rmSync(temporaryDirectory, { recursive: true, force: true });
  }
  const module = { exports: {} };
  vm.runInNewContext(output, {
    module, exports: module.exports, fetch, Headers, process: {
      env: { NEXT_PUBLIC_API_BASE_URL: 'http://api.test/api/v1' },
    },
  });
  return module.exports;
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

test('concurrent expired access requests share one refresh and retry successfully', async () => {
  let accessValid = false;
  let refreshCount = 0;
  const calls = [];
  const fetch = async (url) => {
    const pathname = new URL(url).pathname;
    calls.push(pathname);
    if (pathname === '/api/v1/auth/csrf/') return json({ csrf_token: 'test-csrf' });
    if (pathname === '/api/v1/auth/token/refresh/') {
      refreshCount += 1;
      if (refreshCount > 1) return json({ detail: 'Refresh replay' }, 401);
      accessValid = true;
      return json({ user: { id: 'test-user' }, csrf_token: 'test-csrf' });
    }
    if (pathname === '/api/v1/auth/me/') {
      return accessValid ? json({ id: 'test-user' }) : json({ detail: 'Expired' }, 401);
    }
    return accessValid ? json({ path: pathname }) : json({ detail: 'Expired' }, 401);
  };
  const { apiRequest } = loadApi(fetch);
  const paths = ['/private/profile/', '/private/phone/', '/private/google/'];
  const responses = await Promise.all(paths.map(pathname => apiRequest(pathname)));
  assert.deepEqual(responses.map(value => value.path), paths.map(pathname => `/api/v1${pathname}`));
  assert.equal(refreshCount, 1);
  assert.equal(calls.filter(pathname => pathname === '/api/v1/auth/token/refresh/').length, 1);
});
