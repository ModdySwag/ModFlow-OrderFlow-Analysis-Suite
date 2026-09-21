/* presets.js — the "common values, else your own" combobox (control-surface audit §4, 2026-09-19).
 *
 * A control declares its common values in markup — `data-presets="68,70,80,90,100"` — and this
 * module decorates it at boot with a small preset select beside the original input plus a
 * "Custom…" row that hands the field back for typing. Picking a preset drives the input through
 * its OWN change path (set the value, dispatch `change`), so every existing save path runs and
 * the store adopts the value exactly as if it had been typed — the pattern the audit asked for,
 * with no per-control wiring.
 *
 * The deciding half is pure (`parseSpec`, `pick`) and the Node selftest pins it; the DOM half is a
 * thin executor. A control whose spec is junk is left exactly as it was — the app never grows a
 * broken dropdown where a working number input stood.
 */
'use strict';

(function () {
    var CUSTOM = '__custom';

    function parseSpec(spec) {
        var parts = String(spec == null ? '' : spec).split(',');
        var out = [];
        for (var i = 0; i < parts.length; i += 1) {
            var raw = parts[i] == null ? '' : String(parts[i]).trim();
            if (raw === '') continue;
            var n = Number(raw);
            if (isFinite(n)) out.push(n);
        }
        return out;
    }

    /* What the select should show for a current input value: the value's own string when it is one
       of the presets, else `__custom`. String compare on both sides — "0.70" typed by hand is not
       a preset even though Number("0.70") === 0.7; the select then honestly says Custom. */
    function pick(spec, value) {
        var values = parseSpec(spec);
        var text = String(value == null ? '' : value);
        for (var i = 0; i < values.length; i += 1) {
            if (String(values[i]) === text) return text;
        }
        return CUSTOM;
    }

    function decorate(input) {
        if (!input || input.__ofapPresets) return false;
        var spec = input.getAttribute ? input.getAttribute('data-presets') : '';
        var values = parseSpec(spec);
        if (values.length < 2) return false;                 // one value is not a chooser
        if (!input.parentNode) return false;
        input.__ofapPresets = true;

        var wrap = document.createElement('span');
        wrap.className = 'preset-wrap';
        var sel = document.createElement('select');
        sel.className = 'preset-select';
        sel.title = 'Common values — or Custom… and type your own';
        for (var i = 0; i < values.length; i += 1) {
            var opt = document.createElement('option');
            opt.value = String(values[i]);
            opt.textContent = String(values[i]);
            sel.appendChild(opt);
        }
        var custom = document.createElement('option');
        custom.value = CUSTOM;
        custom.textContent = 'Custom…';
        sel.appendChild(custom);

        function syncFromInput() { sel.value = pick(spec, input.value); }
        sel.addEventListener('change', function () {
            if (sel.value === CUSTOM) {
                /* Custom… is a door, not a value: hand the field back, focused for typing. */
                try { input.focus(); if (input.select) input.select(); } catch (e) { /* fine */ }
                return;
            }
            input.value = sel.value;
            input.dispatchEvent(new Event('change', { bubbles: true }));
        });
        input.addEventListener('input', syncFromInput);
        input.addEventListener('change', syncFromInput);

        input.__ofapSync = syncFromInput;
        input.parentNode.insertBefore(wrap, input);
        wrap.appendChild(sel);
        syncFromInput();
        return true;
    }

    /* Re-read the pairing after something WRITES an input programmatically — a params re-read, a
       settings render, the calendar's config load. A bare `input.value = …` fires no event, so the
       chip beside the field would keep naming the value the field no longer holds (the same
       "two controls, one story" rule the symbol bar learned). Called by the mass re-seeds. */
    function refresh(root) {
        var host = root || (typeof document !== 'undefined' ? document : null);
        if (!host || typeof host.querySelectorAll !== 'function') return 0;
        var nodes = host.querySelectorAll('input[data-presets]');
        var synced = 0;
        for (var i = 0; i < nodes.length; i += 1) {
            if (typeof nodes[i].__ofapSync === 'function') {
                nodes[i].__ofapSync();
                synced += 1;
            }
        }
        return synced;
    }

    function scan(root) {
        var host = root || (typeof document !== 'undefined' ? document : null);
        if (!host || typeof host.querySelectorAll !== 'function') return 0;
        var nodes = host.querySelectorAll('[data-presets]');
        var decorated = 0;
        for (var i = 0; i < nodes.length; i += 1) {
            if (decorate(nodes[i])) decorated += 1;
        }
        return decorated;
    }

    function boot() {
        scan(document);
        /* A runtime-built control (the terminal's + widget adder, a view rebuilt late) joins by
           being scanned again; the sweep is debounced and idempotent (`__ofapPresets`). */
        if (typeof MutationObserver === 'function') {
            var pending = null;
            new MutationObserver(function () {
                if (pending) return;
                pending = setTimeout(function () { pending = null; scan(document); }, 400);
            }).observe(document.body, { childList: true, subtree: true });
        }
    }

    if (typeof window !== 'undefined') {
        window.OFAPPRESETS = { parseSpec: parseSpec, pick: pick, decorate: decorate, scan: scan,
            refresh: refresh, CUSTOM: CUSTOM };
    }
    if (typeof document !== 'undefined') {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
        else boot();
    }
})();
