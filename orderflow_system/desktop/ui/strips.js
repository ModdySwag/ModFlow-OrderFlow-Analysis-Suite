/* strips.js - scrolling information that never yanks the reader.
 *
 * A tape, an alert log, a print list: they append on their own clock. The failure mode is always the
 * same - you scroll up to read a print, the next batch lands, and the view jumps to the bottom,
 * losing the line you were on. Panels should not have to solve that individually.
 *
 * This watches the container instead of owning it: no renderer changes, no coupling. If the reader is
 * at the bottom the strip follows the newest line, exactly as before. If the reader has scrolled away,
 * the strip HOLDS ITS PLACE, keeps appending underneath, and shows "+N new" - click to return.
 *
 * P1-4 gave the reader hands: arrows step a row, PageUp/PageDown a screenful, Home/End go to either
 * end, and a click on a row that carries data-time/data-price LOCATES it - the print goes onto the
 * shared cursor and the engine seeks its viewport to that bar.
 */
(function () {
    'use strict';

    const guards = new Map();
    const NEAR_BOTTOM_PX = 28;

    /* Pure: where a step lands, clamped to the scroller. Kept out of the DOM so the selftest can pin
       the arithmetic (a step past either end stays at that end, never wraps or goes negative). */
    const math = {
        stepTarget(scrollTop, rowH, dir, max) {
            const h = Number(rowH) > 0 ? Number(rowH) : 18;
            const limit = Math.max(0, Number(max) || 0);
            /* The start is clamped into the scroller first: a nonsense position (negative, past the
               end, undefined) is treated as the nearest real place, then stepped from there. */
            const top = Math.max(0, Math.min(limit, Number(scrollTop) || 0));
            return Math.max(0, Math.min(limit, top + h * (Number(dir) < 0 ? -1 : 1)));
        },
    };

    const atBottom = (el, eps) => (el.scrollHeight - el.scrollTop - el.clientHeight)
        <= (eps == null ? NEAR_BOTTOM_PX : eps);

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
            release(st);
        });
        host.appendChild(chip);
        st.chip = chip;
        return chip;
    }

    function paint(st) {
        const chip = chipFor(st);
        const held = !!st.pending || !!st.held;
        if (!held) { chip.style.display = 'none'; chip.classList.remove('held'); paintStripState(); return; }
        chip.style.display = 'inline-block';
        chip.classList.toggle('held', !st.pending);
        const arrow = st.newestAtTop ? '↑' : '↓';
        chip.textContent = st.pending
            ? arrow + ' ' + st.pending + ' ' + (st.pending === 1 ? st.label.replace(/s$/, '') : st.label) + ' · jump to newest'
            : arrow + ' ' + st.label + ' held · jump to newest';
        paintStripState();
    }

    function paintStripState() {
        /* The status chip must be able to say "3 strips are holding your place" - the user should
           never have to guess why a list is not moving. */
        const held = [...guards.values()].filter((s) => s.pending > 0 || s.held).length;
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
                     label: (opts && opts.label) || 'new', chip: null, newestAtTop: false,
                     held: false, hovered: false, rowH: 0 };
        guards.set(el, st);
        st.lastTop = st.scroller.scrollTop;

        /* SAFETY: if no ancestor actually scrolls, this strip cannot be anchored - so it must never
           touch a scroll position. Counting is still useful; moving a reader's scroll with a bad
           anchor is not. The first version could have pulled a reader to the top, which is worse
           than the jump it was written to prevent. */
        st.animate = false;

        /* The anchor is sticky once found. A rebuild empties a tbody for a frame; re-resolving then
           walks up to the PARENT, and the parent's offset (0) reads as "the reader is on the newest
           line", releasing a hold a keystroke has just engaged. Keep what we have while it is still
           the strip's own node; resolve fresh only when there is nothing left to keep. */
        const keepScroller = () => {
            const prev = st.scroller;
            if (prev && prev.isConnected && (prev === el || el.contains(prev) || prev.contains(el))) return prev;
            return scrollerOf(el);
        };
        const refreshAnchor = () => {
            st.scroller = keepScroller();
            st.animate = st.scroller.scrollHeight > st.scroller.clientHeight + 1;
            return st.animate;
        };
        refreshAnchor();

        /* The decision a scroll event makes has to be made against the scroller the strip HAS, not
           against a freshly re-resolved anchor: a rebuild empties the tbody for a frame, `scrollerOf`
           then walks up to the parent, and the parent's offset (0) reads as "the reader is at the
           newest end" - which silently released the hold a keystroke had just engaged. While the
           strip's own nodes are scrollable, that scroller is the one; mid-rebuild, keep the old one. */
        const onScroll = () => {
            st.scroller = keepScroller();
            st.animate = st.scroller.scrollHeight > st.scroller.clientHeight + 1;
            st.lastTop = st.scroller.scrollTop;
            /* Reading a prepend list at offset 0 is the same reader state as reading an append
               list at its end: both mean "on the newest line". */
            st.atBottom = st.newestAtTop ? (st.scroller.scrollTop <= nearEnd(st)) : atBottom(st.scroller, nearEnd(st));
            if (st.atBottom) { st.pending = 0; st.held = false; paint(st); }
        };
        el.addEventListener('scroll', onScroll, { passive: true, capture: true });
        /* The keys act on the strip under the pointer; tracking hover is two cheap listeners. */
        el.addEventListener('pointerenter', () => { st.hovered = true; });
        el.addEventListener('pointerleave', () => {
            st.hovered = false;
            /* A hover that never became a scroll is transient: resume following and drop the count
               it accumulated. A reader who had scrolled away keeps their place and their chip. */
            if (st.atBottom && !st.held) {
                st.pending = 0;
                st.scroller.scrollTop = newestEnd(st);
                st.lastTop = st.scroller.scrollTop;
                paint(st);
            }
        });
        /* Click-to-locate: the nearest row that names a time or a price. */
        el.addEventListener('click', (ev) => {
            const row = ev.target && ev.target.closest ? ev.target.closest('[data-time],[data-price]') : null;
            if (!row || !el.contains(row)) return;
            st.lastLocate = locate(st, row);
        }, true);
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
                if (st.hovered) {
                    /* PAUSE ON HOVER: the pointer is on the list, so scrolling it would pull the row
                       out from under the reader's eyes - the exact jump this module exists to prevent,
                       one gesture earlier. Count what arrived; leave the rows where they are. The
                       pointer leaving resumes following (see pointerleave). */
                    if (added) st.pending += added;
                    else st.pending = Math.max(st.pending, st.newest, 1);
                    paint(st);
                    return;
                }
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

    /* Which end is the newest one: the end the strip FOLLOWS. A log appends (the bottom), the tape
       prepends (the top). */
    function newestEnd(st) {
        return st.newestAtTop ? 0 : st.scroller.scrollHeight;
    }

    /* How close to the follow end still counts as "on the newest line". Never more than half a row:
       with a fixed 28 px, one ArrowDown step (24 px) still read as "at the end", so the hold was
       released the instant it was engaged and the next arriving print pulled the reader back. */
    function nearEnd(st) {
        return Math.min(NEAR_BOTTOM_PX, Math.max(1, rowHeight(st) / 2));
    }

    /* One row's height, measured rather than assumed: a table row, a div row, or a fallback. */
    function rowHeight(st) {
        const host = st.scroller.querySelector('tbody') || st.scroller;
        const first = host.firstElementChild || st.el.firstElementChild;
        if (!first || !first.getBoundingClientRect) return st.rowH || 18;
        const h = first.getBoundingClientRect().height;
        if (h > 2) st.rowH = h;
        return st.rowH || 18;
    }

    function release(st) {
        st.pending = 0;
        st.newest = 0;
        st.held = false;
        st.atBottom = true;
        st.scroller.scrollTop = newestEnd(st);
        st.lastTop = st.scroller.scrollTop;
        paint(st);
    }

    /* Move the reader's place on purpose: this IS a hold, so the chip says so even before anything has
       arrived, and the guard's restore-the-last-position step keeps the new place. */
    function step(st, dir, target) {
        if (!st) return null;
        const sc = st.scroller;
        const max = Math.max(0, sc.scrollHeight - sc.clientHeight);
        const from = sc.scrollTop;
        const to = target != null ? Math.max(0, Math.min(max, target)) : math.stepTarget(from, rowHeight(st), dir, max);
        sc.scrollTop = to;
        st.lastTop = to;
        st.atBottom = Math.abs(to - newestEnd(st)) <= nearEnd(st);
        st.held = !st.atBottom;
        if (st.atBottom) st.pending = 0;
        paint(st);
        return { from: from, to: to, held: st.held, atBottom: st.atBottom };
    }

    /* A row that carries a time (and usually a price) is a place in the session, not just a line of
       text: clicking it puts the print on the shared cursor, seeks the engine's viewport to that bar,
       and ends the hold - the reader has picked the line they were reading. */
    function locate(st, node) {
        if (!st || !node || !node.getAttribute) return null;
        const price = Number(node.getAttribute('data-price'));
        const time = Number(node.getAttribute('data-time'));
        const hasPrice = Number.isFinite(price);
        const hasTime = Number.isFinite(time) && time > 0;
        if (!hasPrice && !hasTime) return null;
        let reached = 0;
        if (window.OFAPCURSOR) {
            OFAPCURSOR.move(hasPrice ? price : null, hasTime ? time : null, 'locate');
            reached += 1;
        }
        let bar = null;
        if (hasTime && window.OFX && typeof OFX.seekToTime === 'function') {
            bar = OFX.seekToTime(time);
            if (bar != null) reached += 1;
        }
        release(st);
        return { price: hasPrice ? price : null, time: hasTime ? time : null, bar: bar, reached: reached };
    }

    /* The strip the keys should act on: the event's own strip first, then the one under the pointer,
       then the last one the reader touched. */
    function stripFor(node) {
        let el = node && node.nodeType === 1 ? node : (node && node.parentElement);
        while (el) {
            if (guards.has(el)) return guards.get(el);
            el = el.parentElement;
        }
        const hovered = [...guards.values()].filter((s) => s.hovered);
        if (hovered.length) return hovered[hovered.length - 1];
        return null;
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

    /* Arrow stepping. Guarded like the shell's own hotkeys: never while a field has focus, and only
       when a strip is hovered or the event came from inside one. */
    const TYPING = /^(INPUT|SELECT|TEXTAREA)$/;
    document.addEventListener('keydown', (ev) => {
        if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
        const t = ev.target;
        if (t && (TYPING.test(t.tagName || '') || t.isContentEditable)) return;
        const st = stripFor(t);
        if (!st || !st.animate) return;
        const sc = st.scroller;
        const page = Math.max(1, sc.clientHeight - rowHeight(st));
        let handled = false;
        if (ev.key === 'ArrowUp' || ev.key === 'ArrowDown') {
            step(st, ev.key === 'ArrowUp' ? -1 : 1);
            handled = true;
        } else if (ev.key === 'PageUp' || ev.key === 'PageDown') {
            step(st, 0, sc.scrollTop + (ev.key === 'PageUp' ? -page : page));
            handled = true;
        } else if (ev.key === 'Home' || ev.key === 'End') {
            /* Home is the NEWEST end (the end the strip follows), End the oldest - so the two keys
               are the same on every strip whatever its direction. */
            const newest = ev.key === 'Home';
            step(st, 0, newest ? newestEnd(st) : (st.newestAtTop ? sc.scrollHeight : 0));
            handled = true;
        }
        if (handled) {
            ev.preventDefault();
            /* The arbiter already leases the surface on keydown, so the status chip names it; this
               only keeps the shell from also acting on the key. */
            st.lastStepAt = Date.now();
        }
    }, true);

    document.addEventListener('click', () => setTimeout(scan, 400));
    /* A strip that only becomes scrollable later (a tape filling with prints, an alert log growing)
       must still be picked up. A rescan of the visible view is cheap and keeps that honest. */
    setInterval(() => { if (!document.hidden) scan(); }, 6000);
    document.addEventListener('ofap:relayout', () => setTimeout(scan, 400));
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(scan, 900));
    else setTimeout(scan, 900);

    /* Does a reader hold this element? The one question a renderer with its own follow logic has to
       ask before moving the offset (tape.js asked it not at all until P1-4, and its `scrollTop = 0`
       on every batch released the hold a keystroke had just engaged). */
    function holds(el) {
        const st = guards.get(el);
        return !!(st && (st.held || st.pending > 0));
    }

    window.OFAPSTRIPS = { guard: guard, scan: scan, state: guards, math: math, holds: holds,
                          step: step, locate: locate, release: release, rowHeight: rowHeight,
                          stripFor: stripFor,
                          holding: () => [...guards.values()].filter((s) => s.pending > 0 || s.held).length };
})();
