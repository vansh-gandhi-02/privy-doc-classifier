"""Write the pipeline flowchart as a draw.io file (deliverables/flowchart.drawio).

The boxes carry the measured numbers from data/*.json when they exist, so the chart
and the results never disagree. Every arrow is drawn through fixed points, so no two
arrows cross or overlap; YES/NO labels sit next to where each arrow leaves its diamond.
Open the file at app.diagrams.net (or draw.io desktop) and export from there.

Run: python -m tools.make_flowchart
"""
from __future__ import annotations

import html
import json

from common.config import DATA_DIR, ROOT

OUT = ROOT / "deliverables" / "flowchart.drawio"

BLUE = "fillColor=#dae8fc;strokeColor=#6c8ebf;"
GREEN = "fillColor=#d5e8d4;strokeColor=#82b366;"
YELLOW = "fillColor=#fff2cc;strokeColor=#d6b656;"
ORANGE = "fillColor=#ffe6cc;strokeColor=#d79b00;"
RED = "fillColor=#f8cecc;strokeColor=#b85450;"
GREY = "fillColor=#f5f5f5;strokeColor=#666666;"
PURPLE = "fillColor=#e1d5e7;strokeColor=#9673a6;"
BOX = "rounded=1;whiteSpace=wrap;html=1;fontSize=11;align=center;verticalAlign=middle;"
DIAMOND = "rhombus;whiteSpace=wrap;html=1;fontSize=10;"
NOTE = "rounded=0;whiteSpace=wrap;html=1;fontSize=11;align=left;verticalAlign=top;spacing=8;"
YES_C, NO_C = "#1b7a2f", "#c0262d"
CHAR_W = 7.3  # rough width of one 12px bold character, to place labels


def _load(rel: str) -> dict:
    p = DATA_DIR / rel
    return json.load(open(p)) if p.exists() else {}


def _inr(v: float) -> str:
    """Indian digit grouping: 130170 -> 1,30,170."""
    s = f"{round(v):d}"
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return ",".join([g for g in [head] + groups if g] + [tail])


def _attr(text: str) -> str:
    return '"' + html.escape(text, quote=True) + '"'


class Chart:
    def __init__(self, dy: float = 0):
        self.dy = dy  # shifts everything down, leaving room for the title
        self.cells: list[str] = []
        self.geo: dict[str, tuple[float, float, float, float]] = {}
        self.n = 0

    def node(self, text: str, x: float, y: float, w: float, h: float, style: str) -> str:
        self.n += 1
        cid = f"n{self.n}"
        y += self.dy
        self.geo[cid] = (x, y, w, h)
        self.cells.append(f'<mxCell id="{cid}" value={_attr(text)} style="{style}" vertex="1" parent="1">'
                          f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        return cid

    def edge(self, a: str, b: str, pts: list[tuple[float, float]], label: str = "", kind: str = "", dashed: bool = False) -> None:
        """An arrow from a to b along pts (first point on a's border, last on b's), straight segments only.

        kind "yes"/"no" colours the label and puts it next to where the arrow leaves a."""
        self.n += 1
        pts = [(x, y + self.dy) for x, y in pts]
        (ax, ay, aw, ah), (bx, by, bw, bh) = self.geo[a], self.geo[b]
        (x0, y0), (x1, y1) = pts[0], pts[-1]
        style = (f"edgeStyle=none;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=1.3;"
                 f"exitX={(x0 - ax) / aw:.4f};exitY={(y0 - ay) / ah:.4f};exitDx=0;exitDy=0;"
                 f"entryX={(x1 - bx) / bw:.4f};entryY={(y1 - by) / bh:.4f};entryDx=0;entryDy=0;")
        if dashed:
            style += "dashed=1;strokeColor=#9673a6;fontColor=#9673a6;"
        geo = '<mxGeometry relative="1" as="geometry">'
        if label:
            text = label
            if kind:
                head, _, rest = label.partition(":")
                color = YES_C if kind == "yes" else NO_C
                text = f'<b><font color="{color}">{head}</font></b>' + (f":{rest}" if rest else "")
                style += "fontSize=12;labelBackgroundColor=#ffffff;"
            else:
                style += "fontSize=11;labelBackgroundColor=#ffffff;"
            lines = label.split("<br>")
            w = max(len(s) for s in lines) * CHAR_W
            seg = [((pts[i][0], pts[i][1]), (pts[i + 1][0], pts[i + 1][1])) for i in range(len(pts) - 1)]
            total = sum(abs(p[0] - q[0]) + abs(p[1] - q[1]) for p, q in seg)
            (p, q) = seg[0]
            first = abs(p[0] - q[0]) + abs(p[1] - q[1])
            if p[0] == q[0]:      # leaves vertically: label beside the line, just below or above the diamond
                d = min(first / 2, 22)
                off = (w / 2 + 6, 0)
            else:                 # leaves horizontally: label on the line, starting at the diamond
                d = min(first / 2, w / 2 + 8)
                off = (0, 0)
            geo = (f'<mxGeometry x="{-1 + 2 * d / total:.4f}" relative="1" as="geometry">'
                   f'<mxPoint x="{off[0]:.1f}" y="{off[1]:.1f}" as="offset"/>')
        else:
            text = ""
        way = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in pts[1:-1])
        if way:
            geo += f'<Array as="points">{way}</Array>'
        geo += "</mxGeometry>"
        self.cells.append(f'<mxCell id="e{self.n}" value={_attr(text)} style="{style}" edge="1" parent="1" '
                          f'source="{a}" target="{b}">{geo}</mxCell>')

    def xml(self, width: int, height: int) -> str:
        body = "".join(self.cells)
        return ('<mxfile host="app.diagrams.net"><diagram name="Pipeline" id="pipeline">'
                f'<mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
                f'fold="1" page="1" pageScale="1" pageWidth="{width}" pageHeight="{height}" math="0" shadow="0"><root>'
                '<mxCell id="0"/><mxCell id="1" parent="0"/>' + body + '</root></mxGraphModel></diagram></mxfile>')


