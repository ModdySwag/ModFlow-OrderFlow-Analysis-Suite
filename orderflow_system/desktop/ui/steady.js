/* ══════════════════════════════════════════════════════════════════
   Steady — refresh must never fight the user.

   The complaint this exists to answer: a poll lands while you are mid-edit,
   the panel rebuilds, a toggle flips back, the screen redraws under your
   hands. Nothing in this program may do that.

   Policy, in order:

     1. a dialog is open (wizard, walkthrough, notice) → every periodic
        data render is skipped: the dialog *is* what the user is doing;
     2. the user is editing inside the container that render would replace
        → skipped, whatever else is happening;
     3. that container holds a field the user changed recently → skipped
        (unsaved input is never thrown away, not even by an unrelated poll);
     4. the pointer is down, or a key was pressed in the last few seconds
        → skipped, so a click cannot land on freshly rebuilt markup;
     5. otherwise the render runs — and the focused element, its caret and
        the scroll positions are restored afterwards if anything moved.

   A tiny "paused" badge appears while the guard is holding updates back, so
   the behaviour is visible instead of mysterious (and it is the honest place
   to look if someone wonders whether the data is live).
   ══════════════════════════════════════════════════════════════════ */

const STEADY = {
    lastActivity: 0,
    pointerDown: false,
    dirty: new Map(),          // element -> last-changed timestamp
    dirtyRoots: new Map(),     // container selector-ish key -> last-changed timestamp
    modals: ['#wizOverlay', '#helpOverlay', '#mt5Notice'],
    skipped: 0,
    allowed: 0,
    wrapped: [],
    graceTypingMs: 4000,       // after the last keystroke, updates resume
    gracePointerMs: 900,       // after a click, before markup may be replaced
    dirtyHoldMs: 30000,        // unsaved field protection
    forceUntil: 0,             // a deliberate action's window — see steadyForce/steadyShouldSkip
};

const STEADY_FIELD_SELECTOR = 'input, select, textarea, [contenteditable="true"]';

/* fields that are part of the guard itself / do not carry data being edited */
function steadyIsNeutralField(el) {
    if (!el) return true;
    if (el.id === 'programSearch') return true;            // the search box does not hold app state
    return false;
}

function steadyField(el) {
    return !!(el && el.matches && el.matches(STEADY_FIELD_SELECTOR) && !steadyIsNeutralField(el));
}

function steadyModalOpen() {
    return STEADY.modals.some((sel) => {
        const el = document.querySelector(sel);
        return !!(el && el.offsetParent !== null);          // visible
    });
}

function steadyActivity(ms) {
    return Date.now() - STEADY.lastActivity < ms;
}

/* A deliberate app-wide action (the top bar's symbol switch) asks the guard to stand aside
   for a moment: the grace below exists to hold back *incidental* updates, and the output of
   an instrument the user just picked is not incidental — it must follow the pick instead of
   sitting out the typing window on the old instrument. A window, not a switch — a stray
   poll landing inside it is an ordinary refresh, and the docked safeties (dialog, in-panel
   editing, unsaved input) still apply. */
function steadyForce(ms) {
    const window_ms = Number(ms) > 0 ? Number(ms) : 2000;
    STEADY.forceUntil = Math.max(STEADY.forceUntil, Date.now() + window_ms);
}

function steadyDirtyIn(root) {
    if (!root) return false;
    const now = Date.now();
    for (const [el] of STEADY.dirty) {
        if (!el.isConnected) { STEADY.dirty.delete(el); continue; }
        if (root.contains(el) && now - (STEADY.dirty.get(el) || 0) < STEADY.dirtyHoldMs) return true;
    }
    return false;
}

/* ── focus / scroll preservation ───────────────────────────────── */
function steadySnapshot(root) {
    const act = document.activeElement;
    const snap = {
        el: steadyField(act) ? act : null,
        start: null,
        end: null,
        scrolls: [],
    };
    if (snap.el) {
        try { snap.start = snap.el.selectionStart; snap.end = snap.el.selectionEnd; } catch (e) { /* not a text field */ }
    }
    const roots = [root, document.querySelector('.views'), document.querySelector('.rail')].filter(Boolean);
    roots.forEach((r) => snap.scrolls.push([r, r.scrollTop, r.scrollLeft]));
    // every scrollable panel, so a re-render cannot jump a list the user scrolled
    document.querySelectorAll('.card-body, .scan-wrap, .tape-scroll').forEach((el) => {
        if (el.scrollTop || el.scrollLeft) snap.scrolls.push([el, el.scrollTop, el.scrollLeft]);
    });
    return snap;
}

