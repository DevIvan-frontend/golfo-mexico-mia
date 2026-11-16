"""Pruebas de la API (pytest o ejecución directa: python tests/test_api.py)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

c = TestClient(app)
DWH = "bbox=-89,28,-88,29"   # celda de 1° del pozo Macondo (Deepwater Horizon)


def ok(r):
    assert r.status_code == 200, (r.status_code, r.text[:300])
    return r.json()


def test_meta_y_grid():
    m = ok(c.get("/api/meta"))
    assert m["months"][0] == "2003-01" and m["months"][-1] == "2024-12"
    for var in ("sst", "chl", "sst_anom", "chl_anom", "sst_change"):
        g = ok(c.get(f"/api/grid/{var}?month=2010-05"))
        vals = [v for fila in g["values"] for v in fila if v is not None]
        assert len(vals) > 1500, (var, len(vals))
    d = ok(c.get("/api/grid/depth"))
    assert max(v for fila in d["values"] for v in fila if v is not None) > 3000


def test_resumen_area():
    s = ok(c.get(f"/api/area/summary?month=2010-05&{DWH}"))
    v = s["variables"]
    assert 20 < v["sst"]["value"] < 32 and v["chl"]["value"] > 0
    assert v["depth"]["max"] > 1000
    assert any(e["id"] == "deepwater-2010" for e in s["events"])
    p = ok(c.get("/api/area/summary?month=2015-08&poly=-90,27;-88,27;-89,29"))
    assert p["selection"]["type"] == "poly" and p["selection"]["ocean_cells"] > 0


def test_series_tablas_3d():
    t = ok(c.get(f"/api/area/timeseries?var=chl&month=2010-05&{DWH}"))
    assert len(t["values"]) == 264 and len(t["annual"]) == 22 and len(t["same_month"]) == 22
    assert t["annual"][1]["direction"] in ("up", "down", "flat")
    sfc = ok(c.get(f"/api/area/surface?var=sst&month=2010-05&{DWH}"))
    assert len(sfc["altitude"]) > 10
    cel = ok(c.get(f"/api/area/cells?month=2010-05&{DWH}"))
    assert len(cel["sst"]) == 16
    dp = ok(c.get(f"/api/area/depth?{DWH}"))
    assert abs(sum(x["pct"] for x in dp["classes"]) - 100) < 1


def test_eventos():
    evs = ok(c.get("/api/events"))
    assert len(evs) >= 20
    assert all(e["start"] >= "2003-01" for e in evs)            # sin eventos anteriores a la línea de tiempo
    assert not any(e["id"] == "ixtoc-1979" for e in evs)
    imp = ok(c.get("/api/events/deepwater-2010/impact"))
    assert imp["cells"] > 50 and imp["sst"]["direction"] in ("up", "down", "flat")
    assert c.get("/api/events/ixtoc-1979/impact").status_code == 400


def test_export_xlsx():
    import base64
    import io

    from openpyxl import load_workbook
    png = base64.b64encode(bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")).decode()
    payload = {
        "filename": "prueba área.xlsx", "title": "Prueba", "info": [["Área", "28–29°N"]],
        "sheets": [{"name": "TSM anual / prueba:larga[1]", "columns": ["Año", "TSM", "Texto"],
                    "rows": [[2003, 26.5, "=1+1"], [2004, None, "ok"], [2005, 27.1, "x"]],
                    "chart": {"type": "line", "title": "TSM", "x_col": 0, "y_cols": [1]}}],
        "images": [{"title": "Gráfico", "png_base64": png}],
    }
    r = c.post("/api/export/xlsx", json=payload)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxmlformats")
    cd = r.headers["content-disposition"]
    assert 'filename="prueba_area.xlsx"' in cd and "filename*=UTF-8''prueba%20%C3%A1rea.xlsx" in cd
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames[0] == "Info" and len(wb.sheetnames) == 3
    ws = wb.worksheets[1]
    assert ws["A2"].value == 2003 and ws["C2"].value == "=1+1" and ws["C2"].data_type == "s"   # sin fórmulas inyectadas
    assert len(ws._charts) == 1 and len(wb.worksheets[2]._images) == 1
    assert c.post("/api/export/xlsx", json={"sheets": [{"name": "x", "columns": []}]}).status_code == 422


def test_cuaderno_jupyter():
    import io
    import json

    import numpy as np
    r = c.get("/api/dataset/grid.npz")
    assert r.status_code == 200
    z = np.load(io.BytesIO(r.content), allow_pickle=False)
    assert z["sst"].shape == (264, z["lats"].size, z["lons"].size) and z["ocean"].sum() > 1500
    assert np.isfinite(z["sst"][:, z["ocean"]]).mean() > 0.9 and str(z["months"][0]) == "2003-01"

    r = c.get(f"/api/notebook/x.ipynb?lang=en&month=2015-08&{DWH}&title=Prueba%20%27%22%0A&base=https://ejemplo.org&target=lite")
    assert r.status_code == 200
    assert 'filename="Golfo_Mexico_MIA_2015-08_-89.0000_28.0000_-88.0000_29.0000_en.ipynb"' in r.headers["content-disposition"]
    nb = r.json()
    assert nb["nbformat"] == 4 and nb["metadata"]["kernelspec"]["name"] == "python"
    param = next(cel for cel in nb["cells"] if "parameters" in cel["metadata"].get("tags", []))
    src = "".join(param["source"])
    ns = {}
    exec(src, ns)                      # la celda de parámetros es Python válido y solo define literales
    assert ns["SELECCION"] == "bbox=-89.0000,28.0000,-88.0000,29.0000" and ns["MES"] == "2015-08"
    assert ns["TITULO"] == "Prueba '\"" and ns["API"] == "https://ejemplo.org" and ns["IDIOMA"] == "en"
    malo = c.get("/api/notebook?base=javascript:alert(1)&title=" + "x" * 50).json()
    ns = {}
    exec("".join(next(cel for cel in malo["cells"] if cel["cell_type"] == "code")["source"]), ns)
    assert ns["API"] == "auto"
    assert c.get("/api/notebook?month=1990-01").status_code == 400
    assert c.get("/api/notebook?lang=fr").status_code == 422
    json.dumps(nb)


def test_radar_sar():
    m = ok(c.get("/api/sar/meta"))
    assert set(m["missions"]) == {"Sentinel-1", "ALOS PALSAR", "UAVSAR", "NISAR"}
    assert ok(c.get("/api/meta"))["sar"]["available"] == m["available"]
    # el proxy de vistas previas solo acepta servidores de ASF (evita SSRF)
    assert c.get("/api/sar/browse?u=https://ejemplo.org/x.jpg").status_code == 400
    assert c.get("/api/sar/browse?u=http://datapool.asf.alaska.edu/BROWSE/x.jpg").status_code == 400
    assert c.get("/api/sar/grid/xyz?year=2020").status_code == 400
    assert c.get("/api/sar/scenes?month=2020-06&months=9&bbox=-89,28,-88,29").status_code == 422
    if m["available"]:
        g = ok(c.get("/api/sar/grid/sar_bright?year=2020"))
        assert len(g["values"]) == 130 and len(g["values"][0]) == 180 and g["scenes"] > 0
        assert any(v is not None for fila in g["values"] for v in fila)
        assert ok(c.get("/api/sar/grid/sar_wind?year=2010"))["note"] == "no_sar_year"
        a = ok(c.get(f"/api/sar/area?{DWH}"))
        assert len(a["years"]) == 8 and a["all"]["n"] > 0 and 0 < a["all"]["wind"] < 20
        for ev_id in m["events"][:2]:
            e = ok(c.get(f"/api/sar/events/{ev_id}"))
            assert "summary" in e and isinstance(e["scenes"], list)
    # detector de manchas NISAR
    sl = ok(c.get("/api/sar/slicks"))
    assert sl["available"] == m["slicks"]["available"]
    assert c.get("/api/sar/slicks/..%2F..%2Fetc.png").status_code in (400, 404)
    assert c.get("/api/sar/slicks/NISAR_no_existe_123.png").status_code == 400
    if sl["available"]:
        e = sl["scenes"][0]
        assert e["image"].startswith("/api/sar/slicks/") and len(e["bounds"]) == 2
        r = c.get(e["image"])
        assert r.status_code == 200 and r.content[:4] == b"\x89PNG"
        for e in sl["scenes"]:
            for x in e["detections"]:
                assert x["confidence"] in ("high", "medium", "calm") and x["area_km2"] >= 1
                assert 18 <= x["lat"] <= 31 and -98 <= x["lon"] <= -80 and x["dr_db"] < 30
    if os.getenv("GOLFO_TEST_RED"):                  # búsqueda en vivo en ASF (requiere internet)
        s = ok(c.get(f"/api/sar/scenes?month=2010-06&{DWH}"))
        assert s["missions"]["ALOS PALSAR"]["total"] > 0


def test_errores():
    assert c.get("/api/area/summary?month=2010-05&bbox=1,2").status_code == 400
    assert c.get("/api/area/summary?month=1990-01&bbox=-89,28,-88,29").status_code == 400
    assert c.get("/api/grid/xyz?month=2010-05").status_code == 400
    assert c.get("/api/noexiste").status_code == 404


def test_protecciones():
    from backend import security
    r = c.get("/api/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    grande = "x" * (security.MAX_BODY + 10)
    assert c.post("/api/export/xlsx", content=grande, headers={"content-type": "application/json"}).status_code == 413
    ip = {"cf-connecting-ip": "203.0.113.7"}                 # IP de documentación (RFC 5737)
    codigos = [c.post("/api/export/xlsx", json={"sheets": []}, headers=ip).status_code for _ in range(security.LIMITE_EXPORT + 1)]
    assert codigos[-1] == 429 and 429 not in codigos[:-1]


def test_frontend():
    r = c.get("/")
    assert r.status_code == 200 and "<html" in r.text.lower()


if __name__ == "__main__":
    for nombre, f in list(globals().items()):
        if nombre.startswith("test_"):
            f(); print("PASS", nombre)
