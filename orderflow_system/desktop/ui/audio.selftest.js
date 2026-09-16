/* audio.selftest.js — the trade-audio rules, pinned without a browser.
 *
 * The value of this module is the DECISION: the master switch, the size threshold, the two-tone
 * "hard" variant and the overlap attenuation are arithmetic, and a wrong one of those is either
 * silence where a trader expected a sound or a machine-gun where they expected one tick.
 * `node desktop/ui/audio.selftest.js` prints "audio selftest: N ok, M failed" and exits non-zero
 * on any failure, so the Python suite gates on it.
 */
'use strict';

const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/audio.js', 'utf8');

let ok = 0;
const failures = [];
function check(name, pass, detail) {
    if (pass) { ok += 1; return; }
    failures.push(name + (detail ? ' — ' + detail : ''));
}

/* A fake Audio element: records volume/play calls, can be made to reject like a dead device. */
function makeAudio() {
    const Ctor = function (source) {
        this.src = source;
        this.volume = 1;
        this.currentTime = 0;
        this.plays = 0;
        Ctor.instances.push(this);
    };
    Ctor.instances = [];
    Ctor.failNext = false;
    Ctor.prototype.play = function () {
        this.plays += 1;
        if (Ctor.failNext) { Ctor.failNext = false; return Promise.reject(new Error('device busy')); }
        return Promise.resolve();
    };
    return Ctor;
}

function boot(audioCtor) {
    const doc = {
        body: { id: 'body' },
        addEventListener() {},
        dispatchEvent(ev) { doc.events.push(ev); return true; },
        events: [],
    };
    const win = { toast() {} };
    const AudioCtor = audioCtor || makeAudio();
    new Function('window', 'document', 'setInterval', 'Audio', 'CustomEvent', src)(
        win, doc, () => 0, AudioCtor, function (type, init) { return { type, detail: init && init.detail }; });
    return { A: win.OFAPAUDIO, doc, AudioCtor };
}

const t = (size, side, symbol) => ({ size, side, side_, symbol: symbol || 'BTCUSDT', side_: side });

/* ── the decision ─────────────────────────────────────────────────────────── */

{
    const { A } = boot();

    check('silent until the master switch is on',
        A.decide({ size: 100, side: 'buy' }, { cfg: A.DEFAULTS, now: 1000, mem: {} }) === null);

    const on = Object.assign({}, A.DEFAULTS, { enabled: true });

    check('every print plays when min_size is 0 and hard is off',
        (A.decide({ size: 0.001, side: 'buy' }, { cfg: Object.assign({}, on, { hard_enabled: false }),
            now: 1000, mem: {} }) || {}).name === 'buy');

    check('the side picks the sample: buy → buy, sell → sell',
        A.decide({ size: 1, side: 'buy' }, { cfg: on, now: 1, mem: {} }).name === 'buy' &&
        A.decide({ size: 1, side: 'sell' }, { cfg: on, now: 1, mem: {} }).name === 'sell');

    check('a side that is neither plays the sell sample (never a crash)',
        A.decide({ size: 1, side: 'SELL' }, { cfg: on, now: 1, mem: {} }).name === 'sell');

    const thresh = Object.assign({}, on, { min_size: 1.0, hard_multiple: 3 });
    check('below the threshold is silent',
        A.decide({ size: 0.99, side: 'buy' }, { cfg: thresh, now: 1, mem: {} }) === null);
    check('at the threshold plays the soft sample',
        A.decide({ size: 1.0, side: 'buy' }, { cfg: thresh, now: 1, mem: {} }).name === 'buy');
    check('at 3× the threshold plays the two-tone alert',
        A.decide({ size: 3.0, side: 'buy' }, { cfg: thresh, now: 1, mem: {} }).name === 'buy-hard');
    check('the hard variant can be disabled',
        A.decide({ size: 9.9, side: 'buy' },
            { cfg: Object.assign({}, thresh, { hard_enabled: false }), now: 1, mem: {} }).name === 'buy');
    check('with no threshold configured there is no hard variant',
        A.decide({ size: 99, side: 'buy' }, { cfg: on, now: 1, mem: {} }).name === 'buy');

    check('a zero or negative print is silent (a junk value must never make a sound)',
        A.decide({ size: 0, side: 'buy' }, { cfg: on, now: 1, mem: {} }) === null &&
        A.decide({ size: -5, side: 'buy' }, { cfg: on, now: 1, mem: {} }) === null);

    check('another instrument is ignored when active_symbol_only is set',
        A.decide({ size: 5, side: 'buy', symbol: 'ETHUSDT' },
            { cfg: on, symbol: 'BTCUSDT', now: 1, mem: {} }) === null);
    check('the active symbol plays',
        (A.decide({ size: 5, side: 'buy', symbol: 'BTCUSDT' },
            { cfg: on, symbol: 'BTCUSDT', now: 1, mem: {} }) || {}).name === 'buy');
}

/* ── overlap attenuation ──────────────────────────────────────────────────── */

