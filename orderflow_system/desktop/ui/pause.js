/* pause.js — freeze every background refresh in OFAP while you work.
 *
 * The engine repaints on rAF and polls its feed on a timer; other modules do the same. Any of
 * them can hand its timer to `OFAPPause.register()`, and one control stops the lot:
 *
 *     const id = setInterval(refresh, 2500);
 *     window.OFAPPause?.register(id, () => { /* restart your own work * (); });
 *
 * The chip lives in the topbar (top-right). `P` toggles it. The state is remembered per browser
 * so a reload does not silently un-freeze a board you parked.
 */
(function () {
    'use strict';

    const KEY = 'ofap.paused';
    const timers = new Map();       // live timerId -> restart callback (emptied while paused)
    const starters = new Set();     // every registered restart callback, outliving its timer
    const state = { paused: false };

    function chipEl() { return document.getElementById('ofapPause'); }

    function paint() {
        const chip = chipEl();
        if (chip) {
            chip.classList.toggle('on', state.paused);
            chip.textContent = state.paused ? '⏸ paused — updates held' : '▶ live — updates running';
            chip.title = state.paused
                ? 'Background refreshes are held: the chart is frozen exactly as it is. Click (or press P) to resume.'
                : 'Background refreshes are running. Click (or press P) to freeze the board while you work on it.';
        }
        if (window.OFX) {
            if (state.paused) OFX.stop();
            else OFX.start();
        }
        if (window.OFAPINTENT) OFAPINTENT.freezeView(state.paused);
        document.dispatchEvent(new CustomEvent('ofap:paused', { detail: { paused: state.paused } }));
    }

    function setPaused(next, remember) {
        state.paused = Boolean(next);
        window.OFAP_PAUSED = state.paused;
        /* Snapshot both ways: a restart callback registers the id of the timer it just created,
           and iterating the live map would then visit that new entry as well. */
        for (const [id] of [...timers]) {
            if (state.paused) { clearInterval(id); timers.delete(id); }
        }
        if (!state.paused) {
            for (const restart of [...starters]) {
                try { restart(); } catch (err) { /* one owner must not stop the others */ }
            }
        }
        if (!state.paused && window.OFX) OFX.renderLayers(true);   // one clean repaint on resume
        if (remember !== false) { try { localStorage.setItem(KEY, state.paused ? '1' : '0'); } catch (err) { /* private mode */ } }
        paint();
    }

    /* The P key lands here (registered into keys.js's map in wire), so the chip's click and the
       key can never disagree about what the state is. */
    function toggle() { setPaused(!state.paused); }

    function register(id, restart) {
        if (typeof id === 'number') timers.set(id, restart);
        /* The callback is kept even after its timer is cleared on pause: a resume rebuilds the
           work from here, which is the whole point of registering. */
        if (typeof restart === 'function') starters.add(restart);
        return id;
    }

    /* An owner that replaces its own timer (a poll re-created on resume) hands in the old id, so
       the next resume does not try to restart a timer that no longer exists. */
    function unregister(id) {
        return timers.delete(id);
    }

    function wire() {
        const chip = chipEl();
        if (chip) chip.addEventListener('click', () => setPaused(!state.paused));
        /* P is the map's 'freeze' binding: registered here because this module owns the action,
           dispatched by keys.js so it carries the shared typing guard and shows up in the sheet. */
        if (window.OFAPKEYS) {
            OFAPKEYS.bind({ id: 'freeze', keys: ['p'], scope: 'Global',
                label: 'freeze / resume every background refresh', run: toggle });
        }
        let remembered = false;
        try { remembered = localStorage.getItem(KEY) === '1'; } catch (err) { remembered = false; }
        setPaused(remembered, false);
    }

    window.OFAPPause = { state, register, unregister, setPaused, toggle, isPaused: () => state.paused };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire);
    else wire();
})();
