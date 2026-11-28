#!/usr/bin/env python3
"""diagramer.py - build a 3-tab diagram block (File explorer, Sequence, UML) from a JSON spec.

Usage:
  python diagramer.py spec.json -o fragment.html            # HTML fragment
  python diagramer.py spec.json --standalone -o page.html   # fragment in a dark page
  python diagramer.py spec.json --insert-into page-spec.json --after glossary
      # adds a section to a mayo-interactive-understanding-html spec

Spec (all three keys optional; a missing key drops that tab):
{
  "id": "dg",                       # unique id prefix, default "dg"
  "heading": "Where the change lives", "lead": "Three views of the same PR.",
  "title": "PR #12 - short name", # only used by --standalone
  "files": [ {"path": "Host/Packages/x/A.cs", "status": "A|M|D", "add": 5, "del": 0, "note": "text for the instant tooltip, may be several lines (use \\n)"} ],
  "tab_names": {"files": "...", "sequence": "...", "uml": "..."},   # optional, for a non-English page
  "files_note": "Unity .meta files are hidden.",
  "sequence": [ {                   # one scene per entry
      "title": "Store not ready",
      "lanes": [ {"key": "iap", "name": "IapPurchaseProcessor", "file": "IapPurchaseProcessor.cs", "status": "mod|new|ext"} ],
      "msgs": [ ["iap", "iap", "label", "keep|add|del|dash"],   # from, to, label, style; from == to is a self call
                ["note", "text"] ],                                 # full width note
      "caption": "optional text under the scene" } ],
  "uml": { "boxes": [ {"key": "A", "col": 0, "row": 0, "status": "new|mod|ext", "stereo": "class",
                       "name": "SeasonPass", "path": "Runtime/SeasonPass.cs",
                       "bases": ["MonoBehaviour"],   # optional: base types that are NOT boxes in this diagram
                       "members": ["+added member", "~changed member", "-removed member", " unchanged member"] } ],
           "edges": [ {"from": "A", "to": "B", "kind": "inh|real|assoc|dep", "label": "uses"} ],
           "caption": "optional" }
}
A member text may contain \\n. The next lines are indented under the same mark.
"""
import argparse, heapq, html, json, os, random, sys
E = html.escape
COL = {"new": ("#34d399", "rgba(6,78,59,.35)"), "mod": ("#fbbf24", "rgba(120,53,15,.30)"), "ext": ("#94a3b8", "rgba(30,41,59,.45)")}
MARK = {"+": "#34d399", "~": "#fbbf24", "-": "#fb7185", " ": "#64748b"}
STATUS_WORD = {"new": "new", "mod": "modified", "ext": "outside diff"}
HINT = "Drag to move. Use the + and \u2212 buttons to zoom (Ctrl or \u2318 + wheel also works)."
CHAR_W = 6.2  # width of one monospace character at 10px, with a small margin

# ---------------------------------------------------------------- explorer
def explorer(files, note):
    root = {"d": {}, "f": []}
    for f in files:
        parts = f["path"].split("/"); n = root
        for x in parts[:-1]:
            n = n["d"].setdefault(x, {"d": {}, "f": []})
        n["f"].append((parts[-1], f.get("status", "M"), f.get("add", 0), f.get("del", 0), f.get("note", "")))
    def count(n): return len(n["f"]) + sum(count(c) for c in n["d"].values())
    def render(n, name=None):
        # Merge folders that have one child folder and no files (like VS Code).
        while name is not None and not n["f"] and len(n["d"]) == 1:
            (k, c), = n["d"].items(); name += "/" + k; n = c
        out = ""
        for fname, st, a, d, nt in sorted(n["f"]):
            head = f"{fname}  +{a} -{d}"
            ic = {"A": "+", "D": "-"}.get(st, "~")
            stat = (f'<i class="a">+{a}</i>' if a else "") + (f'<i class="d">-{d}</i>' if d else "")
            if nt:
                # The tooltip is drawn by the inline script (instant, multi-line, not clipped by the tree).
                out += (f'<li class="dg-file dg-{st} dg-has-note" tabindex="0" data-head="{E(head)}" data-note="{E(nt)}">'
                        f'<span class="ic">{ic}</span><span class="nm">{E(fname)}<b class="ni" aria-hidden="true">i</b></span><span class="st">{stat}</span></li>')
            else:
                out += f'<li class="dg-file dg-{st}" title="{E(head)}"><span class="ic">{ic}</span><span class="nm">{E(fname)}</span><span class="st">{stat}</span></li>'
        for k in sorted(n["d"]):
            out += render(n["d"][k], k)
        if name is None:
            return out
        return f'<li><details open><summary><span class="fo"></span>{E(name)}<em>{count(n)}</em></summary><ul>{out}</ul></details></li>'
    ta = sum(f.get("add", 0) for f in files); td = sum(f.get("del", 0) for f in files)
    hint = " Hover or tap a file with a blue i to read its note." if any(f.get("note") for f in files) else ""
    return (f'<div class="dg-meta">{len(files)} files, +{ta} -{td}.{hint}</div>'
            f'<div class="dg-tree"><ul>{render(root)}</ul></div>'
            f'<p class="dg-cap"><b class="A">+ green</b> added, <b class="M">~ amber</b> modified, <b class="D">- red</b> deleted. '
            f'The number after a folder counts changed files. Single-child folders are merged. {E(note or "")}</p>')