{
    const { A } = boot();
    const cfg = Object.assign({}, A.DEFAULTS, { enabled: true, min_size: 1, overlap_window_ms: 10, overlap_floor: 0.25 });
    const mem = {};

    const first = A.decide({ size: 5, side: 'buy' }, { cfg, now: 1000, mem });
    const second = A.decide({ size: 5, side: 'buy' }, { cfg, now: 1005, mem });
    const third = A.decide({ size: 5, side: 'buy' }, { cfg, now: 1008, mem });
    const fourth = A.decide({ size: 5, side: 'buy' }, { cfg, now: 1009, mem });
    const later = A.decide({ size: 5, side: 'buy' }, { cfg, now: 1100, mem });

    check('the first trigger is at full gain', first.gain === 1 && first.overlap === 0,
        `gain=${first.gain} overlap=${first.overlap}`);
    check('a retrigger inside the window halves the gain', second.gain === 0.5 && second.overlap === 1,
        `gain=${second.gain} overlap=${second.overlap}`);
    check('the next one halves again', third.gain === 0.25 && third.overlap === 2,
        `gain=${third.gain} overlap=${third.overlap}`);
    check('the gain never falls below the floor', fourth.gain === 0.25 && fourth.overlap === 3,
        `gain=${fourth.gain} overlap=${fourth.overlap}`);
    check('after the window the gain is back to full', later.gain === 1 && later.overlap === 0,
        `gain=${later.gain} overlap=${later.overlap}`);
}

/* ── the player ───────────────────────────────────────────────────────────── */

const asyncChecks = [];

{
    const { A, AudioCtor, doc } = boot();
    A.configure(Object.assign({}, A.DEFAULTS, { enabled: true, volume: 0.5 }));
    A.setSymbol('BTCUSDT');

    const fired = A.onTick({ size: 2, side: 'buy', symbol: 'BTCUSDT' });
    check('a qualifying tick plays the sample', fired && fired.name === 'buy' && A.status().plays === 1);
    check('the element volume is gain × the master volume',
        AudioCtor.instances.length === 1 && Math.abs(AudioCtor.instances[0].volume - 0.5) < 1e-9,
        AudioCtor.instances.length ? String(AudioCtor.instances[0].volume) : 'no element');
    check('the sample URL points at the shipped wav',
        AudioCtor.instances[0].src === A.SAMPLES.buy && /alert-buy\.wav$/.test(A.SAMPLES.buy));

    check('a non-qualifying tick plays nothing',
        A.onTick({ size: 2, side: 'buy', symbol: 'ETHUSDT' }) === null && A.status().plays === 1);

    /* the same element is reused, not re-created (a pool, not a leak) */
    const before = AudioCtor.instances.length;
    A.onTick({ size: 2, side: 'buy', symbol: 'BTCUSDT' });
    check('the player reuses one element per sample', AudioCtor.instances.length === before);

    /* a dead device: the rejection arrives asynchronously, so the counters are checked after it */
    AudioCtor.failNext = true;
    A.onTick({ size: 2, side: 'sell', symbol: 'BTCUSDT' });
    asyncChecks.push(Promise.resolve().then(() => {
        check('a rejected play() is counted', A.status().failures === 1, String(A.status().failures));
        check('the failure is announced as an event', doc.events.some((e) => e.type === 'ofap:audio-failed'));
        check('the failure is reported in status()', /device busy/.test(A.status().last_error), A.status().last_error);
    }));

    /* a device that throws synchronously (no element can be created) */
    const { A: A2, AudioCtor: Audio2 } = boot();
    A2.configure(Object.assign({}, A2.DEFAULTS, { enabled: true }));
    Audio2.prototype.play = function () { throw new Error('no device'); };
    const threw = A2.onTick({ size: 1, side: 'buy', symbol: 'BTCUSDT' });
    check('a synchronous throw is caught and counted',
        threw !== null && A2.status().failures === 1, String(A2.status().failures));
}

/* ── the config clamp ─────────────────────────────────────────────────────── */

{
    const { A } = boot();
    const clamped = A.configure({ enabled: 'yes', volume: 5, min_size: -3, hard_multiple: 0,
                                  overlap_floor: 0, overlap_window_ms: 99999 });
    check('a non-true master switch stays off', clamped.enabled === false);
    check('volume is clamped into 0..1', clamped.volume === 1);
    check('a negative threshold floors at 0', clamped.min_size === 0);
    check('hard_multiple cannot go below 1', clamped.hard_multiple === 1);
    check('the overlap floor cannot go below 0.01', clamped.overlap_floor === 0.01);
    check('the overlap window is capped', clamped.overlap_window_ms === 5000);
    check('a missing config yields the defaults',
        A.configure(undefined).enabled === false && A.configure(undefined).volume === A.DEFAULTS.volume);
}

/* ── the samples are the shipped files ────────────────────────────────────── */

{
    const { A } = boot();
    const expected = ['buy', 'sell', 'buy-hard', 'sell-hard'];
    check('exactly four samples are wired', Object.keys(A.SAMPLES).length === 4 &&
        expected.every((k) => A.SAMPLES[k]));
    const dir = __dirname + '/audio';
    const present = fs.readdirSync(dir).filter((f) => f.endsWith('.wav')).sort();
    check('the wav files exist next to the module', present.length === 4,
        'found: ' + present.join(', '));
    expected.forEach((name) => {
        const file = dir + '/' + A.SAMPLES[name].split('/').pop();
        const buf = fs.readFileSync(file);
        const riff = buf.toString('ascii', 0, 4) === 'RIFF' && buf.toString('ascii', 8, 12) === 'WAVE';
        const channels = buf.readUInt16LE(22);
        const rate = buf.readUInt32LE(24);
        const bits = buf.readUInt16LE(34);
        check(name + ': a 44.1 kHz mono 16-bit wav', riff && channels === 1 && rate === 44100 && bits === 16,
            `${riff} ${channels}ch ${rate}Hz ${bits}bit`);
    });
}

/* ── the verdict ──────────────────────────────────────────────────────────── */

Promise.all(asyncChecks).then(() => {
    console.log('audio selftest: ' + ok + ' ok, ' + failures.length + ' failed');
    if (failures.length) {
        failures.forEach((f) => console.log('  FAIL ' + f));
        process.exit(1);
    }
});
