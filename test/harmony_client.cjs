// Executes the actual transport source against an HTTP double. This is not an ArkTS build.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { stripTypeScriptTypes } = require('node:module');
let source = fs.readFileSync(path.join(__dirname, '../harmony/entry/src/main/ets/service/PetApi.ets'), 'utf8');
source = source.replace(/^import .*;\r?\n/gm, '').replace('export class PetApi', 'class PetApi');
let queue = [], calls = [], destroyed = 0;
const http = {
  RequestMethod: { GET: 'GET', POST: 'POST', DELETE: 'DELETE' }, HttpDataType: { STRING: 'string' },
  createHttp() {
    return {
      async request(url, options) {
        calls.push({ url, ...options });
        const item = queue.shift();
        if (!item) throw Error('Unexpected network request');
        if (typeof item === 'function') return item();
        if (item instanceof Error) throw item;
        return item;
      },
      destroy() { destroyed++; }
    };
  }
};
const PetApi = vm.runInNewContext(stripTypeScriptTypes(source) + '\nPetApi;', { http });
const response = (data, cookies = '', code = 200) => ({ result: JSON.stringify(data), cookies, responseCode: code });
const bootstrap = () => response({ apiVersion: 1, appVersion: 'test', pets: [{ id: 1 }], sessionCookieName: 'session', maxMessageChars: 2000 });

(async () => {
  const api = new PetApi();
  for (const address of ['http://example.com', 'http://8.8.8.8', 'http://192.168.1.5/path',
    'https://user:password@example.com', 'http://192.168.1.5:99999', 'file:///x']) {
    assert.throws(() => api.configure(address, true), undefined, address);
  }
  assert.throws(() => api.configure('http://192.168.1.5:5003', false));
  api.configure('http://192.168.1.5:5003', true);
  queue.push(bootstrap()); await api.bootstrap();
  queue.push(response({ username: 'alice' }, 'other=ignored; session=signed-value; HttpOnly; Path=/'));
  await api.login('alice', 'password');
  queue.push(response({ messages: [] })); await api.history(1);
  assert.equal(calls.at(-1).header.Cookie, 'session=signed-value');
  assert.equal(calls.at(-1).usingCache, false);

  queue.push(response({ ok: true }, 'session=; Max-Age=0; Path=/')); await api.logout();
  assert.equal(calls.at(-1).method, 'POST');
  assert.equal(calls.at(-1).extraData, '{}');
  assert.ok(calls.at(-1).url.endsWith('/logout'));
  queue.push(response({ messages: [] })); await api.history(1);
  assert.equal(calls.at(-1).header.Cookie, '');

  queue.push(response({ username: 'alice' }, 'session=old-session; Path=/')); await api.login('alice', 'password');
  queue.push(response({ error: '请先登录' }, '', 401));
  await assert.rejects(() => api.history(1), /请先登录/);
  queue.push(response({ messages: [] })); await api.history(1);
  assert.equal(calls.at(-1).header.Cookie, '');

  queue.push(new Error('network down'));
  await assert.rejects(() => api.history(1), /network down/);
  assert.equal(destroyed, calls.length);

  const request = { petId: 1, message: 'hello', requestId: 'fixed-retry-1234' };
  queue.push(response({ error: 'still running' }, '', 409));
  await assert.rejects(() => api.chat(request), /still running/);
  queue.push(response({ reply: 'hello back' })); await api.chat(request);
  assert.equal(calls.at(-1).extraData, calls.at(-2).extraData);

  let finish;
  queue.push(() => new Promise(resolve => { finish = resolve; }));
  const pending = api.history(1);
  api.configure('https://server.example', false);
  finish(response({ messages: [] }, 'session=stale; Path=/'));
  await assert.rejects(() => pending, /连接已切换/);
  queue.push(bootstrap()); await api.bootstrap();
  assert.equal(calls.at(-1).header.Cookie, '');
  assert.equal(destroyed, calls.length);
  assert.equal(queue.length, 0);
  console.log('PASS: address policy, cookies, logout, expiry, retry identity, stale responses, resource cleanup');
})().catch(error => { console.error(error); process.exitCode = 1; });