def main() -> None:
    bench, l1, l2, l3 = _load("bench.json"), _load("sample/l1_metrics.json"), _load("sample/l2_metrics.json"), _load("sample/l3_metrics.json")
    prec, base = _load("sample/cost_precision.json"), _load("sample/baseline.json")
    la, lc = _load("lockbox_a/final_metrics.json"), _load("lockbox_c/final_metrics.json")
    pick = l3.get("pick", "?")
    mode = l3.get("modes", {}).get(pick, {})
    e2e = l3.get("end_to_end", {}).get(pick, {})
    total = prec.get("point", {}).get("total", 0)

    def pct(v, nd=0):
        return f"{100 * v:.{nd}f}%" if isinstance(v, (int, float)) else "?"

    c = Chart(dy=55)
    c.node("<b>Classifying 5M bank documents on a &#8377;1,00,000 budget: how one document moves through the pipeline</b>",
           20, -45, 1400, 30, "text;html=1;fontSize=18;align=left;verticalAlign=middle;")
    W, MX, CX = 300, 470, 620  # main column: width, left edge, centre line
    D = 60                     # vertical offset of the flow, leaving room for the reading guide at the top left

    guide = ("<b style='font-size:13px'>How to read this flowchart</b><br><br>"
             "<b>1. Follow one document from the top.</b> Each blue box is a step that buys evidence about it; "
             "its cost is in brackets, and the steps get dearer as you go down.<br><br>"
             "<b>2. The document carries a probability for each of the 15 classes.</b> It starts from the class mix "
             "expected for its file format (never 0), and every blue step updates it (Bayes' rule).<br><br>"
             f"<b>3. After each step a diamond decides.</b> <b><font color='{YES_C}'>YES</font></b>: one class is sure "
             f"enough, so stop and accept. <b><font color='{NO_C}'>NO</font></b>: buy the next, dearer step. "
             "Orange diamonds use the movable gate &tau;; yellow ones are fixed checks. "
             "The purple box splits KYC IDs into Proof of Identity or Proof of Address.<br><br>"
             "<b>4. Every document ends in one of two places:</b> ACCEPT (green), with its label, confidence and the "
             "step that settled it, or a person (red).<br><br>"
             "<b>5. The three boxes at the top right apply at every orange diamond:</b> what &tau; is, the critical "
             "safety net, and the budget controller that moves &tau;.<br><br>"
             "<b>Why 95%:</b> an accepted document is then wrong at most 5% of the time, and each next step costs "
             "several times the last, so stopping as soon as one class is sure is the cheapest way to the bar "
             "(macro-F1 &ge; 0.85, critical recall &ge; 0.90).<br><br>"
             "<b>Why &tau; moves only at the gates before the LLM:</b> reading pages is where most of the money goes, so "
             "that is where the controller trades accuracy for spend; never for critical documents.")
    c.node(guide, 20, 20, 430, 390, NOTE + GREY)

    src = c.node("<b>S3 bucket</b><br>5M objects + the free manifest<br>(key, size, checksum)", MX, 20, W, 60,
                 "ellipse;whiteSpace=wrap;html=1;fontSize=11;" + GREY)
    l0 = c.node(f"<b>L0 Open the file</b> ({bench.get('l0_s_per_file', 0) * 1000:.0f} ms, no model)<br>"
                "true type from the bytes; trusted visible text vs scan;<br>"
                "emails and zips unpacked; start from P(class | format)", MX, 120, W, 75, BOX + BLUE)
    dup = c.node("Same checksum<br>as a file seen before?", MX + 60, 235, 180, 80, DIAMOND + YELLOW)
    copy = c.node("Copy the first copy's label<br>(free)", 860, 250, 170, 50, BOX + GREEN)
    txt = c.node("Trusted visible<br>text on page 1?", MX + 60, 360 + D, 180, 80, DIAMOND + YELLOW)
    free = c.node("<b>L2 on the free text</b> (~1 ms)<br>letter-piece model + ID checks<br>"
                  "(checksum-valid IDs are evidence, not verdicts)", 50, 365 + D, 290, 70, BOX + BLUE)
    g_free = c.node("Top class<br>&ge; &tau;?", 130, 480 + D, 130, 80, DIAMOND + ORANGE)
    split = c.node("<b>Bundle splitter</b> (multi-page files)<br>every page: L1 layout + page-number line;<br>"
                   "new document where P(boundary) &ge; 0.40;<br>&quot;Page 3&quot; never starts one, &quot;Page 1&quot; always does",
                   MX, 490 + D, W, 80, BOX + BLUE)
    lay = c.node(f"<b>L1 Layout</b> ({bench.get('l1_s_per_page', 0):.2f} s/page)<br>DiT (frozen, MIT) + 6 readable signals<br>"
                 f"+ logistic regression, temperature-calibrated<br>settles {pct(l1.get('accept_rate'))} of scanned documents "
                 f"at {pct(l1.get('accepted_accuracy'), 1)}", MX, 615 + D, W, 80, BOX + BLUE)
    g1 = c.node("Top class<br>&ge; &tau;?", MX + 85, 740 + D, 130, 80, DIAMOND + ORANGE)
    kyc = c.node("Is it a<br>KYC ID document?", 885, 740 + D, 150, 80, DIAMOND + YELLOW)
    addr = c.node("<b>Address question</b><br>full read of the card;<br>valid PIN + address label or state<br>&rarr; PoA, otherwise PoI",
                  1090, 735 + D, 230, 90, BOX + PURPLE)
    g_addr = c.node("P(KYC) &times; P(answer)<br>&ge; 95%?", 1120, 875 + D, 170, 80, DIAMOND + YELLOW)
    ladder = c.node(f"<b>Reading ladder + L2 text model</b><br>rung 2 selective read: top and largest lines ({bench.get('ocr_selective_s', 0):.2f} s)<br>"
                    f"rung 3 full page ({bench.get('ocr_full_s', 0):.1f} s)<br>rung 4 next informative page + last page<br>"
                    "<i>each rung replaces the last rung's text evidence</i><br>"
                    "legal/property: later pages first (the e-stamp page is shared)", MX, 880 + D, W, 112, BOX + BLUE)
    g2 = c.node("Top class &ge; &tau;?<br>(after each rung)", MX + 60, 1050 + D, 180, 95, DIAMOND + ORANGE)
    llm = c.node(f"<b>L3 LLM</b>: Haiku via <code>claude -p</code>, tools off<br>masked text (IDs replaced by their type);<br>"
                 f"2-5 candidate classes + &quot;none of these&quot;;<br>answer used as a sensor with a measured error rate<br>"
                 f"mode: {pick}, ~&#8377;{mode.get('inr_per_call', 0):.3f} per call", MX, 1205 + D, W, 100, BOX + BLUE)
    g3 = c.node("Top class<br>&ge; 95%?", MX + 85, 1365 + D, 130, 80, DIAMOND + YELLOW)
    human = c.node(f"<b>L4 Human review</b><br>no price quoted: counted, not costed<br>"
                   f"about {round(prec.get('human_docs_5m', 0), -2):,.0f} of 5M documents (dev-test {pct(e2e.get('l4_share_dev'), 1)})",
                   MX, 1500 + D, W, 60, BOX + RED)
    acc = c.node("<b>ACCEPT</b><br>label, confidence, the step that settled it, its cost<br>"
                 "(bundles: one row per document inside, with its page range)", 1055, 1495 + D, 300, 70, BOX + GREEN)

    # the rules that apply at every orange diamond, kept together at the top right
    c.node("<b>Apply at every orange diamond</b>", 1090, 85, 290, 25, "text;html=1;fontSize=12;align=left;verticalAlign=middle;")
    c.node("<b>Critical safety net</b><br>if P(Legal, Property, PoI or PoA) &ge; 10%,<br>the document's gate never drops below 95%",
           1090, 115, 290, 70, NOTE + RED)
    tau = c.node("<b>&tau;</b> = the gate at every orange diamond:<br>95% by default; the controller moves it<br>between 85% and 99%",
                 1090, 200, 290, 65, NOTE + ORANGE)
    ctl = c.node("<b>Budget controller</b><br>after every batch: spend vs a straight plan line<br>"
                 "target &#8377;50k, 10% reserve (aims at &#8377;45k)<br>over plan &rarr; lower &tau;<br>"
                 "under plan &rarr; raise &tau; only if that is measured<br>to buy accuracy (it did not: held at 95%)",
                 1090, 320, 290, 115, NOTE + ORANGE)
    c.edge(ctl, tau, [(1235, 320), (1235, 265)], "moves &tau;", dashed=True)

    # the main flow, top to bottom
    c.edge(src, l0, [(CX, 80), (CX, 120)])
    c.edge(l0, dup, [(CX, 195), (CX, 235)])
    c.edge(dup, copy, [(710, 275), (860, 275)], "YES", "yes")
    c.edge(dup, txt, [(CX, 315), (CX, 360 + D)], "NO", "no")
    c.edge(txt, free, [(530, 400 + D), (340, 400 + D)], "YES: digital files", "yes")
    c.edge(txt, split, [(CX, 440 + D), (CX, 490 + D)], "NO: scans, photos", "no")
    c.edge(free, g_free, [(195, 435 + D), (195, 480 + D)])
    c.edge(g_free, lay, [(260, 520 + D), (390, 520 + D), (390, 655 + D), (MX, 655 + D)], "NO: add layout", "no")
    c.edge(g_free, acc, [(195, 560 + D), (195, 1610 + D), (1205, 1610 + D), (1205, 1565 + D)], "YES", "yes")
    c.edge(split, lay, [(CX, 570 + D), (CX, 615 + D)])
    c.edge(lay, g1, [(CX, 695 + D), (CX, 740 + D)])
    c.edge(g1, kyc, [(685, 780 + D), (885, 780 + D)], "YES", "yes")
    c.edge(g1, ladder, [(CX, 820 + D), (CX, 880 + D)], "NO: buy the cheapest read<br>that can split what's left", "no")
    c.edge(kyc, addr, [(1035, 780 + D), (1090, 780 + D)], "YES", "yes")
    c.edge(kyc, acc, [(960, 740 + D), (960, 700 + D), (1420, 700 + D), (1420, 1530 + D), (1355, 1530 + D)], "NO", "no")
    c.edge(addr, g_addr, [(1205, 825 + D), (1205, 875 + D)])
    c.edge(g_addr, acc, [(1205, 955 + D), (1205, 1495 + D)], "YES", "yes")
    c.edge(g_addr, llm, [(1120, 915 + D), (1060, 915 + D), (1060, 1255 + D), (770, 1255 + D)], "NO", "no")
    c.edge(ladder, g2, [(CX, 992 + D), (CX, 1050 + D)])
    c.edge(g2, kyc, [(710, 1097.5 + D), (960, 1097.5 + D), (960, 820 + D)], "YES", "yes")
    c.edge(g2, ladder, [(530, 1097.5 + D), (420, 1097.5 + D), (420, 964 + D), (MX, 964 + D)], "NO: next rung", "no")
    c.edge(g2, llm, [(CX, 1145 + D), (CX, 1205 + D)], "NO: after rung 4", "no")
    c.edge(llm, g3, [(CX, 1305 + D), (CX, 1365 + D)])
    c.edge(g3, acc, [(685, 1405 + D), (1120, 1405 + D), (1120, 1495 + D)], "YES", "yes")
    c.edge(g3, human, [(CX, 1445 + D), (CX, 1500 + D)], "NO: or the LLM says none of these", "no")
    c.edge(human, acc, [(770, 1530 + D), (1055, 1530 + D)], "a person labels it")

    res = ("<b>Measured (synthetic documents)</b><br>"
           f"dev-test: macro-F1 {e2e.get('macro_f1_l4_as_error', float('nan')):.3f}; critical recall 1.00 on all four<br>"
           f"Lockbox A (sealed, 40% unseen layouts, run once): macro-F1 {la.get('macro_f1_abstain_as_error', float('nan')):.3f}<br>"
           f"Lockbox C (fresh, run once): macro-F1 {lc.get('macro_f1_abstain_as_error', float('nan')):.3f}; critical recall 1.00<br>"
           f"reaching the LLM: {pct(l2.get('l3_docs_5m', 0) / 5e6, 1)}; reaching a person: {pct(e2e.get('l4_share_dev'), 1)}<br>"
           f"5M cost: &#8377;{total:,.0f} ({total / 5e6 * 100:.2f} paise a document) vs &#8377;{_inr(base.get('total_inr', 0))} brute force")
    c.node(res, MX, 1650 + D, 470, 100, NOTE + GREEN)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(c.xml(1460, 1830 + D + 55))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