function steadyRestore(snap) {
    if (!snap) return;
    snap.scrolls.forEach(([el, top, left]) => {
        if (!el || !el.isConnected) return;
        if (el.scrollTop !== top) el.scrollTop = top;
        if (el.scrollLeft !== left) el.scrollLeft = left;
    });
    const el = snap.el;
    if (!el || !el.isConnected) return;
    if (document.activeElement !== el) {
        try { el.focus({ preventScroll: true }); } catch (e) { /* ignore */ }
    }
    if (snap.start !== null && el.setSelectionRange) {
        try { el.setSelectionRange(snap.start, snap.end); } catch (e) { /* ignore */ }
    }
}

/* ── the decision ──────────────────────────────────────────────── */
function steadyShouldSkip(target) {
    if (steadyModalOpen()) return 'dialog open';
    const act = document.activeElement;
    if (target && steadyField(act) && target.contains(act)) return 'editing in this panel';
    if (target && steadyDirtyIn(target)) return 'unsaved input in this panel';
    /* 6. a deliberate app-wide action asked for the pass (steadyForce): the typing/pointer
       grace holds back incidental updates — a symbol switch is the user's own, and the
       output must follow it (the panel holds the old instrument until the next beat
       otherwise, which is exactly the lag the owner measured). */
    if (STEADY.forceUntil && Date.now() < STEADY.forceUntil) return '';
    if (STEADY.pointerDown) return 'pointer down';
    if (steadyActivity(STEADY.graceTypingMs)) return 'typing';
    // a whole-view render with a field focused somewhere: only hold back if that
    // field is in a configuration view (their values are not saved per keystroke)
    if (!target && steadyField(act) && act.closest('[data-view="settings"], [data-view="alerts"], [data-view="instruments"]')) {
        return 'config field focused';
    }
    return '';
}

function steadyGuard(fn, target) {
    const name = fn.name || 'render';
    /* An async render's caller may chain .then/.finally/.catch on what it returns, and the
       skip path used to hand back a bare undefined — one TypeError then aborted the caller
       mid-handler (measured on the symbol switch: the busy rings never cleared, the 10-second
       fallback never registered, and the `ofap:symbol` event behind the refresh never fired,
       so the Engine and the Atlas panels never heard the change). A skipped async render
       therefore answers with a settled promise: nothing to wait for, and nothing broken. */
    const isAsync = fn.constructor && fn.constructor.name === 'AsyncFunction';
    const wrapped = function steadyWrapped(...args) {
        let root = null;
        if (typeof target === 'string') root = document.querySelector(target);
        else if (typeof target === 'function') root = target();
        const why = steadyShouldSkip(root);
        if (why) {
            STEADY.skipped += 1;
            steadyBadge();
            return isAsync ? Promise.resolve() : undefined;
        }
        const snap = steadySnapshot(root);
        let out;
        try {
            out = fn.apply(this, args);
        } catch (err) {
            steadyRestore(snap);
            STEADY.allowed += 1;
            throw err;
        }
        STEADY.allowed += 1;
        steadyBadge();
        steadyRestore(snap);
        // loaders rebuild their markup *after* the await: restore again when they settle,
        // or the focus the user had would be lost by the async part, not the sync one
        if (out && typeof out.then === 'function') {
            const settle = () => { steadyRestore(snap); steadyBadge(); };
            return out.then((res) => { settle(); return res; }, (err) => { settle(); throw err; });
        }
        return out;
    };
    wrapped.__steadyName = name;
    wrapped.__steadyOriginal = fn;
    return wrapped;
}

/* ── the visible "paused" badge ────────────────────────────────── */
function steadyStyles() {
    if (document.getElementById('steadyStyleSheet')) return;
    const st = document.createElement('style');
    st.id = 'steadyStyleSheet';
    st.textContent = `
        .steady-badge { position: fixed; right: 12px; bottom: 10px; z-index: 9997;
                        background: rgba(15,22,34,0.96); border: 1px solid var(--line);
                        border-radius: 999px; padding: 4px 10px; font-size: 11px; color: var(--dim);
                        display: none; align-items: center; gap: 6px; }
        .steady-badge.on { display: flex; }
        .steady-badge .dot { width: 7px; height: 7px; border-radius: 50%; background: #e8be54; }
    `;
    document.head.appendChild(st);
}

