/* strips.js - scrolling information that never yanks the reader.
 *
 * A tape, an alert log, a print list: they append on their own clock. The failure mode is always the
 * same - you scroll up to read a print, the next batch lands, and the view jumps to the bottom,
 * losing the line you were on. Panels should not have to solve that individually.
 *
 * This watches the container instead of owning it: no renderer changes, no coupling. If the reader is
 * at the bottom the strip follows the newest line, exactly as before. If the reader has scrolled away,
 * the strip HOLDS ITS PLACE, keeps appending underneath, and shows "+N new" - click to return.
 */
(function () {
    'use strict';

    const guards = new Map();
    const NEAR_BOTTOM_PX = 28;

    const atBottom = (el) => (el.scrollHeight - el.scrollTop - el.clientHeight) <= NEAR_BOTTOM_PX;

    /* Which end of the list carries the newest row? A log appends (newest last, so following it
       means scrollHeight); the tape PREPENDS (newest first, so following it means offset 0).
       Detected from where the mutation actually landed: guessing a strip's shape from its name or
       its markup failed twice in this file already (see `scrollersUnder`). */
    function prependsTop(addedNodes) {
        for (const n of addedNodes || []) {
            if (!n || n.nodeType !== 1 || !n.parentElement) continue;
            /* Ask the node's OWN list, not the guarded element: the tape's rows land in a tbody one
               level below the scroller, so an el.firstElementChild comparison never matched and the
               strip kept following the wrong end. */
            const p = n.parentElement;
            return p.firstElementChild === n && p.lastElementChild !== n;
        }
        return false;
    }

    function chipFor(st) {
        if (st.chip && st.chip.isConnected) return st.chip;
        const host = st.el.parentElement || st.el;
        if (getComputedStyle(host).position === 'static') host.style.position = 'relative';
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'ofap-strip-chip';
        chip.style.display = 'none';
        chip.addEventListener('click', () => {
            st.pending = 0;
            st.newest = 0;
            st.atBottom = true;
            st.scroller.scrollTop = st.newestAtTop ? 0 : st.scroller.scrollHeight;
            paint(st);
        });
        host.appendChild(chip);
        st.chip = chip;
        return chip;
    }

    function paint(st) {
        const chip = chipFor(st);
        if (!st.pending) { chip.style.display = 'none'; paintStripState(); return; }
        chip.style.display = 'inline-block';
        const arrow = st.newestAtTop ? '↑' : '↓';
        chip.textContent = st.pending
            ? arrow + ' ' + st.pending + ' ' + (st.pending === 1 ? st.label.replace(/s$/, '') : st.label) + ' · jump to newest'
            : arrow + ' new ' + st.label + ' · jump to newest';
        paintStripState();
    }

    function paintStripState() {
        /* The status chip must be able to say "3 strips are holding your place" - the user should
           never have to guess why a list is not moving. */
        const held = [...guards.values()].filter((s) => s.pending > 0).length;
        if (window.OFAPINTENT && OFAPINTENT.setStrips) OFAPINTENT.setStrips(held);
    }

    /* The node the caller hands us is often the content, not the scroller: a tbody inside a card, a
       row list inside a panel. Reading scrollTop off the content node is how the first version of
       this silently never noticed that the reader had scrolled away. Resolve the real scroller. */
    function scrollerOf(el) {
        if (!el) return el;
        if (el.scrollHeight > el.clientHeight + 1) return el;
        const p = el.parentElement;
        if (p && p.scrollHeight > p.clientHeight + 1) return p;
        return el;
    }

    /* Renderer-agnostic identity of the newest row. A list that appends grows in height (counted by
       element additions); a list that caps its length REPLACES its top row and never grows - the tape
       does the latter, which is why an additions-only count showed nothing for it. */
    function topSignature(el) {
        const first = el.firstElementChild;
        if (!first) return '';
        const attrs = first.dataset ? Object.keys(first.dataset).sort().map((k) => k + '=' + first.dataset[k]).join('|') : '';
        return attrs || (first.textContent || '').trim().slice(0, 90);
    }

    function guard(el, opts) {
        if (!el || guards.has(el)) return null;
        const st = { el: el, scroller: scrollerOf(el), pending: 0, atBottom: true, lastTop: 0,
                     label: (opts && opts.label) || 'new', chip: null, newestAtTop: false };
        guards.set(el, st);
        st.lastTop = st.scroller.scrollTop;

        /* SAFETY: if no ancestor actually scrolls, this strip cannot be anchored - so it must never
           touch a scroll position. Counting is still useful; moving a reader's scroll with a bad
           anchor is not. The first version could have pulled a reader to the top, which is worse
           than the jump it was written to prevent. */
        st.animate = false;
        const refreshAnchor = () => {
            const sc = scrollerOf(el);
            st.scroller = sc;
            st.animate = sc === el ? el.scrollHeight > el.clientHeight + 1
                                   : !!(sc && sc.scrollHeight > sc.clientHeight + 1);
            return st.animate;
        };
        refreshAnchor();

        const onScroll = () => {
            refreshAnchor();
            st.lastTop = st.scroller.scrollTop;
            /* Reading a prepend list at offset 0 is the same reader state as reading an append
               list at its end: both mean "on the newest line". */
            st.atBottom = st.newestAtTop ? (st.scroller.scrollTop <= NEAR_BOTTOM_PX) : atBottom(st.scroller);
            if (st.atBottom) { st.pending = 0; paint(st); }
        };
        el.addEventListener('scroll', onScroll, { passive: true, capture: true });
        if (el.parentElement) el.parentElement.addEventListener('scroll', onScroll, { passive: true });

        st.sig = topSignature(el);
        st.newest = 0;
        st.lastCountedAt = 0;

        const obs = new MutationObserver((records) => {
            /* Elements only: a renderer that rebuilds rows also fires for text and attributes, and
               counting those produced "36360 prints" on the real tape - a number nobody can trust.
               If the content is not actually growing, the honest chip says "new prints", not a
               fabricated count. */
            let added = 0;
            const addedNodes = [];
            records.forEach((r) => {
                if (!r.addedNodes) return;
                r.addedNodes.forEach((n) => {
                    if (!n || n.nodeType !== 1) return;
                    added += 1;
                    addedNodes.push(n);
                });
            });
            if (added && prependsTop(addedNodes)) st.newestAtTop = true;
            /* A capped list: the top row changing IS a new print. Throttled so a repaint inside the
               same row cannot inflate the count, and only used when nothing was actually added. */
            refreshAnchor();                     // the strip may have just become scrollable
            const sig = topSignature(el);
            const topChanged = sig && sig !== st.sig;
            st.sig = sig;
            const now = Date.now();
            if (topChanged && !added && (now - st.lastCountedAt) > 250) {
                st.newest += 1;
                st.lastCountedAt = now;
            }
            if (!added && !topChanged) return;
            const nowHeight = el.scrollHeight;
            st.growing = nowHeight > (st.lastHeight || 0);
            st.lastHeight = nowHeight;
            if (!st.growing) added = 0;          // arriving, not accumulating
            if (st.atBottom) {
                /* follow the newest line - at the bottom for a log, at the top for the tape */
                st.scroller.scrollTop = st.newestAtTop ? 0 : st.scroller.scrollHeight;
                st.pending = 0;
                st.lastTop = st.scroller.scrollTop;
                paint(st);
                return;
            }
            /* The reader is elsewhere in the list: count what arrived and put the scroll back where
               they left it. Nothing is dropped - it is all there, one click away. */
            if (added) st.pending += added;
            else st.pending = Math.max(st.pending, st.newest, 1);   // the counted arrivals, or at least one
            const want = st.lastTop;
            if (!st.animate) { paint(st); return; }        // count only: never move what we cannot anchor
            requestAnimationFrame(() => {
                if (!guards.has(el) || !st.animate) return;
                st.scroller = scrollerOf(el);
                if (Math.abs(st.scroller.scrollTop - want) > 1) st.scroller.scrollTop = want;
                paint(st);
            });
        });
        obs.observe(el, { childList: true, subtree: true });
        st.obs = obs;
        paint(st);
        return st;
    }

    /* Hand-picking selectors failed twice: the tape's rows live one level deeper than the container
       I named, and the alerts table has no scroller until it has rows. So discover the scrollers
       instead of guessing their addresses - anything in the visible view that actually scrolls now
       is a strip, whatever it is called. */
    function scrollersUnder(root, limit) {
        const out = [];
        const els = [root].concat([...root.querySelectorAll('*')]);
        for (const el of els) {
            if (out.length >= (limit || 6)) break;
            const cs = getComputedStyle(el);
            if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 8) {
                out.push(el);
            }
        }
        return out;
    }

    function scan() {
        const roots = [document.querySelector('.view.active'), document.getElementById('tapeContainer'),
                       document.getElementById('alertTable'), document.getElementById('logBody')];
        const seen = new Set();
        roots.forEach((root) => {
            if (!root || seen.has(root)) return;
            seen.add(root);
            scrollersUnder(root).forEach((el) => {
                if (guards.has(el)) return;
                guard(el, { label: labelFor(el) });
            });
        });
    }

    function labelFor(el) {
        const id = (el.id || '') + ' ' + (typeof el.className === 'string' ? el.className : '');
        if (/tape|print/i.test(id)) return 'prints';
        if (/alert/i.test(id)) return 'alerts';
        if (/log/i.test(id)) return 'log lines';
        if (/study|signal/i.test(id)) return 'studies';
        return 'rows';
    }

    document.addEventListener('click', () => setTimeout(scan, 400));
    /* A strip that only becomes scrollable later (a tape filling with prints, an alert log growing)
       must still be picked up. A rescan of the visible view is cheap and keeps that honest. */
    setInterval(() => { if (!document.hidden) scan(); }, 6000);
    document.addEventListener('ofap:relayout', () => setTimeout(scan, 400));
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(scan, 900));
    else setTimeout(scan, 900);

    window.OFAPSTRIPS = { guard: guard, scan: scan, state: guards,
                          holding: () => [...guards.values()].filter((s) => s.pending > 0).length };
})();