# ---------------------------------------------------------------- zoom wrapper
def zoomable(svg, W, H, title=""):
    """A pan/zoom frame around one svg. The buttons sit at the bottom right. The JS is in ZOOM_JS."""
    return (f'<div class="dg-zoom" style="aspect-ratio:{W:.0f}/{H:.0f}">{svg}<div class="dg-zt">{E(title)}</div>'
            '<div class="dg-zc"><button type="button" class="dg-zb" data-z="out" aria-label="Zoom out">\u2212</button>'
            '<button type="button" class="dg-zb" data-z="reset" aria-label="Fit to window">\u2922</button>'
            '<button type="button" class="dg-zb" data-z="in" aria-label="Zoom in">+</button>'
            '<button type="button" class="dg-zb dg-zf" data-z="full" aria-label="Full screen" title="Full screen (Esc to close)">\u26F6</button></div></div>')

# ---------------------------------------------------------------- sequence
def scene(sc, uid):
    lanes, msgs = sc["lanes"], sc["msgs"]
    lane_w = max(190, max(len(l["name"]) for l in lanes) * 7 + 34)  # keep long class names inside the box
    idx = {l["key"]: i for i, l in enumerate(lanes)}
    need = 0  # a label must fit between its two lifelines (a self call: between its lifeline and the next)
    for m in msgs:
        if m[0] == "note": continue
        lw = len(m[2]) * 6.4 + 30
        span = abs(idx[m[0]] - idx[m[1]])
        need = max(need, (lw + 56) if span == 0 else lw / span)
    W = max(900, lane_w * len(lanes) + 60, int(need * len(lanes) + 60))
    for _ in range(4):  # a self call on a right-hand lane must not run off the picture
        gap = (W - 60) / len(lanes)
        xs = {l["key"]: 30 + gap * i + gap / 2 for i, l in enumerate(lanes)}
        reach = max([xs[m[0]] + 54 + len(m[2]) * 6.4 + 20 for m in msgs if m[0] != "note" and m[0] == m[1]] + [0])
        if reach <= W: break
        W = int(reach) + 10
    step, top = 46, 100; H = top + 30 + step * (len(msgs) + 1) + 20  # room for the zoom buttons
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{E(sc.get("title", "sequence diagram"))}">',
         f'<defs><marker id="{uid}ah" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><polygon points="0 0,10 4,0 8" fill="#cbd5e1"/></marker>'
         f'<marker id="{uid}ahn" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><polygon points="0 0,10 4,0 8" fill="#34d399"/></marker>'
         f'<marker id="{uid}ahd" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><polygon points="0 0,10 4,0 8" fill="#fb7185"/></marker></defs>']
    for l in lanes:
        x = xs[l["key"]]; w = gap - 14; st = l.get("status", "mod"); c = COL[st][0]
        dash = ' stroke-dasharray="5,4"' if st == "ext" else ""
        o.append(f'<rect x="{x-w/2}" y="12" width="{w}" height="62" rx="6" fill="#0b1220" stroke="{c}" stroke-width="1.5"{dash}/>')
        o.append(f'<text x="{x}" y="34" text-anchor="middle" class="ln">{E(l["name"])}</text>')
        o.append(f'<text x="{x}" y="52" text-anchor="middle" class="lp">{E(l.get("file", ""))}</text>')
        o.append(f'<text x="{x}" y="66" text-anchor="middle" class="ls">{STATUS_WORD[st]}</text>')
        o.append(f'<line x1="{x}" y1="74" x2="{x}" y2="{H-10}" stroke="#334155" stroke-dasharray="4,4"/>')
    n = 0
    for i, m in enumerate(msgs):
        y = top + 30 + step * i + 10
        if m[0] == "note":
            o.append(f'<rect x="30" y="{y-16}" width="{W-60}" height="30" rx="5" fill="rgba(251,146,60,.14)" stroke="#fb923c" stroke-dasharray="3,3"/>')
            o.append(f'<text x="{W/2}" y="{y+3}" text-anchor="middle" class="nt">{E(m[1])}</text>')
            continue
        a, b, label = m[0], m[1], m[2]; sty = m[3] if len(m) > 3 else "keep"; n += 1
        col = {"add": "#34d399", "del": "#fb7185"}.get(sty, "#cbd5e1")
        mk = {"add": "ahn", "del": "ahd"}.get(sty, "ah"); dsh = ' stroke-dasharray="6,4"' if sty in ("del", "dash") else ""
        if a == b:
            x = xs[a]
            o.append(f'<path d="M{x},{y-10} h46 v18 h-46" fill="none" stroke="{col}" stroke-width="1.5"{dsh} marker-end="url(#{uid}{mk})"/>')
            o.append(f'<text x="{x+54}" y="{y+2}" class="ml" fill="{col}">{n}. {E(label)}</text>')
        else:
            o.append(f'<line x1="{xs[a]}" y1="{y}" x2="{xs[b]}" y2="{y}" stroke="{col}" stroke-width="1.5"{dsh} marker-end="url(#{uid}{mk})"/>')
            o.append(f'<text x="{(xs[a]+xs[b])/2}" y="{y-6}" text-anchor="middle" class="ml" fill="{col}">{n}. {E(label)}</text>')
    o.append("</svg>")
    cap = f'<p class="dg-cap">{E(sc["caption"])}</p>' if sc.get("caption") else ""
    return f'<h4>{E(sc.get("title", ""))}</h4>{zoomable("".join(o), W, H, sc.get("title", "Sequence"))}{cap}'

def sequence(scenes, uid):
    legend = ('<p class="dg-cap"><b class="A">green</b> = added call, <b class="D">red dashed</b> = call before the change, '
              'white dashed = hop whose call site is not in the diff. ' + HINT + '</p>')
    return "".join(scene(s, f"{uid}s{i}") for i, s in enumerate(scenes)) + legend


