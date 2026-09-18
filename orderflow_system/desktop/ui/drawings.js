/* drawings.js — the drawing layer.
 *
 * Cloned from the workflow he uses in his order-flow program, checked against its own settings file
 * (`drawingSettings`: lineColorRgb, fillColorRgb, lineWidth, lineStyle, alwaysHighlightPrice,
 * alwaysHighlightTime, per chart) and its documented behaviour:
 *   - a tool menu with figures + text, single-figure mode, hide all, change style, clear all;
 *   - right-click a drawing to edit or delete it;
 *   - Shift constrains lines and rays to 45 degrees;
 *   - a drawing can highlight its time span on the time axis and its price span on the price axis,
 *     on hover or permanently;
 *   - rectangles can extend beyond their original boundaries.
 *
 * View-agnostic on purpose: an adapter supplies the coordinate transforms, so the same layer serves
 * the Engine matrix (bar index / price) and a candle chart (time / price) without knowing which one
 * it is attached to. Drawings are stored in DATA space (epoch seconds + price), never pixels, so pan,
 * zoom and timeframe changes cannot move them.
 */
(function (root) {
    'use strict';

    const KINDS = [
        { id: 'select', label: 'Select / edit', glyph: '⬉', needs: 'none', hint: 'click a drawing to edit it, drag its handles' },
        { id: 'line', label: 'Trend line', glyph: '╱', needs: 'two', hint: 'drag; hold Shift for 45°' },
        { id: 'ray', label: 'Ray', glyph: '➚', needs: 'two', hint: 'a line that continues from its first point' },
        { id: 'hline', label: 'Horizontal line', glyph: '━', needs: 'one', hint: 'one price, across the whole chart' },
        { id: 'vline', label: 'Vertical line', glyph: '┃', needs: 'one', hint: 'one time, top to bottom' },
        { id: 'rect', label: 'Rectangle', glyph: '▭', needs: 'two', hint: 'drag a price/time box; it can extend left/right' },
        { id: 'ellipse', label: 'Ellipse', glyph: '◯', needs: 'two', hint: 'drag between opposite corners' },
        { id: 'channel', label: 'Parallet channel', glyph: '⫽', needs: 'two', hint: 'a trend line with a parallel offset rail' },
        { id: 'fib', label: 'Fibonacci retracement', glyph: '⋔', needs: 'two', hint: 'levels 0 · .236 · .382 · .5 · .618 · .786 · 1' },
        { id: 'text', label: 'Text', glyph: 'T', needs: 'text', hint: 'click, type, Enter' },
        { id: 'measure', label: 'Measure', glyph: '⤢', needs: 'two', hint: 'Δprice, ticks, Δtime and the % move' },
    ];
    const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];

    const state = {
        tool: 'select', drawings: [], selected: null, hidden: false, single: false,
        style: { line: '#4f8cff', fill: 'rgba(79,140,255,.14)', width: 2, dash: 'solid', fontSize: 12 },
        adapter: null, host: null, canvas: null, ctx: null, overlay: null, toolbar: null,
        dragging: null, draft: null, menu: null, seq: 0, tickSize: 0.1, dirty: false, loading: false,
        /* T13/B12: the multi-selection and the bounded undo history (the primary stays
           `selected`); T13/B11: the consequence chip element. */
        multiIds: [], undoStack: [], tip: null,
    };

    const el = (id) => document.getElementById(id);
    const toolsById = Object.fromEntries(KINDS.map((t) => [t.id, t]));
    function uid() { state.seq += 1; return `d${Date.now().toString(36)}${state.seq.toString(36)}`; }

    /* T13/B12: the undo history — one entry per reversible edit, newest last, bounded; the
       entries are closures over what was there, which is all a local edit needs. */
    const UNDO_MAX = 50;
    function pushUndo(entry) {
        if (!entry || typeof entry.undo !== 'function') return;
        state.undoStack.push(entry);
        if (state.undoStack.length > UNDO_MAX) state.undoStack.shift();
    }
    function undo() {
        const entry = state.undoStack.pop();
        if (!entry) return false;
        entry.undo();
        state.multiIds = state.multiIds.filter((id) => state.drawings.some((d) => d.id === id));
        if (state.selected && !state.drawings.some((d) => d.id === state.selected)) state.selected = null;
        paint(); save();
        refreshToolbar();
        return true;
    }
    /* Pure, so the selftest can pin the shift-click toggle. */
    function toggleMember(list, id) {
        const out = (list || []).slice();
        const at = out.indexOf(id);
        if (at >= 0) out.splice(at, 1); else out.push(id);
        return out;
    }
    function isSelected(id) {
        return state.selected === id || state.multiIds.indexOf(id) >= 0;
    }
    function selectionIds() {
        const ids = state.multiIds.slice();
        if (state.selected && ids.indexOf(state.selected) < 0) ids.push(state.selected);
        return ids.filter((id) => state.drawings.some((d) => d.id === id));
    }
    /* T13/B11: the consequence chip — created once per host, moved with the pointer. */
    function ensureTip() {
        if (state.tip && state.tip.isConnected) return state.tip;
        if (!state.host) return null;
        const tip = document.createElement('div');
        tip.className = 'risk-chip';
        tip.hidden = true;
        state.host.appendChild(tip);
        state.tip = tip;
        return tip;
    }

    /* ── coordinates ──────────────────────────────────────────────────────── */
    function toPx(point) {
        const a = state.adapter;
        if (!a || !point) return { x: 0, y: 0 };
        return { x: a.timeToX(point.t), y: a.priceToY(point.p) };
    }
    function toData(x, y) {
        const a = state.adapter;
        return { t: a.xToTime(x), p: a.yToPrice(y) };
    }
    function size() {
        const a = state.adapter;
        return { w: a ? a.width() : 0, h: a ? a.height() : 0 };
    }

    /* ── geometry helpers ─────────────────────────────────────────────────── */
    function distToSegment(px, py, ax, ay, bx, by) {
        const dx = bx - ax, dy = by - ay;
        const len2 = dx * dx + dy * dy;
        if (!len2) return Math.hypot(px - ax, py - ay);
        let t = ((px - ax) * dx + (py - ay) * dy) / len2;
        t = Math.max(0, Math.min(1, t));
        return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
    }
    function snap45(a, b) {
        /* Shift constrains a line to 45° in SCREEN space, which is what the user sees. */
        const pa = toPx(a.a), pb = toPx(b.b);
        const dx = pb.x - pa.x, dy = pb.y - pa.y;
        const len = Math.max(Math.abs(dx), Math.abs(dy));
        return { ...b, b: toData(pa.x + Math.sign(dx) * len, pa.y + Math.sign(dy) * len) };
    }

    /* ── rendering ────────────────────────────────────────────────────────── */
    function styleOf(draw) {
        return { ...state.style, ...(draw.style || {}) };
    }
    function strokeFor(ctx, draw, width) {
        const s = styleOf(draw);
        ctx.strokeStyle = s.line;
        ctx.lineWidth = width || s.width || 2;
        ctx.setLineDash(s.dash === 'dashed' ? [8, 5] : (s.dash === 'dotted' ? [2, 3] : []));
    }
    function label(ctx, text, x, y, color) {
        ctx.font = `600 ${state.style.fontSize}px ui-monospace, monospace`;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        const w = ctx.measureText(text).width + 8;
        ctx.fillStyle = 'rgba(8,12,20,.82)';
        ctx.fillRect(x, y - 8, w, 15);
        ctx.fillStyle = color || '#dbe4f0';
        ctx.fillText(text, x + 4, y);
    }

    function drawOne(ctx, draw) {
        const { w, h } = size();
        const a = toPx(draw.a), b = toPx(draw.b || draw.a);
        const sel = state.selected === draw.id;
        ctx.save();
        strokeFor(ctx, draw);
        if (draw.kind === 'hline') {
            ctx.beginPath(); ctx.moveTo(0, a.y); ctx.lineTo(w, a.y); ctx.stroke();
            label(ctx, draw.text || `${draw.a.p.toFixed(2)}`, 6, a.y - 10, styleOf(draw).line);
        } else if (draw.kind === 'vline') {
            ctx.beginPath(); ctx.moveTo(a.x, 0); ctx.lineTo(a.x, h); ctx.stroke();
        } else if (draw.kind === 'line' || draw.kind === 'measure') {
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
            if (draw.kind === 'measure') {
                const dp = draw.b.p - draw.a.p;
                const ticks = state.tickSize ? dp / state.tickSize : 0;
                const pct = draw.a.p ? (dp / draw.a.p) * 100 : 0;
                const mins = Math.round(Math.abs(draw.b.t - draw.a.t) / 60);
                label(ctx, `${dp >= 0 ? '+' : ''}${dp.toFixed(2)}  (${ticks >= 0 ? '+' : ''}${ticks.toFixed(0)} ticks, ${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%)`,
                    Math.min(a.x, b.x) + 6, Math.min(a.y, b.y) - 14, '#ffd166');
                label(ctx, `${mins} min`, Math.min(a.x, b.x) + 6, Math.max(a.y, b.y) + 14, '#93a4bd');
            }
        } else if (draw.kind === 'ray') {
            const dx = b.x - a.x, dy = b.y - a.y;
            const k = dx === 0 ? Infinity : Math.abs((dx > 0 ? w - a.x : -a.x) / dx);
            const k2 = dy === 0 ? Infinity : Math.abs((dy > 0 ? h - a.y : -a.y) / dy);
            const kk = Math.max(k || 0, k2 || 0);
            ctx.beginPath(); ctx.moveTo(a.x, a.y);
            ctx.lineTo(a.x + dx * (kk === Infinity ? 1 : kk), a.y + dy * (kk === Infinity ? 1 : kk));
            ctx.stroke();
        } else if (draw.kind === 'rect' || draw.kind === 'channel' || draw.kind === 'fib') {
            const x0 = Math.min(a.x, b.x), x1 = Math.max(a.x, b.x);
            const y0 = Math.min(a.y, b.y), y1 = Math.max(a.y, b.y);
            if (draw.kind === 'rect') {
                const ext = draw.extend || 'none';
                const left = ext === 'left' || ext === 'both' ? 0 : x0;
                const right = ext === 'right' || ext === 'both' ? w : x1;
                if (styleOf(draw).fill) { ctx.fillStyle = styleOf(draw).fill; ctx.fillRect(left, y0, right - left, y1 - y0); }
                ctx.strokeRect(left, y0, right - left, y1 - y0);
            } else if (draw.kind === 'channel') {
                ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
                const off = draw.offset || 40;
                ctx.beginPath(); ctx.moveTo(a.x, a.y + off); ctx.lineTo(b.x, b.y + off); ctx.stroke();
                if (styleOf(draw).fill) {
                    ctx.fillStyle = styleOf(draw).fill;
                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.lineTo(b.x, b.y + off); ctx.lineTo(a.x, a.y + off);
                    ctx.closePath(); ctx.fill();
                }
            } else {
                /* Fibonacci retracement between the two points. */
                FIB_LEVELS.forEach((lv) => {
                    const y = a.y + (b.y - a.y) * lv;
                    ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y);
                    ctx.strokeStyle = lv === 0 || lv === 1 ? styleOf(draw).line : 'rgba(210,153,34,.75)';
                    ctx.setLineDash(lv === 0 || lv === 1 ? [] : [5, 4]);
                    ctx.stroke();
                    const price = draw.a.p + (draw.b.p - draw.a.p) * lv;
                    label(ctx, `${(lv * 100).toFixed(1)}%  ${price.toFixed(2)}`, x1 + 4, y, '#ffd166');
                });
                ctx.setLineDash([]);
            }
        } else if (draw.kind === 'ellipse') {
            const cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
            const rx = Math.abs(b.x - a.x) / 2, ry = Math.abs(b.y - a.y) / 2;
            ctx.beginPath();
            ctx.ellipse(cx, cy, Math.max(1, rx), Math.max(1, ry), 0, 0, Math.PI * 2);
            if (styleOf(draw).fill) { ctx.fillStyle = styleOf(draw).fill; ctx.fill(); }
            ctx.stroke();
        } else if (draw.kind === 'text') {
            label(ctx, draw.text || 'text', a.x, a.y, styleOf(draw).line);
        }

        /* Axis highlighting: the drawing's own time span on the time axis, its price span on the
           price axis (permanent when the drawing asks, otherwise while it is hovered/selected). */
        const hovering = state.hoverId === draw.id;
        const wantPrice = (draw.highlight && draw.highlight.price) || hovering;
        const wantTime = (draw.highlight && draw.highlight.time) || hovering;
        if (wantTime) {
            const x0 = Math.min(a.x, b.x), x1 = Math.max(a.x, b.x);
            ctx.fillStyle = 'rgba(79,140,255,.85)';
            ctx.fillRect(x0, h - 3, Math.max(2, x1 - x0), 3);
        }
        if (wantPrice) {
            const y0 = Math.min(a.y, b.y), y1 = Math.max(a.y, b.y);
            ctx.fillStyle = 'rgba(79,140,255,.85)';
            ctx.fillRect(w - 3, y0, 3, Math.max(2, y1 - y0));
        }

        if (sel) {
            /* Endpoint handles, so a drawing is edited the way a drawing tool should be. */
            ctx.setLineDash([4, 3]);
            ctx.strokeStyle = 'rgba(255,214,102,.95)';
            ctx.lineWidth = 1;
            if (draw.kind === 'hline') ctx.strokeRect(0, a.y - 3, w, 6);
            else if (draw.kind === 'vline') ctx.strokeRect(a.x - 3, 0, 6, h);
            else if (draw.kind !== 'text') {
                const bx = Math.min(a.x, b.x) - 3, by = Math.min(a.y, b.y) - 3;
                ctx.strokeRect(bx, by, Math.abs(b.x - a.x) + 6, Math.abs(b.y - a.y) + 6);
            }
            [[a, 'a'], [b, 'b']].forEach(([pt, which]) => {
                if (draw.kind === 'hline' || draw.kind === 'vline') return;
                ctx.fillStyle = '#ffd166';
                ctx.fillRect(pt.x - 4, pt.y - 4, 8, 8);
            });
        }
        ctx.restore();
    }

    function paint() {
        const ctx = state.ctx;
        if (!ctx) return;
        const { w, h } = size();
        ctx.clearRect(0, 0, w, h);
        if (state.hidden) return;
        state.drawings.forEach((draw) => drawOne(ctx, draw));
        if (state.draft) drawOne(ctx, state.draft);
    }

    /* ── hit testing ──────────────────────────────────────────────────────── */
    function hit(x, y) {
        for (let i = state.drawings.length - 1; i >= 0; i -= 1) {
            const draw = state.drawings[i];
            const a = toPx(draw.a), b = toPx(draw.b || draw.a);
            const s = styleOf(draw);
            const tol = Math.max(6, (s.width || 2) + 4);
            if (draw.kind === 'hline' && Math.abs(y - a.y) <= tol) return { draw, handle: null };
            if (draw.kind === 'vline' && Math.abs(x - a.x) <= tol) return { draw, handle: null };
            if (draw.kind === 'text') {
                const w = (draw.text || 'text').length * 7 + 10;
                if (x >= a.x && x <= a.x + w && Math.abs(y - a.y) <= 10) return { draw, handle: null };
                continue;
            }
            if (Math.hypot(x - a.x, y - a.y) <= 8 && draw.kind !== 'hline' && draw.kind !== 'vline') return { draw, handle: 'a' };
            if (draw.b && Math.hypot(x - b.x, y - b.y) <= 8) return { draw, handle: 'b' };
            if (draw.kind === 'line' || draw.kind === 'ray' || draw.kind === 'measure' || draw.kind === 'channel') {
                if (distToSegment(x, y, a.x, a.y, b.x, b.y) <= tol) return { draw, handle: null };
                if (draw.kind === 'channel' && distToSegment(x, y, a.x, a.y + (draw.offset || 40), b.x, b.y + (draw.offset || 40)) <= tol) return { draw, handle: null };
            } else if (draw.kind === 'rect' || draw.kind === 'fib') {
                const x0 = Math.min(a.x, b.x), x1 = Math.max(a.x, b.x);
                const y0 = Math.min(a.y, b.y), y1 = Math.max(a.y, b.y);
                if (x >= x0 - tol && x <= x1 + tol && y >= y0 - tol && y <= y1 + tol) return { draw, handle: null };
            } else if (draw.kind === 'ellipse') {
                const cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
                const rx = Math.abs(b.x - a.x) / 2, ry = Math.abs(b.y - a.y) / 2;
                const v = ((x - cx) ** 2) / Math.max(1, rx ** 2) + ((y - cy) ** 2) / Math.max(1, ry ** 2);
                if (v <= 1.15) return { draw, handle: null };
            }
        }
        return null;
    }

    /* ── persistence ──────────────────────────────────────────────────────── */
    function serialize() {
        return {
            symbol: state.adapter ? state.adapter.symbol : '',
            view: state.adapter ? state.adapter.view : '',
            style: { ...state.style },
            hidden: state.hidden,
            single: state.single,
            drawings: state.drawings.map((d) => ({
                id: d.id, kind: d.kind, a: d.a, b: d.b || d.a, text: d.text || '',
                style: d.style || null, highlight: d.highlight || null,
                extend: d.extend || 'none', offset: d.offset || 40,
            })),
        };
    }
    let saveTimer = null;
    function save(immediate) {
        if (!state.adapter) return;
        state.dirty = true;
        const push = async () => {
            try {
                const res = await fetch('/api/control/drawings', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(serialize()),
                });
                const out = await res.json();
                state.dirty = !(out && out.ok);
            } catch (err) { state.dirty = true; }
        };
        if (immediate) { clearTimeout(saveTimer); void push(); return; }
        clearTimeout(saveTimer);
        saveTimer = setTimeout(() => { void push(); }, 700);
    }
    async function load() {
        if (!state.adapter) return;
        state.loading = true;
        try {
            const res = await fetch(`/api/control/drawings?symbol=${encodeURIComponent(state.adapter.symbol)}&view=${encodeURIComponent(state.adapter.view)}`);
            const out = await res.json();
            const block = out && out.block;
            state.drawings = (block && Array.isArray(block.drawings)) ? block.drawings : [];
            if (block && block.style) state.style = { ...state.style, ...block.style };
            state.hidden = !!(block && block.hidden);
            state.single = !!(block && block.single);
        } catch (err) { state.drawings = []; }
        state.loading = false;
        paint();
        refreshToolbar();
    }

    /* ── events ───────────────────────────────────────────────────────────── */
    function armOverlay(armed) {
        if (!state.canvas) return;
        state.canvas.style.pointerEvents = armed ? 'auto' : 'none';
        state.canvas.style.cursor = armed ? 'crosshair' : 'default';
    }
    function setTool(id) {
        if (!toolsById[id]) return;
        state.tool = id;
        const armed = id !== 'select';
        armOverlay(armed);
        if (!armed) { state.selected = null; state.multiIds = []; }
        paint();
        refreshToolbar();
        if (window.OFAPDRAW.onTool) window.OFAPDRAW.onTool(id);
    }
    function select(id, opts) {
        if (opts && opts.add) {
            /* T13/B12: shift-click extends the selection instead of replacing it — the old
               primary folds into the set, and the clicked drawing becomes the primary. */
            if (state.selected === id) {
                state.selected = null;
                state.multiIds = state.multiIds.filter((m) => m !== id);
            } else if (state.multiIds.indexOf(id) >= 0) {
                state.multiIds = toggleMember(state.multiIds, id);
            } else if (state.selected) {
                state.multiIds = toggleMember(state.multiIds.concat(state.selected), id);
                state.selected = id;
            } else {
                state.selected = id;
            }
        } else {
            state.selected = id;
            state.multiIds = [];
        }
        paint();
        refreshToolbar();
    }
    function remove(id) {
        const at = state.drawings.findIndex((d) => d.id === id);
        if (at < 0) return;
        const gone = state.drawings.splice(at, 1)[0];
        if (state.selected === id) state.selected = null;
        state.multiIds = state.multiIds.filter((m) => m !== id);
        pushUndo({ label: 'remove ' + gone.kind,
            undo: () => { state.drawings.splice(Math.min(at, state.drawings.length), 0, gone); } });
        paint(); save();
        refreshToolbar();
    }
    /* T13/B12: the Del key removes the WHOLE selection, in one undoable step. */
    function deleteSelection() {
        const ids = selectionIds();
        if (!ids.length) return false;
        const ats = ids.map((id) => ({ draw: state.drawings.find((d) => d.id === id),
            at: state.drawings.findIndex((d) => d.id === id) })).filter((s) => s.draw);
        state.drawings = state.drawings.filter((d) => ids.indexOf(d.id) < 0);
        if (ids.indexOf(state.selected) >= 0) state.selected = null;
        state.multiIds = state.multiIds.filter((m) => ids.indexOf(m) < 0);
        pushUndo({ label: 'remove ' + ats.length + ' marking(s)', undo: () => {
            ats.slice().sort((x, y) => x.at - y.at).forEach((s) => {
                state.drawings.splice(Math.min(s.at, state.drawings.length), 0, s.draw);
            });
        } });
        paint(); save();
        refreshToolbar();
        return true;
    }
    function selectAll() {
        if (!state.drawings.length) return false;
        state.selected = null;
        state.multiIds = state.drawings.map((d) => d.id);
        paint(); refreshToolbar();
        return true;
    }
    function clearAll() {
        if (!state.drawings.length) return;
        const gone = state.drawings.slice();
        state.drawings = [];
        state.selected = null;
        state.multiIds = [];
        pushUndo({ label: 'clear', undo: () => { state.drawings = gone; } });
        paint(); save(true);
    }
    function hideAll(flag) {
        state.hidden = flag === undefined ? !state.hidden : !!flag;
        paint(); save();
        refreshToolbar();
    }
    function duplicate(draw) {
        const copy = { ...draw, id: uid(), a: { ...draw.a }, b: { ...draw.b } };
        copy.a.p += (state.tickSize || 0.1) * 5;
        copy.b.p += (state.tickSize || 0.1) * 5;
        state.drawings.push(copy);
        pushUndo({ label: 'duplicate ' + draw.kind,
            undo: () => { state.drawings = state.drawings.filter((d) => d.id !== copy.id); } });
        paint(); save();
        return copy;
    }

    function closeMenu() {
        if (state.menu && state.menu.parentNode) state.menu.parentNode.removeChild(state.menu);
        state.menu = null;
    }
    function openContextMenu(draw, clientX, clientY) {
        closeMenu();
        const menu = document.createElement('div');
        menu.className = 'draw-menu';
        const mk = (text, fn) => {
            const b = document.createElement('button');
            b.className = 'draw-menu-item';
            b.textContent = text;
            b.addEventListener('click', (ev) => { ev.stopPropagation(); closeMenu(); fn(); });
            menu.appendChild(b);
            return b;
        };
        /* §56 carry-over: edited IN PLACE in the menu — window.prompt is not guaranteed to
           render in the frozen WebView. (No closeMenu on click: the editor lives in the menu.) */
        const textRow = document.createElement('button');
        textRow.className = 'draw-menu-item';
        textRow.textContent = draw.text ? 'Edit text…' : 'Add text…';
        textRow.addEventListener('click', (ev) => {
            ev.stopPropagation();
            if (menu.querySelector('.draw-inline-text')) return;   // one editor at a time
            inlineText(menu, draw.text || '', (text) => {
                draw.text = text;
                paint(); save(); closeMenu();
            });
        });
        menu.appendChild(textRow);
        mk(`Highlight price: ${draw.highlight && draw.highlight.price ? 'on' : 'off'}`, () => {
            draw.highlight = { ...(draw.highlight || {}), price: !(draw.highlight && draw.highlight.price) };
            paint(); save();
        });
        mk(`Highlight time: ${draw.highlight && draw.highlight.time ? 'on' : 'off'}`, () => {
            draw.highlight = { ...(draw.highlight || {}), time: !(draw.highlight && draw.highlight.time) };
            paint(); save();
        });
        if (draw.kind === 'rect') {
            mk(`Extend: ${draw.extend || 'none'}`, () => {
                const order = ['none', 'left', 'right', 'both'];
                draw.extend = order[(order.indexOf(draw.extend || 'none') + 1) % order.length];
                paint(); save();
            });
        }
        if (draw.kind === 'channel') {
            mk('Widen channel', () => { draw.offset = (draw.offset || 40) + 12; paint(); save(); });
            mk('Narrow channel', () => { draw.offset = Math.max(6, (draw.offset || 40) - 12); paint(); save(); });
        }
        mk('Undo last edit', () => undo());
        mk('Select all markings', () => selectAll());
        mk('Duplicate', () => duplicate(draw));
        mk(`Style: ${styleOf(draw).dash} · ${styleOf(draw).width}px`, () => cycleStyle(draw));
        mk('Delete', () => remove(draw.id));
        menu.style.left = `${clientX}px`;
        menu.style.top = `${clientY}px`;
        document.body.appendChild(menu);
        state.menu = menu;
    }
    function cycleStyle(draw) {
        const dashes = ['solid', 'dashed', 'dotted'];
        const widths = [1, 2, 3];
        const s = styleOf(draw);
        const nextDash = dashes[(dashes.indexOf(s.dash) + 1) % dashes.length];
        const nextWidth = widths[(widths.indexOf(s.width) + 1) % widths.length];
        draw.style = { ...(draw.style || {}), dash: nextDash, width: nextWidth };
        paint(); save();
    }

    /* §56 carry-over: the in-place text editor (draw menu + text tool). Enter/Apply commit,
       Esc/× cancel; nothing here depends on a system dialog rendering. */
    function inlineText(host, value, commit, cancel) {
        const wrap = document.createElement('div');
        wrap.className = 'draw-inline-text';
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'draw-inline-input';
        input.value = value || '';
        input.setAttribute('spellcheck', 'false');
        const apply = document.createElement('button');
        apply.type = 'button';
        apply.className = 'draw-inline-apply';
        apply.textContent = 'Apply';
        const drop = document.createElement('button');
        drop.type = 'button';
        drop.className = 'draw-inline-cancel';
        drop.textContent = '×';
        const done = (ok) => {
            if (!wrap.parentNode) return;
            wrap.remove();
            if (ok) commit(input.value);
            else if (cancel) cancel();
        };
        apply.addEventListener('click', (ev) => { ev.stopPropagation(); done(true); });
        drop.addEventListener('click', (ev) => { ev.stopPropagation(); done(false); });
        input.addEventListener('keydown', (ev) => {
            ev.stopPropagation();
            if (ev.key === 'Enter') { ev.preventDefault(); done(true); }
            else if (ev.key === 'Escape') { ev.preventDefault(); done(false); }
        });
        wrap.appendChild(input);
        wrap.appendChild(apply);
        wrap.appendChild(drop);
        host.appendChild(wrap);
        input.focus();
        if (input.select) input.select();
        return wrap;
    }

    /* ── pointer plumbing ─────────────────────────────────────────────────── */
    function bindPointer(host) {
        const canvas = state.canvas;
        /* Armed: the overlay takes the gesture and builds a figure. */
        canvas.addEventListener('mousedown', (ev) => {
            if (ev.button !== 0) return;
            const rect = canvas.getBoundingClientRect();
            const x = ev.clientX - rect.left, y = ev.clientY - rect.top;
            const spec = toolsById[state.tool];
            if (!spec || spec.needs === 'none') return;
            ev.preventDefault();
            if (spec.needs === 'text') {
                /* §56 carry-over: a floating field at the click point (Apply/Enter commits,
                   Esc/× drops the placeholder drawing) — no system dialog anywhere. */
                const data = toData(x, y);
                const draw = { id: uid(), kind: 'text', a: data, b: data, text: '' };
                state.drawings.push(draw);
                pushUndo({ label: 'add text',
                    undo: () => { state.drawings = state.drawings.filter((d) => d.id !== draw.id); } });
                select(draw.id);
                const host = (state.canvas && state.canvas.parentElement) || document.body;
                const hrect = host.getBoundingClientRect();
                const wrap = inlineText(host, '', (text) => {
                    draw.text = text;
                    paint(); save(); finishFigure();
                }, () => {
                    state.drawings = state.drawings.filter((d) => d.id !== draw.id);
                    select(null);
                    paint();
                });
                wrap.classList.add('is-float');
                wrap.style.left = Math.max(4, ev.clientX - hrect.left) + 'px';
                wrap.style.top = Math.max(4, ev.clientY - hrect.top) + 'px';
                return;
            }
            const data = toData(x, y);
            state.dragging = { x, y };
            state.draft = { id: 'draft', kind: state.tool, a: data, b: data, offset: 40,
                            extend: 'none', highlight: null };
            paint();
        });
        canvas.addEventListener('mousemove', (ev) => {
            if (!state.draft || !state.dragging) return;
            const rect = canvas.getBoundingClientRect();
            const x = ev.clientX - rect.left, y = ev.clientY - rect.top;
            if (ev.shiftKey && (state.tool === 'line' || state.tool === 'ray' || state.tool === 'channel')) {
                state.draft = snap45(state.draft, { b: toData(x, y) });
            } else {
                state.draft.b = toData(x, y);
            }
            paint();
        });
        const finish = (ev) => {
            if (!state.draft) return;
            const spec = toolsById[state.tool];
            const moved = state.dragging ? Math.hypot((ev.clientX || 0), (ev.clientY || 0)) : 0;
            const draw = { ...state.draft, id: uid() };
            if (spec.needs === 'two' || spec.needs === 'one') {
                state.drawings.push(draw);
                pushUndo({ label: 'add ' + draw.kind,
                    undo: () => { state.drawings = state.drawings.filter((d) => d.id !== draw.id); } });
                select(draw.id);
            }
            state.draft = null;
            state.dragging = null;
            save();
            finishFigure();
            paint();
        };
        canvas.addEventListener('mouseup', finish);
        canvas.addEventListener('mouseleave', (ev) => {
            if (state.draft) finish(ev);
            if (state.tip) state.tip.hidden = true;
        });

        /* Idle / select: hit-test in the capture phase so a hit claims the gesture but a miss lets
           the host pan and zoom as if the layer were not there. */
        host.addEventListener('mousedown', (ev) => {
            if (state.tool !== 'select' || ev.button !== 0) return;
            const rect = state.canvas.getBoundingClientRect();
            const x = ev.clientX - rect.left, y = ev.clientY - rect.top;
            const found = hit(x, y);
            if (!found) { if (state.selected || state.multiIds.length) { state.selected = null; state.multiIds = []; paint(); } return; }
            ev.preventDefault();
            ev.stopPropagation();
            /* T13/B12: shift-click extends the selection; a drag on a selected member moves
               the WHOLE selection. The handles still act on the grabbed drawing alone. */
            select(found.draw.id, { add: ev.shiftKey });
            const mode = found.handle ? 'handle' : 'move';
            const group = (mode === 'move' && isSelected(found.draw.id) && selectionIds().length > 1)
                ? state.drawings.filter((d) => selectionIds().indexOf(d.id) >= 0)
                : [found.draw];
            const starts = group.map((d) => ({ draw: d, a: { ...d.a }, b: { ...d.b } }));
            const startA = { ...found.draw.a }, startB = { ...found.draw.b };
            const origin = toData(x, y);
            const tip = ensureTip();
            let movedFlag = false;
            const move = (mv) => {
                movedFlag = true;
                const now = toData(mv.clientX - rect.left, mv.clientY - rect.top);
                const dt = now.t - origin.t, dp = now.p - origin.p;
                if (mode === 'move') {
                    starts.forEach((s) => {
                        s.draw.a = { t: s.a.t + dt, p: s.a.p + dp };
                        s.draw.b = { t: s.b.t + dt, p: s.b.p + dp };
                    });
                } else if (found.handle === 'a') {
                    found.draw.a = now;
                } else {
                    found.draw.b = now;
                }
                /* T13/B11: the consequence of the price under the pointer, in the paper
                   account's own unit — or an honest distance when there is no position. */
                if (tip) {
                    const px = toPx({ t: now.t, p: now.p });
                    const text = window.OFAPRISK ? OFAPRISK.text(now.p) : '';
                    if (text) {
                        tip.textContent = text;
                        tip.style.left = (px.x + 14) + 'px';
                        tip.style.top = Math.max(4, px.y - 30) + 'px';
                        tip.hidden = false;
                    } else tip.hidden = true;
                }
                paint();
            };
            const up = () => {
                document.removeEventListener('mousemove', move, true);
                document.removeEventListener('mouseup', up, true);
                if (tip) tip.hidden = true;
                if (movedFlag && mode === 'move') {
                    pushUndo({ label: 'move', undo: () => {
                        starts.forEach((s) => { s.draw.a = { ...s.a }; s.draw.b = { ...s.b }; });
                    } });
                } else if (movedFlag && mode === 'handle') {
                    const isA = found.handle === 'a';
                    pushUndo({ label: 'reshape', undo: () => {
                        if (isA) found.draw.a = { ...startA };
                        else found.draw.b = { ...startB };
                    } });
                }
                save();
            };
            document.addEventListener('mousemove', move, true);
            document.addEventListener('mouseup', up, true);
        }, true);

        host.addEventListener('mousemove', (ev) => {
            if (state.tool !== 'select') return;
            const rect = state.canvas.getBoundingClientRect();
            const found = hit(ev.clientX - rect.left, ev.clientY - rect.top);
            const id = found ? found.draw.id : null;
            if (id !== state.hoverId) { state.hoverId = id; paint(); }
        });

        host.addEventListener('contextmenu', (ev) => {
            const rect = state.canvas.getBoundingClientRect();
            const x = ev.clientX - rect.left, y = ev.clientY - rect.top;
            const found = hit(x, y);
            if (!found) return;
            ev.preventDefault();
            select(found.draw.id);
            openContextMenu(found.draw, ev.clientX, ev.clientY);
        });

        document.addEventListener('keydown', (ev) => {
            if (state.menu && ev.key === 'Escape') { closeMenu(); return; }
            const host2 = ev.target && ev.target.closest && ev.target.closest('input,textarea,select');
            if (host2) return;
            if (ev.key === 'Escape') {
                if (state.draft) { state.draft = null; paint(); return; }
                if (state.tool !== 'select') { setTool('select'); return; }
                if (state.selected || state.multiIds.length) { state.selected = null; state.multiIds = []; paint(); }
                return;
            }
            if (ev.key === 'Delete' || ev.key === 'Backspace') {
                if (selectionIds().length) {
                    ev.preventDefault();
                    deleteSelection();
                }
            }
            if ((ev.key === 'z' || ev.key === 'Z') && (ev.ctrlKey || ev.metaKey)) {
                if (state.undoStack.length) { ev.preventDefault(); undo(); }
            }
        });
        /* The tool's keys stay local (scoped to the drawing selection and the draft in progress);
           the shortcut sheet lists them through the app's one map. */
        if (window.OFAPKEYS) {
            OFAPKEYS.document([
                { keys: 'Esc', label: 'close the drawing menu, cancel the draft, drop the tool, deselect', scope: 'Drawings' },
                { keys: 'Del / Backspace', label: 'remove the selected drawing', scope: 'Drawings' },
                { keys: 'Ctrl+Z', label: 'undo the last marking edit', scope: 'Drawings' },
                { keys: 'shift+click', label: 'add a drawing to the selection (drag moves the set)', scope: 'Drawings' },
            ]);
        }
        document.addEventListener('mousedown', (ev) => {
            if (state.menu && !ev.target.closest('.draw-menu')) closeMenu();
        }, true);
    }

    function finishFigure() {
        if (state.single) setTool('select');
    }

    /* ── toolbar ──────────────────────────────────────────────────────────── */
    function buildToolbar(host) {
        const bar = document.createElement('div');
        bar.className = 'draw-toolbar';
        bar.innerHTML = KINDS.map((t) => `<button class="draw-tool" data-tool="${t.id}" title="${t.label} — ${t.hint}">${t.glyph}</button>`).join('')
            + '<span class="draw-sep"></span>'
            + '<button class="draw-tool draw-mode" data-mode="single" title="Single figure mode — return to Select after each figure">1×</button>'
            + '<button class="draw-tool draw-mode" data-mode="hide" title="Hide or show all drawings on this view">👁</button>'
            + '<button class="draw-tool draw-mode" data-mode="all" title="Select every drawing on this view — shift-click adds to the set, a drag moves it">▣</button>'
            + '<button class="draw-tool draw-mode" data-mode="undo" title="Undo the last marking edit (Ctrl+Z)">↶</button>'
            + '<button class="draw-tool draw-mode" data-mode="clear" title="Clear all drawings on this view">⌫</button>';
        bar.addEventListener('click', (ev) => {
            const tool = ev.target.closest('.draw-tool');
            if (!tool) return;
            if (tool.dataset.tool) { setTool(tool.dataset.tool); return; }
            const mode = tool.dataset.mode;
            if (mode === 'single') { state.single = !state.single; save(); refreshToolbar(); }
            if (mode === 'hide') hideAll();
            if (mode === 'clear') {
                const ok = !state.drawings.length || !window.confirm
                    || window.confirm(`Clear ${state.drawings.length} drawing(s) on this view?`);
                if (ok) clearAll();
            }
            if (mode === 'all') selectAll();
            if (mode === 'undo') undo();
        });
        host.appendChild(bar);
        state.toolbar = bar;
        return bar;
    }
    function refreshToolbar() {
        if (!state.toolbar) return;
        state.toolbar.querySelectorAll('.draw-tool[data-tool]').forEach((b) => {
            b.classList.toggle('on', b.dataset.tool === state.tool);
        });
        const single = state.toolbar.querySelector('[data-mode="single"]');
        if (single) single.classList.toggle('on', !!state.single);
        const hide = state.toolbar.querySelector('[data-mode="hide"]');
        if (hide) hide.classList.toggle('on', !!state.hidden);
        const undoBtn = state.toolbar.querySelector('[data-mode="undo"]');
        if (undoBtn) undoBtn.classList.toggle('dim', !state.undoStack.length);
    }

    /* ── attach ───────────────────────────────────────────────────────────── */
    function attach(host, adapter) {
        if (!host || !adapter) return null;
        state.host = host;
        state.adapter = adapter;
        state.tickSize = Number(adapter.tickSize) || 0.1;
        const canvas = document.createElement('canvas');
        canvas.className = 'draw-layer';
        host.appendChild(canvas);
        state.canvas = canvas;
        state.ctx = canvas.getContext('2d');
        buildToolbar(host);
        resize();
        bindPointer(host);
        setTool('select');
        if (typeof adapter.subscribe === 'function') adapter.subscribe(() => { resize(); paint(); });
        void load();
        return canvas;
    }
    function resize() {
        const { w, h } = size();
        const c = state.canvas;
        if (!c) return;
        const dpr = window.devicePixelRatio || 1;
        c.style.width = `${w}px`;
        c.style.height = `${h}px`;
        c.width = Math.max(1, Math.round(w * dpr));
        c.height = Math.max(1, Math.round(h * dpr));
        const ctx = c.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        paint();
    }

    root.OFAPDRAW = {
        TOOLS: KINDS, state, attach, resize, paint, setTool, select, remove, clearAll, hideAll,
        duplicate, save, load, serialize,
        undo, deleteSelection, selectAll, isSelected,
        undoDepth: () => state.undoStack.length,
        get selected() { return state.selected; },
        get multiIds() { return state.multiIds.slice(); },
        get drawings() { return state.drawings; },
    };

    /* §72: a window or display-scale change may have moved the host box; re-fit and repaint from
       the same entry point the adapter's subscribe uses. (This layer already sizes its backing
       store by dpr — the listener keeps it current when nothing else fires.) */
    if (typeof document !== 'undefined') {
        document.addEventListener('ofap:relayout', () => {
            try { if (state.canvas) resize(); } catch (e) { /* the layer's own path reports its faults */ }
        });
    }
})(typeof globalThis !== 'undefined' ? globalThis : this);
