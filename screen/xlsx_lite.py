"""只用标准库读 .xlsx（本机各环境都没装 openpyxl）：返回 {表名: 行列表}，单元格为字符串或数字。"""
import re
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def _col(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(path):
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = {r.get("Id"): r.get("Target") for r in rels}
    out = {}
    for sh in wb.find("m:sheets", NS):
        rid = sh.get("{%s}id" % NS["r"])
        p = target[rid].lstrip("/")
        p = p if p.startswith("xl/") else "xl/" + p
        rows = []
        for row in ET.fromstring(z.read(p)).iter("{%s}row" % NS["m"]):
            vals = {}
            for c in row.findall("m:c", NS):
                v = c.find("m:v", NS)
                t = c.get("t")
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter("{%s}t" % NS["m"]))
                elif v is not None:
                    try:
                        f = float(v.text)
                        val = int(f) if f.is_integer() and abs(f) < 2**53 else f
                    except ValueError:
                        val = v.text
                else:
                    continue
                vals[_col(c.get("r"))] = val
            if vals:
                rows.append([vals.get(i, "") for i in range(max(vals) + 1)])
        out[sh.get("name")] = rows
    return out
