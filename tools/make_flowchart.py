"""Write the pipeline flowchart as a draw.io file (deliverables/flowchart.drawio).

The boxes carry the measured numbers from data/sample/*_metrics.json when they
exist, so the chart and the results never disagree. Open the file at
app.diagrams.net (or draw.io desktop) and export a PNG from there.

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
NOTE = "rounded=0;whiteSpace=wrap;html=1;fontSize=10;align=left;verticalAlign=top;spacing=6;"


def _load(name: str) -> dict:
    p = DATA_DIR / "sample" / name
    return json.load(open(p)) if p.exists() else {}


class Chart:
    def __init__(self):
        self.cells: list[str] = []
        self.n = 0

    def node(self, text: str, x: int, y: int, w: int, h: int, style: str) -> str:
        self.n += 1
        cid = f"n{self.n}"
        self.cells.append(f'<mxCell id="{cid}" value={_attr(text)} style="{style}" vertex="1" parent="1">'
                          f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        return cid

    def edge(self, a: str, b: str, label: str = "", dashed: bool = False, exit: str = "", entry: str = "") -> None:
        self.n += 1
        style = "edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;fontSize=10;endArrow=block;endFill=1;"
        if dashed:
            style += "dashed=1;strokeColor=#9673a6;"
        style += exit + entry
        self.cells.append(f'<mxCell id="e{self.n}" value={_attr(label)} style="{style}" edge="1" parent="1" source="{a}" target="{b}">'
                          f'<mxGeometry relative="1" as="geometry"/></mxCell>')

    def xml(self) -> str:
        body = "".join(self.cells)
        return ('<mxfile host="app.diagrams.net"><diagram name="Pipeline" id="pipeline">'
                '<mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
                'fold="1" page="1" pageScale="1" pageWidth="1654" pageHeight="1700" math="0" shadow="0"><root>'
                '<mxCell id="0"/><mxCell id="1" parent="0"/>' + body + '</root></mxGraphModel></diagram></mxfile>')


def _attr(text: str) -> str:
    return '"' + html.escape(text, quote=True) + '"'


def main() -> None:
    l1, l2, l3, ctl, base = (_load(n) for n in ("l1_metrics.json", "l2_metrics.json", "l3_metrics.json", "controller.json", "baseline.json"))
    pick = l3.get("pick", "?")
    mode = l3.get("modes", {}).get(pick, {})
    e2e = l3.get("end_to_end", {}).get(pick, {})

    def pct(v, nd=0):
        return f"{100 * v:.{nd}f}%" if isinstance(v, (int, float)) else "?"

    c = Chart()
    W = 300
    MX = 470  # main column x
    src = c.node("<b>S3 bucket</b><br>5M objects + the free manifest<br>(key, size, checksum)", MX, 20, W, 60, "ellipse;whiteSpace=wrap;html=1;fontSize=11;" + GREY)
    l0 = c.node("<b>L0 Open the file</b> (~2.5 ms, no model)<br>true type from the bytes; trusted visible text vs scan;<br>"
                "emails and zips unpacked; start from P(class | format)", MX, 110, W, 75, BOX + BLUE)
    dup = c.node("Same checksum<br>as a file seen before?", MX + 60, 210, 180, 80, DIAMOND + YELLOW)
    copy = c.node("Copy the first copy's label<br>(free)", MX + 380, 225, 170, 50, BOX + GREEN)
    txt = c.node("Trusted visible<br>text on page 1?", MX + 60, 320, 180, 80, DIAMOND + YELLOW)
    free = c.node("<b>L2 on the free text</b> (~1 ms)<br>letter-piece model + ID checks<br>(checksum-valid IDs are evidence, not verdicts)",
                  MX - 400, 330, 270, 70, BOX + BLUE)
    g_free = c.node("Top class<br>&ge; &tau;?", MX - 330, 430, 130, 80, DIAMOND + ORANGE)
    split = c.node("<b>Bundle splitter</b> (multi-page files)<br>every page: L1 layout + page-number line;<br>"
                   "new document where P(boundary) &ge; 0.40;<br>&quot;Page 3&quot; never starts one, &quot;Page 1&quot; always does",
                   MX, 420, W, 80, BOX + BLUE)
    lay = c.node(f"<b>L1 Layout</b> (0.14 s/page)<br>DiT (frozen, MIT) + 6 readable signals<br>+ logistic regression, temperature-calibrated"
                 f"<br>settles {pct(l1.get('accept_rate'))} of documents at {pct(l1.get('accepted_accuracy'), 1)}",
                 MX, 525, W, 80, BOX + BLUE)
    g1 = c.node("Top class<br>&ge; &tau;?", MX + 85, 635, 130, 80, DIAMOND + ORANGE)
    kyc = c.node("Is it a<br>KYC ID document?", MX + 410, 635, 150, 80, DIAMOND + YELLOW)
    addr = c.node("<b>Address question</b> (D24)<br>full read of the card;<br>valid PIN + address label or state<br>&rarr; PoA, otherwise PoI",
                  MX + 620, 630, 230, 90, BOX + PURPLE)
    g_addr = c.node("P(KYC) &times; P(answer)<br>&ge; 95%?", MX + 655, 750, 160, 80, DIAMOND + YELLOW)
    ladder = c.node("<b>Reading ladder + L2 text model</b><br>rung 2 selective read: top and largest lines (0.63 s)<br>"
                    "rung 3 full page (2.9 s)<br>rung 4 next informative page + last page<br>"
                    "<i>each rung replaces the last rung's text evidence</i><br>"
                    "legal/property: later pages first (the e-stamp page is shared)", MX, 745, W, 112, BOX + BLUE)
    g2 = c.node("Top class &ge; &tau;?<br>(after each rung)", MX + 60, 905, 180, 95, DIAMOND + ORANGE)
    net = c.node("<b>Critical safety net</b><br>if P(Legal, Property, PoI or PoA) &ge; 10%,<br>the document's gate never drops below 95%",
                 MX - 330, 915, 250, 70, NOTE + RED)
    tau_note = c.node("<b>&tau;</b> = the gate at every orange diamond:<br>95% by default; the controller moves it<br>between 85% and 99%",
                      MX - 330, 1010, 250, 60, NOTE + ORANGE)
    llm = c.node(f"<b>L3 LLM</b>: Haiku via <code>claude -p</code>, tools off<br>masked text (IDs replaced by their type);<br>"
                 f"2-5 candidate classes + &quot;none of these&quot;;<br>answer used as a sensor with a measured error rate<br>"
                 f"mode: {pick}, ~&#8377;{mode.get('inr_per_call', 0):.3f} per call",
                 MX, 1125, W, 100, BOX + BLUE)
    g3 = c.node("Top class<br>&ge; 95%?", MX + 85, 1255, 130, 80, DIAMOND + YELLOW)
    human = c.node(f"<b>L4 Human review</b><br>benchmark &#8377;1 per document<br>dev-test share: {pct(e2e.get('l4_share_dev'), 1)}",
                   MX, 1370, W, 60, BOX + RED)
    acc = c.node("<b>ACCEPT</b><br>label, confidence, the step that settled it, its cost<br>"
                 "(bundles: one row per document inside, with its page range)", MX + 620, 1365, 300, 70, BOX + GREEN)
    ctl_box = c.node("<b>Budget controller</b><br>after every batch: spend vs a straight plan line<br>"
                     "target &#8377;50k, 10% reserve (aims at &#8377;45k)<br>over plan &rarr; lower &tau;<br>"
                     "under plan &rarr; raise &tau; only if that is measured<br>to buy accuracy (it did not: held at 95%)",
                     MX + 620, 960, 270, 100, NOTE + ORANGE)

    c.edge(src, l0)
    c.edge(l0, dup)
    c.edge(dup, copy, "yes")
    c.edge(dup, txt, "no")
    c.edge(txt, free, "yes: digital PDF, DOCX,<br>XLSX, TXT, email")
    c.edge(free, g_free)
    c.edge(g_free, acc, "yes", exit="exitX=0.5;exitY=1;", entry="entryX=0;entryY=0.5;")
    c.edge(g_free, lay, "no: add layout", exit="exitX=1;exitY=0.5;", entry="entryX=0;entryY=0.5;")
    c.edge(txt, split, "no: scans, photos")
    c.edge(split, lay)
    c.edge(lay, g1)
    c.edge(g1, kyc, "yes")
    c.edge(kyc, addr, "yes")
    c.edge(kyc, acc, "no", exit="exitX=0.5;exitY=0;", entry="entryX=1;entryY=0.25;")
    c.edge(addr, g_addr)
    c.edge(g_addr, acc, "yes", exit="exitX=0.5;exitY=1;", entry="entryX=0.5;entryY=0;")
    c.edge(g_addr, llm, "no", exit="exitX=0;exitY=0.5;", entry="entryX=1;entryY=0.5;")
    c.edge(g1, ladder, "no: buy the cheapest read<br>that can split what's left")
    c.edge(ladder, g2)
    c.edge(g2, kyc, "yes", exit="exitX=1;exitY=0.5;", entry="entryX=0.5;entryY=1;")
    c.edge(g2, ladder, "no: next rung", exit="exitX=0;exitY=0.5;", entry="entryX=0;entryY=0.75;")
    c.edge(g2, llm, "no, after rung 4")
    c.edge(net, g2, "", dashed=True)
    c.edge(tau_note, g2, "", dashed=True)
    c.edge(ctl_box, g2, "moves &tau;", dashed=True)
    c.edge(llm, g3)
    c.edge(g3, acc, "yes", exit="exitX=1;exitY=0.5;", entry="entryX=0;entryY=0.25;")
    c.edge(g3, human, "no / none of these")
    c.edge(human, acc)

    rule = ("<b>The rule at every gate</b><br>"
            "Each document carries a probability for every class, starting from P(class | format), never 0.<br>"
            "Every step multiplies in its evidence (Bayes) and the document stops when one class reaches the gate.<br>"
            "Otherwise it buys the cheapest next piece of evidence that can separate the classes still in play.<br><br>"
            "<b>Why 95%:</b> an accepted document is then wrong at most 5% of the time, and the measured accuracy of<br>"
            "accepted documents is higher; the next step costs 3-10x the last, so stopping as soon as one is sure is<br>"
            "the cheap way to the bar (macro-F1 &ge; 0.85, critical recall &ge; 0.90).<br>"
            "<b>Why one movable gate (&tau;) before the LLM:</b> reading pages is where most of the money goes, so the<br>"
            "controller trades accuracy for spend at every gate before the LLM, and never for critical documents.")
    c.node(rule, 20, 1460, 640, 175, NOTE + GREY)
    la = json.load(open(DATA_DIR / "lockbox_a" / "final_metrics.json")) if (DATA_DIR / "lockbox_a" / "final_metrics.json").exists() else {}
    res = ("<b>Measured (synthetic documents)</b><br>"
           f"dev-test macro-F1 {e2e.get('macro_f1_l4_as_error', float('nan')):.3f}; critical recall 1.00 on all four<br>"
           f"Lockbox A (sealed, unseen layouts, run once): macro-F1 {la.get('macro_f1_abstain_as_error', float('nan')):.3f}<br>"
           f"reaching the LLM: {pct(l2.get('l3_docs_5m', 0) / 5e6, 1)}; reaching humans: {pct(e2e.get('l4_share_dev'), 1)}<br>"
           f"5M run: &#8377;{ctl.get('controlled_spent', 0):,.0f} vs &#8377;{base.get('total_inr', 0):,.0f} brute force")
    c.node(res, 700, 1460, 420, 120, NOTE + GREEN)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(c.xml())
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
