/* Behavior checks: busy/expired cues, manual priority, settings, retry, race. */
const assert = require('node:assert/strict');
const { Controller } = require('../static/js/den/pet-care-runtime.js');
global.document = new EventTarget(); document.hidden = false;
global.localStorage = { getItem: () => null };
const settle = () => new Promise(resolve => setImmediate(resolve));

(async () => {
  let now = 1000000, pet = 3, available = false, comfort = 0, cancelled = 0;
  let emotion = true, fail = true, claimResolve, noticeCount = 0;
  const fetcher = async path => {
    if (fail) throw Error('temporary offline');
    const data = path.includes('/claim')
      ? await new Promise(resolve => { claimResolve = resolve; })
      : path.includes('/pet-calls') ? { enabled: false, clips: [] }
      : { signedIn: true, settings: { emotion } };
    return { ok: true, json: async () => ({ scope: 'account-a', petId: pet, ...data }) };
  };
  const controller = new Controller({scope: 'account-a', pet: () => ({ id: pet }),
    now: () => now, fetcher, available: () => available, noticeAvailable: () => false,
    comfort: async () => { comfort++; }, cancelComfort: () => { cancelled++; }});
  controller.nudge = () => { noticeCount++; };
  try {
    await settle(); assert.equal(controller.ready, false);
    fail = false; now += 16000; await controller.tick();
    assert.equal(controller.ready, true, 'recover without reloading after offline startup');
    controller.handle({ emotion: { action: 'company' } });
    await controller.tick(); assert.equal(comfort, 0, 'do not interrupt existing activity');
    now += 21000; available = true; await controller.tick();
    assert.equal(comfort, 0, 'expired sadness cue must not act later');
    controller.handle({ emotion: { action: 'company' } });
    controller.manual(); await controller.tick(); assert.equal(comfort, 0);
    controller.handle({ emotion: { action: 'company' } });
    await controller.tick(); assert.equal(comfort, 1);
    controller.handle({ emotion: { action: 'company' } });
    await controller.tick(); assert.equal(comfort, 1, 'cooldown avoids repeated approach');
    const before = cancelled;
    controller.handle({ emotion: { action: 'space' } });
    assert.equal(cancelled, before + 1, 'explicit space wins during cooldown');
    emotion = false; await controller.refresh();
    assert.equal(cancelled, before + 2, 'turning off comfort cancels owned action');
    now += 121000; controller.handle({ emotion: { action: 'company' } });
    assert.equal(controller.pending, null);

    // Refresh cannot discard a reminder already claimed from the server.
    controller.a.noticeAvailable = () => true;
    const polling = controller.poll(); await settle();
    await controller.refresh(); assert.equal(controller.refreshRequested, true);
    claimResolve({ notice: { id: 'one', message: '明天面试，加油' } });
    await polling; await settle(); assert.equal(noticeCount, 1);
    assert.equal(controller.ready, true);

    // An account-scope mismatch must never populate current settings.
    controller.fetcher = async () => ({ok:true,json:async()=>({scope:'account-b'})});
    await controller.refresh(); assert.equal(controller.ready, false);
    console.log('PASS: offline recovery, deferred expiry, manual priority, cooldown, space, off switch, claim/refresh race, account isolation');
  } finally { controller.dispose(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
