"""Generic HTML stats-table parser (Basketball-Reference style markup).

Basketball Reference renders most secondary tables inside HTML comments and uses
two-level headers ("over_header" groups). Column ids (`data-stat`) changed in the
site's 2024-25 redesign, so this parser keys columns by their *visible header
label + header group* and keeps the data-stat as a fallback for unlabeled columns.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Comment, Tag


@dataclass
class Column:
    label: str          # visible header text, e.g. "FG%"
    group: str          # over-header text, e.g. "FG% by Distance" ("" when none)
    data_stat: str      # data-stat attribute ("" when none)


@dataclass
class Cell:
    text: str
    data_stat: str = ""
    hrefs: list = field(default_factory=list)
    bold: bool = False
    colspan: int = 1
    csk: str | None = None


@dataclass
class Row:
    cells: list                     # list[(Column|None, Cell)]
    classes: list
    row_id: str = ""
    special_text: str | None = None  # e.g. "Did Not Play" spanning row

    def get(self, label: str, group: str | None = None) -> Cell | None:
        for col, cell in self.cells:
            if col is None:
                continue
            if col.label == label and (group is None or group.lower() in col.group.lower()):
                return cell
        return None

    def by_stat(self, *data_stats: str) -> Cell | None:
        for col, cell in self.cells:
            ds = cell.data_stat or (col.data_stat if col else "")
            if ds in data_stats:
                return cell
        return None

    def first_text(self) -> str:
        return self.cells[0][1].text if self.cells else ""


@dataclass
class Table:
    id: str
    caption: str
    columns: list
    body: list
    foot: list

    def labels(self) -> list:
        return [c.label for c in self.columns]


_ws = re.compile(r"\s+")


def _txt(el: Tag) -> str:
    return _ws.sub(" ", el.get_text(" ", strip=True)).strip()


def _cell(el: Tag) -> Cell:
    return Cell(
        text=_txt(el),
        data_stat=el.get("data-stat", "") or "",
        hrefs=[a.get("href", "") for a in el.find_all("a")],
        bold=el.find("strong") is not None or el.name == "strong",
        colspan=int(el.get("colspan", 1) or 1),
        csk=el.get("csk"),
    )


def _header(thead: Tag | None) -> list:
    if thead is None:
        return []
    rows = thead.find_all("tr", recursive=False) or thead.find_all("tr")
    if not rows:
        return []
    label_row = rows[-1]
    label_cells = label_row.find_all(["th", "td"], recursive=False)
    # Expand over-header groups (colspans) across columns.
    groups: list[str] = []
    for over in rows[:-1]:
        g: list[str] = []
        for c in over.find_all(["th", "td"], recursive=False):
            g.extend([_txt(c)] * int(c.get("colspan", 1) or 1))
        groups = g  # innermost over-header wins
    cols = []
    idx = 0
    for c in label_cells:
        span = int(c.get("colspan", 1) or 1)
        group = groups[idx] if idx < len(groups) else ""
        for _ in range(span):
            cols.append(Column(label=_txt(c), group=group, data_stat=c.get("data-stat", "") or ""))
        idx += span
    return cols


def _rows(section: Tag | None, columns: list) -> list:
    if section is None:
        return []
    out = []
    for tr in section.find_all("tr", recursive=False):
        classes = tr.get("class", []) or []
        if any(c in classes for c in ("thead", "over_header", "spacer")):
            continue
        tds = tr.find_all(["th", "td"], recursive=False)
        if not tds:
            continue
        cells = [_cell(td) for td in tds]
        special = None
        if any(c.colspan >= 4 for c in cells):
            special = " ".join(c.text for c in cells if c.colspan >= 4)
        mapped = []
        i = 0
        for c in cells:
            col = columns[i] if i < len(columns) else None
            mapped.append((col, c))
            i += c.colspan
        out.append(Row(cells=mapped, classes=classes, row_id=tr.get("id", "") or "", special_text=special))
    return out


def parse_table(t: Tag) -> Table:
    cap = t.find("caption")
    cols = _header(t.find("thead"))
    tbodies = t.find_all("tbody")
    body = []
    if tbodies:
        for tb in tbodies:
            body.extend(_rows(tb, cols))
    else:
        trs = [tr for tr in t.find_all("tr") if tr.parent is t]
        fake = BeautifulSoup("<tbody></tbody>", "lxml").tbody
        for tr in trs[1:]:
            fake.append(tr)
        body = _rows(fake, cols)
    return Table(id=t.get("id", "") or "", caption=_txt(cap) if cap else "", columns=cols,
                 body=body, foot=_rows(t.find("tfoot"), cols))


def all_tables(html: str) -> dict:
    """Parse every <table> including ones hidden in HTML comments. Keyed by id
    (tables without an id get 'table_<n>')."""
    soup = BeautifulSoup(html, "lxml")
    found: list[Tag] = list(soup.find_all("table"))
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        if "<table" in c:
            found.extend(BeautifulSoup(str(c), "lxml").find_all("table"))
    out: dict = {}
    for n, t in enumerate(found):
        pt = parse_table(t)
        key = pt.id or f"table_{n}"
        if key not in out:
            out[key] = pt
    return out


def find_table(tables: dict, ids: list, caption_keywords: list | None = None) -> Table | None:
    for i in ids:
        if i in tables:
            return tables[i]
    if caption_keywords:
        for t in tables.values():
            cap = t.caption.lower()
            if all(k.lower() in cap for k in caption_keywords):
                return t
    return None


# -- value parsing ------------------------------------------------------------
_num = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)$")


def parse_number(text: str | None):
    """'.453' -> 0.453, '45.3%' -> 0.453, '1,234' -> 1234, '' -> None, '36:24' -> 36.4."""
    if text is None:
        return None
    s = text.strip().replace(",", "").replace("−", "-")
    if s in ("", "—", "-", "N/A", "NA"):
        return None
    if re.match(r"^\d+:\d{2}$", s):  # minutes mm:ss
        m, sec = s.split(":")
        return round(int(m) + int(sec) / 60, 2)
    pct = s.endswith("%")
    if pct:
        s = s[:-1]
    if not _num.match(s):
        return None
    v = float(s)
    if pct:
        v = v / 100.0
    if v.is_integer() and not pct and "." not in s:
        return int(v)
    return v


def team_from_hrefs(hrefs: list) -> tuple:
    """('GSW', 2016) from '/teams/GSW/2016.html'."""
    for h in hrefs:
        m = re.search(r"/teams/([A-Z0-9]{2,4})/(\d{4})\.html", h)
        if m:
            return m.group(1), int(m.group(2))
    return None, None


def player_id_from_hrefs(hrefs: list) -> list:
    out = []
    for h in hrefs:
        m = re.search(r"/players/[a-z]/([a-z0-9]+)\.html", h)
        if m:
            out.append(m.group(1))
    return out