let steadyBadgeAt = 0;
function steadyBadge() {
    /* D-13: this runs on every input/pointer/wheel event and reads layout (offsetParent) three
       times per call. At most one real evaluation per 250 ms; the badge is a hint, not a meter. */
    const nowAt = Date.now();
    if (nowAt - steadyBadgeAt < 250) return;
    steadyBadgeAt = nowAt;
    steadyStyles();
    let el = document.getElementById('steadyBadge');
    if (!el) {
        el = document.createElement('div');
        el.id = 'steadyBadge';
        el.className = 'steady-badge';
        el.innerHTML = '<span class="dot"></span><span id="steadyBadgeText">updates paused while you work</span>';
        document.body.appendChild(el);
    }
    const busy = steadyModalOpen() || steadyActivity(STEADY.graceTypingMs) || STEADY.pointerDown
        || steadyField(document.activeElement);
    el.classList.toggle('on', !!busy);
    const t = document.getElementById('steadyBadgeText');
    if (t) {
        t.title = `Panels are held still while you type, click or have a dialog open. `
            + `${STEADY.skipped} render(s) skipped, ${STEADY.allowed} applied this session.`;
    }
}

/* ── activity wiring ───────────────────────────────────────────── */
function steadyWire() {
    const mark = () => { STEADY.lastActivity = Date.now(); steadyBadge(); };
    ['keydown', 'input', 'change', 'focusin', 'wheel'].forEach((ev) =>
        document.addEventListener(ev, mark, true));
    document.addEventListener('pointerdown', () => { STEADY.pointerDown = true; mark(); }, true);
    document.addEventListener('pointerup', () => { STEADY.pointerDown = false; mark(); }, true);
    document.addEventListener('input', (e) => {
        const el = e.target;
        if (el && el.matches && el.matches(STEADY_FIELD_SELECTOR)) {
            STEADY.dirty.set(el, Date.now());
        }
    }, true);
    document.addEventListener('change', (e) => {
        const el = e.target;
        if (el && el.matches && el.matches(STEADY_FIELD_SELECTOR)) {
            STEADY.dirty.set(el, Date.now());
        }
    }, true);
    // blur does not immediately clear dirt: a poll one tick later would still wipe
    // a value the user only just left (and forms save on submit, not on blur)
    setInterval(() => {
        const now = Date.now();
        for (const [el, ts] of STEADY.dirty) {
            if (!el.isConnected || now - ts > STEADY.dirtyHoldMs * 4) STEADY.dirty.delete(el);
        }
        steadyBadge();
    }, 5000);
}

/* ── wrap the app's render entry points ────────────────────────── */
function steadyWrapRenderers() {
    const map = [
        // the repo's own panels
        ['refreshSlowPanels', () => document.querySelector('.view.active')],
        ['renderOverviewSignals', '#overviewSignals, .view[data-view="overview"]'],
        ['renderOverviewTable', '#overviewTable, .view[data-view="overview"]'],
        ['renderStatus', null],
        ['renderPlatform', null],
        ['renderInstruments', '#instrumentsTable, .view[data-view="instruments"]'],
        ['renderSettings', '#settingsBody, .view[data-view="settings"]'],
        ['renderThresholds', '#thresholds, .view[data-view="settings"]'],
        ['renderAtlasSettings', '.view[data-view="settings"]'],
        ['loadFootprint', () => document.querySelector('.view[data-view="orderflow"]')],
        ['loadOrderbook', () => document.querySelector('.view[data-view="depth"]')],
        ['loadTape', () => document.querySelector('.view[data-view="tape"]')],
        ['loadSignals', () => document.querySelector('.view[data-view="signals"]')],
        ['loadStrategy', () => document.querySelector('.view[data-view="strategy"]')],
        ['loadPerformance', () => document.querySelector('.view[data-view="performance"]')],
        ['loadChart', () => document.querySelector('.view[data-view="chart"]')],
        ['loadLogs', () => document.querySelector('.view[data-view="logs"]')],
        ['refreshAllPanels', null],
        // this session's modules
        ['inLoad', '#tkIntentCard'],
        ['ctxRefresh', '#ctxCard'],
        ['mpLoad', '#mpCard'],
        ['scanRefresh', '#scanView'],
        ['vwapRefresh', null],
        ['detectorRefresh', '#ddCard'],
    ];
    map.forEach(([name, target]) => {
        const fn = window[name];
        if (typeof fn !== 'function' || fn.__steadyName) return;
        window[name] = steadyGuard(fn, target);
        STEADY.wrapped.push(name);
    });
}

(function steadyBoot() {
    steadyStyles();
    steadyWire();
    let tries = 0;
    const tick = () => {
        tries += 1;
        steadyWrapRenderers();
        steadyBadge();
        if (tries < 60) setTimeout(tick, 500);      // late-defined functions get wrapped too
    };
    tick();
    setInterval(() => {                             // and any that appear later
        if (document.hidden || window.OFAP_PAUSED) return;   // D-13: a held board sweeps nothing
        steadyWrapRenderers();
    }, 10000);
})();