# ---------------------------------------------------------------- uml edge router
CELL, CLEAR, TURN, STUB = 10, 14, 7, 2  # grid size, space kept around a box, turn cost, stub length in cells
DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]  # right, down, left, up

def _ports(b):
    """Candidate ports of a box: (x, y, outward direction index), snapped to the grid."""
    x, y, w, h = b["x"], b["y"], b["w"], b["h"]; out = []
    snap = lambda v: round(v / CELL) * CELL
    for f in (0.25, 0.5, 0.75):
        px = snap(x + w * f)
        out.append((px, y, 3)); out.append((px, y + h, 1))
    for f in (0.3, 0.55, 0.8):
        py = snap(y + 20 + (h - 32) * f)
        out.append((x + w, py, 0)); out.append((x, py, 2))
    return out

def _route_once(B, edges, W, H, order):
    """Orthogonal routes that never enter a box. One Dijkstra per edge over a coarse grid.
    Edges are routed in the given order (the first one gets the best path). Returns routes in edge order."""
    nx, ny = int(W // CELL) + 2, int(H // CELL) + 2
    blocked = set()
    for b in B.values():
        # "+ 1" on the low side keeps top and left ports usable: the stub end (STUB cells out) must not fall in a blocked cell.
        for cx in range(int((b["x"] - CLEAR) // CELL) + 1, int((b["x"] + b["w"] + CLEAR) // CELL) + 1):
            for cy in range(int((b["y"] - CLEAR) // CELL) + 1, int((b["y"] + b["h"] + CLEAR) // CELL) + 1):
                blocked.add((cx, cy))
    used_h, used_v, used_ports = set(), set(), []
    def stub_end(p):
        px, py, d = p; dx, dy = DIRS[d]
        return round((px + dx * STUB * CELL) / CELL), round((py + dy * STUB * CELL) / CELL)
    def port_pen(key, p):  # keep two edges off the same spot of a box side
        return sum(40 for k, q in used_ports if k == key and abs(q[0] - p[0]) + abs(q[1] - p[1]) < 24)
    routes = {}
    for idx in order:
        e = edges[idx]
        a, b = B[e["from"]], B[e["to"]]
        starts = {}
        for p in _ports(a):
            c = stub_end(p)
            if c not in blocked: starts[(c, p[2])] = (p, STUB + port_pen(a["key"], p))
        goals = {}
        for p in _ports(b):
            c = stub_end(p)
            if c not in blocked: goals.setdefault(c, []).append((p, port_pen(b["key"], p)))
        heap, dist, prev, tick = [], {}, {}, 0
        for (c, d), (p, pen) in starts.items():
            st = (c, d); dist[st] = pen; prev[st] = None
            heapq.heappush(heap, (pen, tick, st)); tick += 1
        best = None
        while heap:
            cost, _, st = heapq.heappop(heap)
            if st == "END": break
            if isinstance(st, tuple) and st[0] == "goal":
                best = st; break
            if cost > dist.get(st, 1e18): continue
            (cx, cy), d = st
            if (cx, cy) in goals:
                for p, pen in goals[(cx, cy)]:
                    inward = (p[2] + 2) % 4
                    total = cost + pen + (0 if d == inward else TURN)
                    g = ("goal", st, p)
                    if total < dist.get(g, 1e18):
                        dist[g] = total; prev[g] = st; heapq.heappush(heap, (total, tick, g)); tick += 1
            for nd in range(4):
                if nd == (d + 2) % 4: continue
                dx, dy = DIRS[nd]; n = (cx + dx, cy + dy)
                if not (0 <= n[0] < nx and 0 <= n[1] < ny) or n in blocked: continue
                step = 1 + (TURN if nd != d else 0)
                if nd % 2 == 0: step += (30 if n in used_h else 0) + (20 if n in used_v else 0)
                else: step += (30 if n in used_v else 0) + (20 if n in used_h else 0)
                ns = (n, nd)
                if cost + step < dist.get(ns, 1e18):
                    dist[ns] = cost + step; prev[ns] = st; heapq.heappush(heap, (cost + step, tick, ns)); tick += 1
        if best is None:
            sys.exit(f"diagramer: no clear route for edge {e['from']} -> {e['to']}. Move a box to another col or row.")
        cells, st = [], best[1]
        while st is not None:
            cells.append(st); st = prev[st]
        cells.reverse()
        sp = starts[cells[0]][0]; gp = best[2]
        pts = [(sp[0], sp[1])] + [(c[0][0] * CELL, c[0][1] * CELL) for c in cells] + [(gp[0], gp[1])]
        # orthogonal: first and last point share a coordinate with the stub end
        pts[1] = (sp[0], pts[1][1]) if sp[2] % 2 else (pts[1][0], sp[1])
        pts[-2] = (gp[0], pts[-2][1]) if gp[2] % 2 else (pts[-2][0], gp[1])
        clean = []
        for pt in pts:  # drop repeated points and points in the middle of a straight line
            if clean and clean[-1] == pt: continue
            if len(clean) > 1 and ((clean[-2][0] == clean[-1][0] == pt[0]) or (clean[-2][1] == clean[-1][1] == pt[1])): clean[-1] = pt
            else: clean.append(pt)
        for (x1, y1), (x2, y2) in zip(clean, clean[1:]):
            for cx in range(int(min(x1, x2) // CELL), int(max(x1, x2) // CELL) + 1):
                for cy in range(int(min(y1, y2) // CELL), int(max(y1, y2) // CELL) + 1):
                    (used_h if y1 == y2 else used_v).add((cx, cy))
        used_ports.append((a["key"], sp)); used_ports.append((b["key"], gp))
        routes[idx] = (e, clean)
    return [routes[i] for i in range(len(edges))]

def _seg_hits(p, q, r, pad=0):
    (x1, y1), (x2, y2) = p, q
    rx1, ry1, rx2, ry2 = r[0] - pad, r[1] - pad, r[0] + r[2] + pad, r[1] + r[3] + pad
    return max(min(x1, x2), rx1) < min(max(x1, x2), rx2) and max(min(y1, y2), ry1) < min(max(y1, y2), ry2) \
        or (min(x1, x2) == max(x1, x2) and rx1 < x1 < rx2 and min(y1, y2) < ry2 and max(y1, y2) > ry1) \
        or (min(y1, y2) == max(y1, y2) and ry1 < y1 < ry2 and min(x1, x2) < rx2 and max(x1, x2) > rx1)

def place_label(text, pts, B, placed):
    """Put a label beside the longest segment where it touches no box and no other label."""
    lw, lh = len(text) * 5.8 + 6, 13
    segs = sorted(zip(pts, pts[1:]), key=lambda s: -(abs(s[0][0] - s[1][0]) + abs(s[0][1] - s[1][1])))
    for (x1, y1), (x2, y2) in segs:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        cands = [(mx, my - 6, "middle"), (mx, my + 14, "middle")] if y1 == y2 else [(mx + 8, my + 4, "start"), (mx - 8, my + 4, "end")]
        for x, y, anchor in cands:
            left = x - lw / 2 if anchor == "middle" else (x if anchor == "start" else x - lw)
            r = (left, y - lh + 2, lw, lh)
            if any(_rect_hit(r, (b["x"], b["y"], b["w"], b["h"])) for b in B.values()): continue
            if any(_rect_hit(r, q) for q in placed): continue
            placed.append(r); return x, y, anchor
    x, y, anchor = (segs[0][0][0] + segs[0][1][0]) / 2, (segs[0][0][1] + segs[0][1][1]) / 2 - 6, "middle"
    placed.append((x - lw / 2, y - lh + 2, lw, lh)); return x, y, anchor

def _rect_hit(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]

# ---------------------------------------------------------------- layout review (fewer crossing arrows)
def _tangles(routes):
    """Return (overlaps, crossings): lists of edge-name pairs. Overlap = two edges share a stretch of line. Crossing = two edges cross at a right angle."""
    segs = [(f"{e['from']}->{e['to']}", list(zip(p, p[1:]))) for e, p in routes]
    over, cross = [], []
    for i, (na, sa) in enumerate(segs):
        for nb, sb in segs[i + 1:]:
            for p, q in sa:
                for u, v in sb:
                    ha, hb = p[1] == q[1], u[1] == v[1]
                    if ha != hb:
                        (h1, h2), (v1, v2) = ((p, q), (u, v)) if ha else ((u, v), (p, q))
                        if min(h1[0], h2[0]) < v1[0] < max(h1[0], h2[0]) and min(v1[1], v2[1]) < h1[1] < max(v1[1], v2[1]):
                            cross.append((na, nb))
                    elif ha and p[1] == u[1] and min(max(p[0], q[0]), max(u[0], v[0])) > max(min(p[0], q[0]), min(u[0], v[0])):
                        over.append((na, nb))
                    elif not ha and p[0] == u[0] and min(max(p[1], q[1]), max(u[1], v[1])) > max(min(p[1], q[1]), min(u[1], v[1])):
                        over.append((na, nb))
    return over, cross

def _cost(routes):
    over, cross = _tangles(routes)
    bends = sum(len(p) - 2 for _, p in routes)
    length = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for _, p in routes for a, b in zip(p, p[1:]))
    return len(over) * 1000 + len(cross) * 50 + bends * 3 + length / 20

def route_edges(B, edges, W, H, tries=10):
    """Route all edges. Try several routing orders and keep the one with the fewest overlaps and crossings."""
    n = len(edges); ids = list(range(n))
    mid = lambda k: (B[k]["x"] + B[k]["w"] / 2, B[k]["y"] + B[k]["h"] / 2)
    span = lambda i: abs(mid(edges[i]["from"])[0] - mid(edges[i]["to"])[0]) + abs(mid(edges[i]["from"])[1] - mid(edges[i]["to"])[1])
    orders = [ids, ids[::-1], sorted(ids, key=span), sorted(ids, key=span, reverse=True)]
    rng = random.Random(7)
    for _ in range(tries):
        o = ids[:]; rng.shuffle(o); orders.append(o)
    best = None
    for o in orders:
        r = _route_once(B, edges, W, H, o); c = _cost(r)
        if best is None or c < best[0]: best = (c, r)
        if c < 50: break  # no overlap and no crossing: cannot do better on tangles
    return best[1]

def _layout(B):
    """Set x and y of every box from its col and row. Returns W, H, row tops and row heights."""
    ncol = max(b["col"] for b in B.values()) + 1; nrow = max(b["row"] for b in B.values()) + 1
    GX, GY, PAD = 130, 100, 60
    cw = [max([b["w"] for b in B.values() if b["col"] == c] or [0]) for c in range(ncol)]
    rh = [max([b["h"] for b in B.values() if b["row"] == r] or [0]) for r in range(nrow)]
    cx = [PAD + sum(cw[:c]) + GX * c for c in range(ncol)]
    ry = [PAD + sum(rh[:r]) + GY * r for r in range(nrow)]
    for b in B.values():
        b["x"] = cx[b["col"]] + (cw[b["col"]] - b["w"]) / 2; b["y"] = ry[b["row"]]
    return cx[-1] + cw[-1] + PAD, ry[-1] + rh[-1] + PAD + 40, ry, rh

def review_layout(B, edges, bands, routes):
    """After routing: report arrows that still cross or overlap, and look for a box move that removes them.
    A move keeps the box in its band, off other boxes, and keeps every parent above its child."""
    over, cross = _tangles(routes)
    if not over and not cross: return
    for na, nb in over: print(f"diagramer WARNING: arrows {na} and {nb} share a line", file=sys.stderr)
    for na, nb in cross: print(f"diagramer NOTE: arrows {na} and {nb} cross", file=sys.stderr)
    names = {n for pair in over + cross for n in pair}
    involved = {k for e in edges if f"{e['from']}->{e['to']}" in names for k in (e["from"], e["to"])}
    nrow = max(b["row"] for b in B.values()) + 1; ncol = max(b["col"] for b in B.values()) + 1
    band_of = lambda r: next((i for i, bd in enumerate(bands) if bd["rows"][0] <= r <= bd["rows"][1]), None)
    found = []
    for key in sorted(involved):
        b0 = B[key]; best = None
        rows = range(bands[band_of(b0["row"])]["rows"][0], bands[band_of(b0["row"])]["rows"][1] + 1) if bands and band_of(b0["row"]) is not None else range(nrow)
        for c in range(ncol + 1):
            for r in rows:
                if (c, r) == (b0["col"], b0["row"]) or any(o is not b0 and o["col"] == c and o["row"] == r for o in B.values()): continue
                T = {k: dict(v) for k, v in B.items()}; T[key].update(col=c, row=r)
                if any(T[e["to"]]["row"] >= T[e["from"]]["row"] for e in edges if e.get("kind") in ("inh", "real")): continue
                try:
                    W2, H2, _, _ = _layout(T); r2 = _route_once(T, edges, W2, H2, list(range(len(edges))))
                except SystemExit: continue
                cst = _cost(r2); o2, c2 = _tangles(r2)
                if len(o2) + len(c2) < len(over) + len(cross) and (best is None or cst < best[0]): best = (cst, c, r, len(c2), len(o2))
        if best: found.append((best[0], key, best[1], best[2], best[3], best[4]))
    for cst, key, c, r, nc, no in sorted(found)[:3]:
        print(f"diagramer HINT: move {B[key]['name']} to col {c}, row {r}: crossings {len(cross)} -> {nc}, shared lines {len(over)} -> {no}", file=sys.stderr)

def check_uml(B, routes, labels):
    """Warn on stderr when anything overlaps: an edge over a box, a label over a box or another label."""
    for e, pts in routes:
        for b in B.values():
            r = (b["x"], b["y"], b["w"], b["h"])
            for p, q in zip(pts, pts[1:]):
                if _seg_hits(p, q, r):
                    print(f"diagramer WARNING: edge {e['from']}->{e['to']} crosses box {b['key']}", file=sys.stderr)
    for i, r in enumerate(labels):
        for b in B.values():
            if _rect_hit(r, (b["x"], b["y"], b["w"], b["h"])):
                print(f"diagramer WARNING: an edge label overlaps box {b['key']}", file=sys.stderr)
        for q in labels[i + 1:]:
            if _rect_hit(r, q): print("diagramer WARNING: two edge labels overlap", file=sys.stderr)

def check_hierarchy(B, edges):
    """Warn on stderr when a parent type is not on a row above its child (inh and real edges)."""
    for e in edges:
        if e.get("kind") not in ("inh", "real"): continue
        child, parent = B[e["from"]], B[e["to"]]
        if parent["row"] >= child["row"]:
            print(f"diagramer WARNING: {parent['name']} ({'extends' if e['kind'] == 'inh' else 'implements'} target) is on row {parent['row']}, "
                  f"not above {child['name']} (row {child['row']}). Give the parent a lower row.", file=sys.stderr)

# ---------------------------------------------------------------- uml
def uml(spec, uid):
    boxes = spec["boxes"]; B = {}
    names = {x["key"]: x["name"] for x in boxes}
    def bases_text(b):
        """': A, B, C' from the box's own "bases" (types outside the diagram), then its extends, then its implements edges."""
        out = list(b.get("bases", []))
        for kind in ("inh", "real"):
            out += [names[e["to"]] for e in spec.get("edges", []) if e["from"] == b["key"] and e.get("kind") == kind and names[e["to"]] not in out]
        return ": " + ", ".join(out) if out else ""
    for b in boxes:
        lines = []
        for m in b.get("members", []):
            mark, text = m[0], m[1:]
            for i, part in enumerate(text.split("\n")):
                lines.append((mark if i == 0 else " ", part))
        bs = bases_text(b)
        longest = max([len(t) for _, t in lines] + [len(b["name"]) * 1.2, len(b.get("path", "")) * 0.9, len(bs) * 0.9, 30])
        w = b.get("w") or max(300, int(longest * CHAR_W + 44))
        h = 62 + (len(lines) * 17 + 8 if lines else 6) + (16 if bs else 0)
        B[b["key"]] = dict(b, lines=lines, w=w, h=h, bases_txt=bs)
    W, H, ry, rh = _layout(B)
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="UML class diagram">',
         f'<defs><marker id="{uid}tri" markerWidth="14" markerHeight="12" refX="13" refY="6" orient="auto"><polygon points="1 1,13 6,1 11" fill="#0b1220" stroke="#94a3b8" stroke-width="1.3"/></marker>'
         f'<marker id="{uid}open" markerWidth="12" markerHeight="10" refX="11" refY="5" orient="auto"><polyline points="1 1,11 5,1 9" fill="none" stroke="#94a3b8" stroke-width="1.4"/></marker></defs>']
    for bd in spec.get("bands", []):  # optional layer bands: {"label": "...", "rows": [first, last]}, drawn behind the boxes
        r0, r1 = bd["rows"]; top, bot = ry[r0] - 34, ry[r1] + rh[r1] + 26
        o.append(f'<rect x="6" y="{top}" width="{W - 12}" height="{bot - top}" rx="8" fill="rgba(148,163,184,.05)" stroke="rgba(148,163,184,.18)" stroke-dasharray="3,4"/>')
        o.append(f'<text x="{W - 18}" y="{top + 16}" text-anchor="end" class="ls" style="letter-spacing:.08em">{E(bd["label"].upper())}</text>')
    for b in B.values():
        st = b.get("status", "mod"); c, fill = COL[st]; x, y, w, h = b["x"], b["y"], b["w"], b["h"]
        dash = ' stroke-dasharray="5,4"' if st == "ext" else ""
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#0b1220"/>')
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{c}" stroke-width="1.6"{dash}/>')
        o.append(f'<text x="{x+w/2}" y="{y+16}" text-anchor="middle" class="stereo">{E("«" + b.get("stereo", "class") + "»")}</text>')
        o.append(f'<text x="{x+w/2}" y="{y+34}" text-anchor="middle" class="cname">{E(b["name"])}</text>')
        off = 16 if b["bases_txt"] else 0
        if off:
            o.append(f'<text x="{x+w/2}" y="{y+50}" text-anchor="middle" class="mem" style="fill:#c4b5fd">{E(b["bases_txt"])}</text>')
        o.append(f'<text x="{x+w/2}" y="{y+50+off}" text-anchor="middle" class="path">{E(b.get("path", ""))}</text>')
        if b["lines"]:
            o.append(f'<line x1="{x}" y1="{y+58+off}" x2="{x+w}" y2="{y+58+off}" stroke="{c}" stroke-opacity=".5"/>')
        for i, (mk, t) in enumerate(b["lines"]):
            ty = y + 76 + off + i * 17
            o.append(f'<text x="{x+10}" y="{ty}" class="mem" fill="{MARK[mk]}">{E(mk)}</text>')
            o.append(f'<text x="{x+24}" y="{ty}" class="mem" fill="{"#cbd5e1" if mk != " " else "#64748b"}">{E(t)}</text>')
    routes = route_edges(B, spec.get("edges", []), W, H)
    labels = []
    for e, pts in routes:
        kind = e.get("kind", "dep")
        d = "M" + " L".join(f"{px},{py}" for px, py in pts)
        dash = ' stroke-dasharray="6,4"' if kind in ("real", "dep") else ""
        mk = "tri" if kind in ("inh", "real") else "open"
        o.append(f'<path d="{d}" fill="none" stroke="#94a3b8" stroke-width="1.4"{dash} marker-end="url(#{uid}{mk})"/>')
        if e.get("label"):
            labels.append((e["label"], pts))
    placed = []
    for text, pts in labels:  # drawn last, with a halo, so no line hides a label
        x, y, anchor = place_label(text, pts, B, placed)
        o.append(f'<text x="{x}" y="{y}" class="elabel" text-anchor="{anchor}">{E(text)}</text>')
    check_uml(B, routes, placed)
    check_hierarchy(B, spec.get("edges", []))
    review_layout(B, spec.get("edges", []), spec.get("bands", []), routes)
    o.append("</svg>")
    leg = ('<p class="dg-cap"><b class="A">+</b> added member, <b class="M">~</b> changed, <b class="D">-</b> removed. '
           'Green box = new type, amber = modified, dashed = outside the diff. Solid arrow + hollow triangle = extends, '
           'dashed + triangle = implements, dashed arrow = uses or creates, solid arrow = holds. The blue line in each box is the file. ' + HINT + '</p>')
    cap = f'<p class="dg-cap">{E(spec["caption"])}</p>' if spec.get("caption") else ""
    return f'{zoomable("".join(o), W, H, "UML classes")}{leg}{cap}'

# ---------------------------------------------------------------- page
CSS = """
.dg{margin:1.2rem 0;font:13px/1.5 ui-monospace,Menlo,Consolas,monospace;color:#e2e8f0}
.dg input{position:absolute;opacity:0;pointer-events:none}
.dg-tabs{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
.dg-tabs label{border:1px solid #334155;border-radius:6px;padding:6px 14px;cursor:pointer;background:#0f172a;color:#cbd5e1}
.dg-p{display:none}
.dg h4{margin:14px 0 6px;font-size:13px;color:#cbd5e1}
.dg-meta,.dg-cap{color:#94a3b8;font-size:12px;line-height:1.6;margin:6px 0}
.dg-cap b.A{color:#34d399}.dg-cap b.M{color:#fbbf24}.dg-cap b.D{color:#fb7185}
.dg-tree{background:#0b1220;border:1px solid #1e293b;border-radius:8px;padding:8px 6px;overflow-x:auto;line-height:22px}
.dg-tree ul{list-style:none;margin:0 0 0 7px;padding-left:16px;border-left:1px solid #1e293b}.dg-tree>ul{padding-left:0;border:0;margin-left:0}
.dg-tree summary{cursor:pointer;color:#cbd5e1;list-style:none;white-space:nowrap;border-radius:4px}
.dg-tree summary::-webkit-details-marker{display:none}.dg-tree summary::before{content:"\\25B8";display:inline-block;width:14px;color:#64748b}
.dg-tree details[open]>summary::before{content:"\\25BE"}
.dg-tree summary:hover,.dg-file:hover{background:#111c33}
.dg-tree .fo{display:inline-block;width:14px;height:10px;margin-right:6px;background:#38bdf8;border-radius:2px;opacity:.85;vertical-align:-1px}
.dg-tree summary em{font-style:normal;color:#64748b;font-size:11px;margin-left:8px}
.dg-file{display:flex;align-items:center;white-space:nowrap;padding-left:14px;border-radius:4px}
.dg-file .ic{width:14px;text-align:center;font-weight:700;margin-right:6px}.dg-file .nm{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis}.dg-has-note{cursor:help;outline:none}.dg-has-note:focus-visible{box-shadow:0 0 0 1px #22d3ee}.dg-file .ni{display:inline-block;width:14px;height:14px;margin-left:8px;border:1px solid #22d3ee;border-radius:50%;color:#22d3ee;font:italic 700 10px/13px Georgia,serif;text-align:center;vertical-align:1px}
.dg-tip{position:fixed;z-index:1100;display:none;max-width:min(440px,92vw);padding:10px 12px;background:#0f172a;border:1px solid #334155;border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.5);font:12px/1.55 ui-monospace,Menlo,Consolas,monospace;color:#e2e8f0;white-space:pre-wrap;overflow-wrap:anywhere;pointer-events:none}.dg-tip .th{display:block;margin-bottom:6px;color:#22d3ee;font-weight:700}
.dg-A{color:#34d399}.dg-M{color:#fbbf24}.dg-D{color:#fb7185}
.dg-file .st{margin-left:24px;font-size:11px;color:#64748b}.dg-file .st i{font-style:normal;margin-left:6px}.dg-file .st .a{color:#2f8f6f}.dg-file .st .d{color:#b9566a}
.dg-zoom{position:relative;overflow:hidden;max-height:85vh;background:#020617;border:1px solid #1e293b;border-radius:10px;cursor:grab;touch-action:pinch-zoom pan-y;user-select:none}.dg-zoom.drag{cursor:grabbing}.dg-zoom svg{display:block;width:100%;height:100%;transform-origin:0 0;will-change:transform}.dg-zc{position:absolute;right:10px;bottom:10px;display:flex;gap:4px;z-index:2}.dg-zb{width:30px;height:30px;border:1px solid #334155;border-radius:6px;background:#0f172a;color:#e2e8f0;font:16px/1 ui-monospace,Menlo,monospace;cursor:pointer;padding:0}.dg-zb:hover{border-color:#22d3ee;color:#22d3ee}.dg-zt{display:none}.dg-zoom.full{position:fixed;inset:0;z-index:1000;max-height:none;aspect-ratio:auto!important;border-radius:0;border:0}.dg-zoom.full .dg-zt{display:block;position:absolute;left:16px;top:12px;z-index:2;color:#cbd5e1;font:13px ui-monospace,Menlo,monospace;pointer-events:none}.dg-zoom.full .dg-zb{width:36px;height:36px}
.dg .ln{font-size:11px;font-weight:700;fill:#f1f5f9}.dg .lp{font-size:9px;fill:#7dd3fc}.dg .ls{font-size:9px;fill:#94a3b8}.dg .ml{font-size:11px;paint-order:stroke;stroke:#020617;stroke-width:4px}.dg .nt{font-size:10px;fill:#fdba74}
.dg .stereo{font-size:10px;fill:#94a3b8}.dg .cname{font-size:12px;font-weight:700;fill:#f1f5f9}.dg .path{font-size:9px;fill:#7dd3fc}.dg .mem{font-size:10px}.dg .elabel{font-size:10px;fill:#94a3b8;paint-order:stroke;stroke:#020617;stroke-width:4px}
"""

ZOOM_JS = """
(function(){
  if (window.__dgZoom) return; window.__dgZoom = 1;
  var MIN = 0.4, MAX = 6;
  function st(f){ return f._z || (f._z = {s:1, x:0, y:0}); }
  function clamp(f){
    var z = st(f), w = f.clientWidth, h = f.clientHeight;
    var lx = Math.min(0, w - w*z.s), hx = Math.max(0, w - w*z.s), ly = Math.min(0, h - h*z.s), hy = Math.max(0, h - h*z.s);
    z.x = Math.min(hx, Math.max(lx, z.x)); z.y = Math.min(hy, Math.max(ly, z.y));
  }
  function paint(f){ clamp(f); var z = st(f); f.querySelector('svg').style.transform = 'translate('+z.x+'px,'+z.y+'px) scale('+z.s+')'; }
  function zoomAt(f, k, cx, cy){
    var z = st(f), n = Math.min(MAX, Math.max(MIN, z.s * k)); k = n / z.s;
    z.x = cx - (cx - z.x) * k; z.y = cy - (cy - z.y) * k; z.s = n; paint(f);
  }
  function toggleFull(f){
    var on = !f.classList.contains('full');
    f.classList.toggle('full', on);
    document.documentElement.style.overflow = on ? 'hidden' : '';
    f.querySelector('.dg-zf').textContent = on ? '\\u2715' : '\\u26F6';
    f._z = {s:1, x:0, y:0}; paint(f);
  }
  document.addEventListener('keydown', function(e){
    if (e.key !== 'Escape') return; var f = document.querySelector('.dg-zoom.full'); if (f) toggleFull(f);
  });
  document.addEventListener('click', function(e){
    var b = e.target.closest && e.target.closest('.dg-zb'); if (!b) return;
    var f = b.closest('.dg-zoom'), a = b.getAttribute('data-z');
    if (a === 'full') { toggleFull(f); }
    else if (a === 'reset') { f._z = {s:1, x:0, y:0}; paint(f); }
    else zoomAt(f, a === 'in' ? 1.25 : 0.8, f.clientWidth / 2, f.clientHeight / 2);
  });
  document.addEventListener('wheel', function(e){
    var f = e.target.closest && e.target.closest('.dg-zoom'); if (!f || !(e.ctrlKey || e.metaKey)) return;
    e.preventDefault(); var r = f.getBoundingClientRect();
    zoomAt(f, e.deltaY < 0 ? 1.1 : 0.9, e.clientX - r.left, e.clientY - r.top);
  }, {passive:false});
  var drag = null;
  document.addEventListener('pointerdown', function(e){
    var f = e.target.closest && e.target.closest('.dg-zoom'); if (!f || e.target.closest('.dg-zc')) return;
    var z = st(f); drag = {f:f, px:e.clientX, py:e.clientY, x:z.x, y:z.y}; f.classList.add('drag');
  });
  document.addEventListener('pointermove', function(e){
    if (!drag) return; var z = st(drag.f); z.x = drag.x + e.clientX - drag.px; z.y = drag.y + e.clientY - drag.py; paint(drag.f);
  });
  function end(){ if (drag) { drag.f.classList.remove('drag'); drag = null; } }
  document.addEventListener('pointerup', end); document.addEventListener('pointercancel', end);
})();

(function(){
  if (window.__dgTip) return; window.__dgTip = 1;
  var tip = document.createElement('div'); tip.className = 'dg-tip'; tip.setAttribute('role', 'tooltip');
  var head = document.createElement('span'); head.className = 'th';
  var body = document.createElement('span'); tip.appendChild(head); tip.appendChild(body);
  document.body.appendChild(tip);
  var cur = null;
  function show(li){
    cur = li; head.textContent = li.getAttribute('data-head') || ''; body.textContent = li.getAttribute('data-note');
    tip.style.display = 'block';
    var r = li.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
    var x = Math.max(8, Math.min(r.left + 24, window.innerWidth - w - 8));
    var y = r.bottom + 6; if (y + h > window.innerHeight - 8) y = Math.max(8, r.top - h - 6);
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }
  function hide(){ cur = null; tip.style.display = 'none'; }
  function find(e){ return e.target.closest ? e.target.closest('.dg-has-note') : null; }
  document.addEventListener('mouseover', function(e){ var li = find(e); if (li) show(li); else if (cur) hide(); });
  document.addEventListener('focusin', function(e){ var li = find(e); if (li) show(li); else if (cur) hide(); });
  document.addEventListener('click', function(e){ var li = find(e); if (li && cur !== li) show(li); else if (!li && cur) hide(); });
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape') hide(); });
  window.addEventListener('scroll', hide, true);
})();
"""

def fragment(spec):
    uid = spec.get("id", "dg"); tabs = []; N = spec.get("tab_names", {})
    if spec.get("files"): tabs.append((N.get("files", "File explorer"), explorer(spec["files"], spec.get("files_note"))))
    if spec.get("sequence"): tabs.append((N.get("sequence", "Sequence"), sequence(spec["sequence"], uid)))
    if spec.get("uml"): tabs.append((N.get("uml", "UML classes"), uml(spec["uml"], uid)))
    if not tabs: sys.exit("diagramer: spec has none of files, sequence, uml")
    inputs = "".join(f'<input type="radio" name="{uid}-t" id="{uid}-t{i}"{" checked" if i == 0 else ""}>' for i in range(len(tabs)))
    labels = "".join(f'<label for="{uid}-t{i}">{i+1} · {E(n)}</label>' for i, (n, _) in enumerate(tabs))
    panels = "".join(f'<div class="dg-p" id="{uid}-p{i}">{h}</div>' for i, (_, h) in enumerate(tabs))
    rules = "".join(f"#{uid}-t{i}:checked~#{uid}-p{i}{{display:block}}#{uid}-t{i}:checked~.dg-tabs label[for={uid}-t{i}]{{border-color:#22d3ee;color:#22d3ee}}" for i in range(len(tabs)))
    return f'<style>{CSS}{rules}</style><div class="dg">{inputs}<div class="dg-tabs">{labels}</div>{panels}</div><script>{ZOOM_JS}</script>'

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec"); ap.add_argument("-o", "--output")
    ap.add_argument("--standalone", action="store_true")
    ap.add_argument("--insert-into", help="understanding-page spec JSON to add the diagram section to")
    ap.add_argument("--after", default="glossary", help="section id to insert after (default: glossary)")
    a = ap.parse_args()
    spec = json.load(open(a.spec)); frag = fragment(spec)
    if a.insert_into:
        page = json.load(open(a.insert_into)); sid = spec.get("id", "dg")
        sec = {"id": "diagrams", "num": "◈", "heading": spec.get("heading", "Where the change lives"),
               "lead": spec.get("lead", "Three views of the same change: files, runtime order, and types."), "html": frag}
        secs = [s for s in page["sections"] if s.get("id") != "diagrams"]
        idx = next((i for i, s in enumerate(secs) if s.get("id") == a.after), None)
        if idx is None: sys.exit(f"diagramer: no section with id '{a.after}'")
        secs.insert(idx + 1, sec); page["sections"] = secs
        json.dump(page, open(a.insert_into, "w"), ensure_ascii=False, indent=2)
        print(f"inserted section 'diagrams' after '{a.after}' in {a.insert_into}"); return
    if a.standalone:
        t = E(spec.get("title", "Diagrams"))
        frag = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{t}</title>'
                f'<style>:root{{color-scheme:dark}}body{{margin:0;background:#020617}}main{{max-width:1280px;margin:auto;padding:24px 16px 40px}}h1{{font:18px ui-monospace,Menlo,monospace;color:#e2e8f0}}</style></head><body><main><h1>{t}</h1>{frag}</main></body></html>')
    if a.output: open(os.path.expanduser(a.output), "w").write(frag); print(os.path.expanduser(a.output))
    else: print(frag)

if __name__ == "__main__":
    main()
