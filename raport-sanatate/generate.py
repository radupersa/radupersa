#!/usr/bin/env python3
"""
Raport Sanatate Generator
Intrari:  data/corp.csv  · data/nutritie.csv  · data/activitati.json
Iesire:   raport.html

Ruleaza:  python3 generate.py
"""

import csv, json, math, os
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
OUT  = ROOT / "raport.html"

TDEE_FACTOR   = 1.45   # BMR × factor activitate moderata
PROT_OPT_LOW  = 1.6    # g/kg masa musculara
PROT_OPT_HIGH = 2.2    # g/kg masa musculara
MORNING_MAX_S = 120    # sub 2 min = rutina de dimineata, nu antrenament real
BREAK_THRESH  = 3      # zile consecutive fara antrenament = pauza semnificativa

# ─── Loaders ─────────────────────────────────────────────────────────────────

def load_corp():
    rows = []
    with open(DATA / "corp.csv") as f:
        for r in csv.DictReader(f):
            r["data"] = datetime.strptime(r["data"], "%Y-%m-%d")
            for k in ["greutate","grasime_proc","masa_musc_kg","musc_proc",
                      "BMR","body_score","varsta_corp","FC_repaus"]:
                r[k] = float(r[k]) if r.get(k) and r[k].strip() else None
            rows.append(r)
    return sorted(rows, key=lambda x: x["data"])

def load_nutritie():
    rows = []
    with open(DATA / "nutritie.csv") as f:
        for r in csv.DictReader(f):
            r["data"] = datetime.strptime(r["data"], "%Y-%m-%d")
            for k in ["kcal","proteine_g","grasimi_g","carbs_g"]:
                r[k] = float(r[k]) if r.get(k) and r[k].strip() else None
            rows.append(r)
    return sorted(rows, key=lambda x: x["data"])

def load_activitati():
    with open(DATA / "activitati.json") as f:
        acts = json.load(f)
    for a in acts:
        a["start_dt"] = datetime.fromisoformat(a["start_local"])
    return sorted(acts, key=lambda x: x["start_dt"])

# ─── Analysis ────────────────────────────────────────────────────────────────

SPORT_LABELS = {
    "WeightTraining": "Sala",
    "Ride": "Cycling",
    "MountainBikeRide": "MTB",
    "Walk": "Mers",
    "Run": "Alergare",
    "Workout": "Workout",
}

def sport_label(a):
    return a.get("name") or SPORT_LABELS.get(a["sport_type"], a["sport_type"])

def is_real(a):
    if a["sport_type"] == "Workout" and a["moving_time"] < MORNING_MAX_S:
        return False
    return True

def fmt_min(sec):
    return f"{sec/60:.1f} min"

def fmt_km(m):
    return f"{m/1000:.2f} km" if m else "—"

def analyze(corp, nutritie, activitati):
    start, end = corp[0], corp[-1]
    real    = [a for a in activitati if is_real(a)]
    morning = [a for a in activitati if not is_real(a)]

    # Nutrition — exclude days with < 500 kcal (likely incomplete)
    complete_nut = [r for r in nutritie if r["kcal"] and r["kcal"] >= 500]
    prot_days    = [r for r in complete_nut if r["proteine_g"]]
    fat_days     = [r for r in complete_nut if r["grasimi_g"]]
    carb_days    = [r for r in complete_nut if r["carbs_g"]]

    avg_kcal  = sum(r["kcal"] for r in complete_nut) / len(complete_nut) if complete_nut else 0
    avg_prot  = sum(r["proteine_g"] for r in prot_days) / len(prot_days) if prot_days else 0
    avg_fat   = sum(r["grasimi_g"]  for r in fat_days)  / len(fat_days)  if fat_days  else 0
    avg_carbs = sum(r["carbs_g"]    for r in carb_days) / len(carb_days) if carb_days else 0

    bmr  = end["BMR"] or 1680
    tdee = bmr * TDEE_FACTOR

    total_cal_burned = sum(a["total_calories"] for a in real)
    total_re         = sum(a["relative_effort"] or 0 for a in real)
    total_dist_m     = sum(a["distance"] or 0 for a in real)

    # Detect longest training break
    real_dates = sorted({a["start_dt"].date() for a in real})
    max_break, max_break_start, max_break_end = 0, None, None
    if real_dates:
        for i in range(1, len(real_dates)):
            gap = (real_dates[i] - real_dates[i-1]).days - 1
            if gap > max_break:
                max_break = gap
                max_break_start = real_dates[i-1] + timedelta(days=1)
                max_break_end   = real_dates[i] - timedelta(days=1)

    # Protein optimum based on last muscle mass
    musc = end["masa_musc_kg"] or 57.5
    prot_opt_low  = musc * PROT_OPT_LOW
    prot_opt_high = musc * PROT_OPT_HIGH

    return {
        "start": start,
        "end":   end,
        "period_days": (end["data"] - start["data"]).days,
        "delta_greutate": round((end["greutate"] or 0) - (start["greutate"] or 0), 1),
        "delta_grasime":  round((end["grasime_proc"] or 0) - (start["grasime_proc"] or 0), 1),
        "delta_body_score": int((end["body_score"] or 0) - (start["body_score"] or 0)),
        "delta_varsta":     int((end["varsta_corp"] or 0) - (start["varsta_corp"] or 0)),
        "real":     real,
        "morning":  morning,
        "total_cal_burned": total_cal_burned,
        "total_re":  total_re,
        "total_dist_km": total_dist_m / 1000,
        "avg_kcal":  avg_kcal,
        "avg_prot":  avg_prot,
        "avg_fat":   avg_fat,
        "avg_carbs": avg_carbs,
        "tdee":      tdee,
        "deficit":   tdee - avg_kcal,
        "prot_opt_low":  prot_opt_low,
        "prot_opt_high": prot_opt_high,
        "max_break":       max_break,
        "max_break_start": max_break_start,
        "max_break_end":   max_break_end,
        "complete_nut": complete_nut,
    }

# ─── HTML helpers ────────────────────────────────────────────────────────────

def bar(pct_of_max, color, max_w=100):
    w = min(max_w, max(0, int(pct_of_max)))
    return f'<div class="bar-bg"><div class="bar-fill bar-{color}" style="width:{w}%"></div></div>'

def delta_html(val, unit="", invert=False):
    if val is None: return '<span class="neu">—</span>'
    sign  = "▲" if val > 0 else "▼"
    cls   = ("neg" if val > 0 else "pos") if invert else ("pos" if val > 0 else "neg")
    if val == 0: cls, sign = "neu", "="
    return f'<span class="{cls}">{sign} {abs(val):.1f}{unit}</span>'

def ro_date(d):
    MONTHS = ["","Ian","Feb","Mar","Apr","Mai","Iun","Iul","Aug","Sep","Oct","Nov","Dec"]
    return f"{d.day} {MONTHS[d.month]}"

def sport_dot_class(a):
    st = a["sport_type"]
    if st == "WeightTraining": return "training", "T"
    if st in ("Ride","MountainBikeRide"): return "cycling", "C"
    if st == "Walk": return "morning", "W"
    if st == "Run":  return "training", "R"
    return "morning", "M"

# ─── CSS ─────────────────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f0f4f8; color: #1a202c; }

.header { background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%); color: white; padding: 40px 48px; }
.header h1 { font-size: 28px; font-weight: 700; }
.header p  { margin-top: 6px; color: #a0aec0; font-size: 14px; }
.header .badge { display: inline-block; margin-top: 12px; font-size: 11px; font-weight: 600;
  background: rgba(255,255,255,0.15); padding: 4px 12px; border-radius: 12px; color: #e2e8f0; }

.container { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }

.section-title { font-size: 18px; font-weight: 700; color: #2d3748;
  margin: 36px 0 16px; border-left: 4px solid #fc8181; padding-left: 12px; }
.section-title.blue   { border-left-color: #4299e1; }
.section-title.green  { border-left-color: #48bb78; }
.section-title.orange { border-left-color: #ed8936; }
.section-title.purple { border-left-color: #9f7aea; }

.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }
.kpi-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
.kpi-label { font-size: 11px; text-transform: uppercase; letter-spacing: .6px; color: #718096; }
.kpi-value { font-size: 28px; font-weight: 700; color: #2d3748; margin: 6px 0 2px; }
.kpi-delta { font-size: 13px; }
.pos { color: #48bb78; } .neg { color: #fc8181; } .neu { color: #a0aec0; } .warn { color: #ed8936; }

.alert { background: #fff5f5; border: 1px solid #fed7d7; border-left: 4px solid #fc8181;
  border-radius: 8px; padding: 16px 20px; margin-bottom: 8px; }
.alert.orange { background: #fffaf0; border-color: #fbd38d; border-left-color: #ed8936; }
.alert.green  { background: #f0fff4; border-color: #9ae6b4; border-left-color: #48bb78; }
.alert.blue   { background: #ebf8ff; border-color: #90cdf4; border-left-color: #4299e1; }
.alert h3 { font-size: 14px; font-weight: 700; color: #c53030; margin-bottom: 4px; }
.alert.orange h3 { color: #c05621; }
.alert.green  h3 { color: #276749; }
.alert.blue   h3 { color: #2b6cb0; }
.alert p { font-size: 13px; color: #718096; line-height: 1.6; }
.alert strong { color: #2d3748; }

.table-wrap { background: white; border-radius: 12px; overflow-x: auto; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #edf2f7; padding: 11px 16px; text-align: left; font-size: 11px;
  text-transform: uppercase; letter-spacing: .5px; color: #718096; }
td { padding: 11px 16px; border-top: 1px solid #f7fafc; }
tr:hover td { background: #f7fafc; }
.row-bad  { background: #fff5f5 !important; }
.row-good { background: #f0fff4 !important; }
.row-warn { background: #fffaf0 !important; }

.bar-wrap { display: flex; align-items: center; gap: 8px; }
.bar-bg   { flex: 1; background: #edf2f7; border-radius: 4px; height: 8px; max-width: 120px; }
.bar-fill { height: 100%; border-radius: 4px; }
.bar-blue   { background: #4299e1; }
.bar-green  { background: #48bb78; }
.bar-orange { background: #ed8936; }
.bar-red    { background: #fc8181; }
.bar-purple { background: #9f7aea; }

.insight-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
.insight { background: white; border-radius: 12px; padding: 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08); border-top: 3px solid #4299e1; }
.insight.green  { border-top-color: #48bb78; }
.insight.orange { border-top-color: #ed8936; }
.insight.red    { border-top-color: #fc8181; }
.insight.purple { border-top-color: #9f7aea; }
.insight h3 { font-size: 14px; font-weight: 700; color: #2d3748; margin-bottom: 8px; }
.insight p  { font-size: 13px; color: #718096; line-height: 1.6; }
.insight strong { color: #2d3748; }

.timeline { position: relative; }
.timeline::before { content: ''; position: absolute; left: 20px; top: 0; bottom: 0; width: 2px; background: #e2e8f0; }
.tl-item { position: relative; padding: 0 0 24px 52px; }
.tl-dot { position: absolute; left: 10px; top: 4px; width: 22px; height: 22px;
  border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; color: white; }
.tl-dot.training { background: #4299e1; }
.tl-dot.cycling  { background: #ed8936; }
.tl-dot.morning  { background: #a0aec0; }
.tl-date  { font-size: 11px; color: #a0aec0; text-transform: uppercase; letter-spacing: .5px; }
.tl-title { font-size: 15px; font-weight: 700; color: #2d3748; margin: 2px 0 4px; }
.tl-meta  { font-size: 13px; color: #718096; }
.tl-badge { display: inline-block; font-size: 11px; font-weight: 600;
  padding: 2px 8px; border-radius: 12px; margin: 4px 4px 0 0; }
.badge-blue   { background: #ebf8ff; color: #2b6cb0; }
.badge-green  { background: #f0fff4; color: #276749; }
.badge-orange { background: #fffaf0; color: #c05621; }
.badge-red    { background: #fff5f5; color: #c53030; }
.badge-gray   { background: #edf2f7; color: #718096; }

.nutrition-day { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #f7fafc; }
.nutrition-day:last-child { border-bottom: none; }
.nut-date     { font-size: 12px; font-weight: 700; color: #718096; width: 50px; flex-shrink: 0; }
.nut-bar-wrap { flex: 1; display: flex; flex-direction: column; gap: 3px; }
.nut-bar-row  { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #a0aec0; }
.nut-bar-bg   { flex: 1; background: #edf2f7; border-radius: 3px; height: 6px; max-width: 240px; }
.nut-bar-fill { height: 100%; border-radius: 3px; }
.nut-label { width: 34px; }
.nut-value { width: 60px; text-align: right; font-size: 12px; font-weight: 600; color: #2d3748; }

.macro-pill { display: inline-flex; align-items: center; gap: 4px; font-size: 11px;
  font-weight: 600; padding: 2px 8px; border-radius: 10px; margin-right: 4px; }
.macro-p { background: #ebf8ff; color: #2b6cb0; }
.macro-f { background: #fffaf0; color: #c05621; }
.macro-c { background: #f0fff4; color: #276749; }

footer { text-align: center; padding: 32px; color: #a0aec0; font-size: 12px; }
"""

# ─── Section builders ─────────────────────────────────────────────────────────

def build_alerts(s, corp, nutritie):
    html = '<div style="margin-top: 16px; display: flex; flex-direction: column; gap: 8px;">'

    # Training break alert
    if s["max_break"] and s["max_break"] >= BREAK_THRESH:
        d1 = ro_date(s["max_break_start"])
        d2 = ro_date(s["max_break_end"])
        html += f"""
    <div class="alert orange">
      <h3>⚠ Pauza de antrenament: {s['max_break']} zile fara sesiune reala ({d1}–{d2})</h3>
      <p>Strava confirma ca intre <strong>{d1} si {d2}</strong> nu a existat nicio sesiune
      de sala sau ciclism. Rutinele de dimineata inregistrate (sub 2 minute) reprezinta
      probabil mobilitate/stretching, nu antrenament propriu-zis.</p>
    </div>"""

    # Weight gain alert
    dw = s["delta_greutate"]
    if dw > 1.0:
        prev = corp[-2] if len(corp) >= 2 else None
        prev_txt = ""
        if prev:
            dw2 = round((s["end"]["greutate"] or 0) - (prev["greutate"] or 0), 1)
            days2 = (s["end"]["data"] - prev["data"]).days
            prev_txt = f' Fata de ultima masurare din {ro_date(prev["data"])} ({prev["greutate"]} kg), cresterea este de <strong>+{dw2} kg in {days2} zile</strong>.'
        html += f"""
    <div class="alert">
      <h3>Greutate crescuta cu +{dw} kg fata de startul din {ro_date(s['start']['data'])} — cel mai ridicat nivel din perioada</h3>
      <p>De la <strong>{s['start']['greutate']} kg</strong> ({ro_date(s['start']['data'])}) la
      <strong>{s['end']['greutate']} kg</strong> ({ro_date(s['end']['data'])}).{prev_txt}
      Tendinta negativa s-a accelerat.</p>
    </div>"""

    # Nutrition log incomplete alert
    if s["avg_kcal"] > 0 and dw > 0.5 and s["avg_kcal"] < s["tdee"]:
        html += f"""
    <div class="alert blue">
      <h3>Nutritie logata: ~{s['avg_kcal']:.0f} kcal/zi — dar greutatea a crescut, semn ca logul este incomplet</h3>
      <p>Daca aportul real ar fi fost de {s['avg_kcal']:.0f} kcal/zi cu TDEE estimat ~{s['tdee']:.0f} kcal,
      greutatea ar fi trebuit sa <em>scada</em>. Cresterea de <strong>+{dw} kg</strong> sugereaza
      ca o parte semnificativa din mancare nu a fost logata.</p>
    </div>"""

    html += "</div>"
    return html


def build_kpi_grid(s):
    end, start = s["end"], s["start"]
    dw  = s["delta_greutate"]
    dg  = s["delta_grasime"]
    dbs = s["delta_body_score"]
    dv  = s["delta_varsta"]

    w_cls  = "neg" if dw > 0 else "pos"
    g_cls  = "neg" if dg > 0 else "pos"
    bs_cls = "pos" if dbs > 0 else ("neg" if dbs < 0 else "neu")
    v_cls  = "neg" if dv > 0 else ("pos" if dv < 0 else "neu")

    prot_cls = "neg" if s["avg_prot"] < s["prot_opt_low"] else "pos"

    return f"""
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">Greutate</div>
      <div class="kpi-value">{end['greutate']} kg</div>
      <div class="kpi-delta {w_cls}">{'▲' if dw>0 else '▼'} {abs(dw):.1f} kg fata de start ({start['greutate']} kg)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Grasime corporala</div>
      <div class="kpi-value">{end['grasime_proc'] or '—'}%</div>
      <div class="kpi-delta {g_cls}">{'▲' if dg>0 else '▼'} {abs(dg):.1f}% fata de start ({start['grasime_proc']}%)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Masa musculara</div>
      <div class="kpi-value">{end['masa_musc_kg'] or '—'} kg</div>
      <div class="kpi-delta neu">Estimat · {end['musc_proc'] or '—'}% din greutate</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Body Score</div>
      <div class="kpi-value">{int(end['body_score']) if end['body_score'] else '—'}</div>
      <div class="kpi-delta {bs_cls}">{'▲' if dbs>0 else '▼' if dbs<0 else '='} {abs(dbs)} fata de start ({int(start['body_score']) if start['body_score'] else '—'})</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Varsta corporala</div>
      <div class="kpi-value">{int(end['varsta_corp']) if end['varsta_corp'] else '—'} ani</div>
      <div class="kpi-delta {v_cls}">{'▲' if dv>0 else '▼' if dv<0 else '='} {abs(dv)} ani fata de start ({int(start['varsta_corp']) if start['varsta_corp'] else '—'})</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Calorii arse (antren.)</div>
      <div class="kpi-value">{s['total_cal_burned']:,}</div>
      <div class="kpi-delta neu">{len(s['real'])} sesiuni reale · {s['total_dist_km']:.1f} km</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Medie kcal/zi (logat)</div>
      <div class="kpi-value">{s['avg_kcal']:.0f}</div>
      <div class="kpi-delta neu">TDEE estimat: ~{s['tdee']:.0f} kcal/zi</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Proteina medie/zi</div>
      <div class="kpi-value">{s['avg_prot']:.0f}g</div>
      <div class="kpi-delta {prot_cls}">Optim: {s['prot_opt_low']:.0f}–{s['prot_opt_high']:.0f}g/zi</div>
    </div>
  </div>"""


def build_corp_table(corp):
    MONTHS = ["","Ian","Feb","Mar","Apr","Mai","Iun","Iul","Aug","Sep","Oct","Nov","Dec"]

    def row_class(i, total):
        if i == 0: return "row-good"
        if i == total - 1: return "row-bad"
        return ""

    html = """
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Data</th><th>Greutate</th><th>Grasime %</th>
          <th>Masa musc. (kg)</th><th>Musc. %</th>
          <th>BMR (kcal)</th><th>Body Score</th>
          <th>Varsta corp.</th><th>FC repaus</th>
        </tr>
      </thead>
      <tbody>"""

    for i, r in enumerate(corp):
        rc = row_class(i, len(corp))
        d  = r["data"]
        label = "start" if i == 0 else ("actual ★" if i == len(corp)-1 else "")
        lspan = f' <span style="color:#{"a0aec0" if i==0 else "fc8181"};font-size:11px;">{label}</span>' if label else ""

        g    = r["grasime_proc"] or 0
        g_pct = min(100, int(g / 30 * 100))
        g_color = "green" if g < 22 else ("orange" if g < 24 else "red")

        fc = int(r["FC_repaus"]) if r["FC_repaus"] else "—"
        bs = int(r["body_score"]) if r["body_score"] else "—"
        vc = int(r["varsta_corp"]) if r["varsta_corp"] else "—"
        musc = r["masa_musc_kg"] or "—"
        musc_p = r["musc_proc"] or "—"
        bmr  = int(r["BMR"]) if r["BMR"] else "—"

        html += f"""
        <tr class="{rc}">
          <td><strong>{d.day} {MONTHS[d.month]}</strong>{lspan}</td>
          <td>{r['greutate']} kg</td>
          <td><div class="bar-wrap">{g}% {bar(g_pct, g_color)}</div></td>
          <td>{'~' if i==len(corp)-1 else ''}{musc} kg</td>
          <td>{'~' if i==len(corp)-1 else ''}{musc_p}%</td>
          <td>{'~' if i==len(corp)-1 else ''}{bmr}</td>
          <td><strong>{bs}</strong></td>
          <td>{vc}</td>
          <td>{fc}</td>
        </tr>"""

    html += """
      </tbody>
    </table>
  </div>"""
    return html


def build_nutrition_section(nutritie, s):
    if not nutritie:
        return "<p style='color:#a0aec0;padding:16px;'>Nu exista date de nutritie.</p>"

    d_start = nutritie[0]["data"]
    d_end   = nutritie[-1]["data"]
    period  = f"{ro_date(d_start)}–{ro_date(d_end)} {d_end.year}"

    max_kcal = max((r["kcal"] or 0) for r in nutritie) or 2500

    html = f'<div class="table-wrap" style="padding: 20px 24px;">'

    for r in nutritie:
        kcal = r["kcal"]
        prot = r["proteine_g"]
        fat  = r["grasimi_g"]
        carb = r["carbs_g"]
        note = r.get("note","")

        # incomplete day
        is_incomplete = not kcal or kcal < 500

        kcal_w = int((kcal or 0) / max_kcal * 100) if kcal else 0
        kcal_color = "red" if (kcal and kcal < 1000) else ("blue" if (kcal and kcal > 1800) else "orange")
        kcal_style = "" if not is_incomplete else "color:#a0aec0;"

        prot_ok = prot and prot >= s["prot_opt_low"]
        prot_color = "green" if prot_ok else ("orange" if (prot and prot >= 80) else "red")
        prot_w = int(prot / s["prot_opt_high"] * 100) if prot else 0

        fat_w = int((fat or 0) / 100 * 100) if fat else 0
        fat_high = fat and fat > 80
        fat_style = "background:#fff5f5;color:#c53030;" if fat_high else ""

        border_style = ""
        date_style   = ""
        if is_incomplete or (kcal and kcal < 1200):
            border_style = 'border-left: 3px solid #e2e8f0; padding-left: 8px; margin-left: -8px;'
            date_style   = 'color:#a0aec0;'

        kcal_val = f"{int(kcal)}" if kcal else "—"
        prot_val = f"{int(prot)}g {'✓✓' if (prot and prot>=s['prot_opt_high']) else '✓' if prot_ok else '⚠'}" if prot else "—"
        prot_v_style = f"color:#{'48bb78' if prot_ok else ('ed8936' if (prot and prot>=80) else 'fc8181')};"

        html += f'''
    <div class="nutrition-day" style="{border_style}">
      <div class="nut-date" style="{date_style}">{ro_date(r["data"])}</div>
      <div class="nut-bar-wrap">
        <div class="nut-bar-row">
          <span class="nut-label" style="color:#4299e1;">kcal</span>
          <div class="nut-bar-bg"><div class="nut-bar-fill bar-{kcal_color}" style="width:{kcal_w}%"></div></div>
          <span class="nut-value" style="{kcal_style}">{kcal_val}</span>
        </div>'''

        if prot is not None:
            html += f'''
        <div class="nut-bar-row">
          <span class="nut-label" style="color:#{'48bb78' if prot_ok else 'ed8936'};">Prot</span>
          <div class="nut-bar-bg"><div class="nut-bar-fill bar-{prot_color}" style="width:{min(100,prot_w)}%"></div></div>
          <span class="nut-value" style="{prot_v_style}">{prot_val}</span>
        </div>'''

        html += '<div>'
        if fat is not None:
            html += f'<span class="macro-pill macro-f" style="{fat_style}">Grasimi {int(fat)}g{"  ⚠" if fat_high else ""}</span>'
        if carb is not None:
            html += f'<span class="macro-pill macro-c">Carbs {int(carb)}g</span>'
        if note:
            for part in note.split(";"):
                part = part.strip()
                if part:
                    html += f'<span class="tl-badge badge-gray">{part}</span>'
        html += '</div></div></div>'

    # Summary row
    cn = s["complete_nut"]
    if cn:
        html += f'''
    <div style="margin-top:16px;padding:12px 0;border-top:2px solid #edf2f7;
      display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;">
      <div>
        <div style="font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:.5px;">Medie kcal/zi</div>
        <div style="font-size:22px;font-weight:700;color:#2d3748;margin-top:4px;">{s['avg_kcal']:.0f}</div>
        <div style="font-size:12px;color:#718096;">{period} ({len(cn)} zile complete)</div>
      </div>
      <div>
        <div style="font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:.5px;">Medie proteina/zi</div>
        <div style="font-size:22px;font-weight:700;color:#fc8181;margin-top:4px;">~{s['avg_prot']:.0f}g</div>
        <div style="font-size:12px;color:#718096;">Optim: {s['prot_opt_low']:.0f}–{s['prot_opt_high']:.0f}g/zi</div>
      </div>
      <div>
        <div style="font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:.5px;">Medie grasimi/zi</div>
        <div style="font-size:22px;font-weight:700;color:#ed8936;margin-top:4px;">~{s['avg_fat']:.0f}g</div>
        <div style="font-size:12px;color:#718096;">Unele zile ridicate</div>
      </div>
      <div>
        <div style="font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:.5px;">Medie carbs/zi</div>
        <div style="font-size:22px;font-weight:700;color:#48bb78;margin-top:4px;">~{s['avg_carbs']:.0f}g</div>
        <div style="font-size:12px;color:#718096;">In limite normale</div>
      </div>
      <div>
        <div style="font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:.5px;">Deficit estimat</div>
        <div style="font-size:22px;font-weight:700;color:#4299e1;margin-top:4px;">~{s['deficit']:.0f} kcal</div>
        <div style="font-size:12px;color:#718096;">vs TDEE ~{s['tdee']:.0f} kcal/zi</div>
      </div>
    </div>'''

    html += "</div>"
    return html


def build_activity_timeline(activitati, s):
    html = '<div class="timeline">'

    real_set = {a["id"] for a in s["real"]}

    # Group morning routines into break periods
    break_start = s["max_break_start"]
    break_end   = s["max_break_end"]

    shown_break = False
    morning_in_break = []

    for a in activitati:
        aid = a["id"]
        dt  = a["start_dt"]

        if not is_real(a):
            if break_start and break_end and break_start <= dt.date() <= break_end:
                morning_in_break.append(a)
            continue

        # Flush break block before next real activity
        if morning_in_break and not shown_break:
            shown_break = True
            d1 = ro_date(morning_in_break[0]["start_dt"])
            d2 = ro_date(morning_in_break[-1]["start_dt"])
            badges = " ".join(
                f'<span class="tl-badge badge-gray">{ro_date(m["start_dt"])}: {m["moving_time"]}s / {m["total_calories"]} kcal</span>'
                for m in morning_in_break
            )
            html += f'''
    <div class="tl-item" style="opacity:0.6;">
      <div class="tl-dot morning" style="font-size:9px;background:#e2e8f0;">M</div>
      <div class="tl-date">{d1}–{d2} — pauza antrenament</div>
      <div class="tl-title" style="color:#a0aec0;">{len(morning_in_break)}× Morning Workout (rutine scurte)</div>
      <div class="tl-meta" style="color:#a0aec0;">Durata: sub 1 minut fiecare · cateva kcal / sesiune · Zero antrenament real.</div>
      <div style="margin-top:6px;">{badges}</div>
    </div>'''

        dot_cls, dot_ltr = sport_dot_class(a)
        dist_txt  = f" · {fmt_km(a['distance'])}" if a.get("distance") else ""
        elev_txt  = f" · ↑{a['elevation_gain']:.0f}m" if a.get("elevation_gain") else ""
        ach_txt   = f" · {a['achievement_count']} achiev." if a.get("achievement_count") else ""
        pr_txt    = f" · {a['pr_count']} PR-uri 🏆" if a.get("pr_count") else ""

        hr_avg = a.get("avg_hr")
        hr_max = a.get("avg_hr") and a.get("max_hr")

        badges = f'<span class="tl-badge badge-green">{int(a["total_calories"])} kcal</span>'
        if hr_avg:
            badges += f'<span class="tl-badge badge-blue">FC med {hr_avg:.0f} bpm</span>'
        if a.get("max_hr"):
            badges += f'<span class="tl-badge badge-red">FC max {int(a["max_hr"])} bpm</span>'
        if a.get("relative_effort"):
            badges += f'<span class="tl-badge badge-orange">RE {int(a["relative_effort"])}</span>'
        if a.get("avg_cadence"):
            badges += f'<span class="tl-badge badge-blue">Cadenta {a["avg_cadence"]:.1f} rpm</span>'
        if a.get("avg_watts"):
            badges += f'<span class="tl-badge badge-blue">{a["avg_watts"]:.0f}W avg</span>'
        if a.get("pr_count"):
            badges += f'<span class="tl-badge badge-green">{a["pr_count"]} PR-uri 🏆</span>'
        if a.get("achievement_count") and a["achievement_count"] > a.get("pr_count",0):
            badges += f'<span class="tl-badge badge-orange">{a["achievement_count"]} achievements</span>'
        if a.get("kudos_count"):
            badges += f'<span class="tl-badge badge-gray">{a["kudos_count"]} kudos</span>'

        desc = a.get("description","") or ""
        meta = f"{fmt_min(a['moving_time'])}{dist_txt}{elev_txt}"

        html += f'''
    <div class="tl-item">
      <div class="tl-dot {dot_cls}">{dot_ltr}</div>
      <div class="tl-date">{dt.strftime("%d %B %Y")}</div>
      <div class="tl-title">{a["name"]} — {meta}</div>
      <div class="tl-meta">{desc if desc and len(desc)<100 else ""}</div>
      <div>{badges}</div>
    </div>'''

    html += "</div>"
    return html


def build_activity_table(s):
    real = s["real"]
    if not real:
        return "<p style='color:#a0aec0;padding:16px;'>Nu exista activitati reale.</p>"

    html = """
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Data</th><th>Sport</th><th>Durata</th><th>Calorii</th>
          <th>FC medie</th><th>FC max</th><th>Efort rel.</th><th>Distanta / Note</th>
        </tr>
      </thead>
      <tbody>"""

    total_cal = total_re = total_dist = 0

    for a in real:
        dt = a["start_dt"]
        hr_avg = f'{a["avg_hr"]:.0f}' if a.get("avg_hr") else "—"
        hr_max = f'{int(a["max_hr"])}' if a.get("max_hr") else "—"
        re_val = int(a["relative_effort"]) if a.get("relative_effort") else 0
        dist   = a.get("distance") or 0
        note   = fmt_km(dist) if dist else ("1 PR" if a.get("pr_count") else "—")
        if a.get("pr_count") and dist:
            note += f' · {a["pr_count"]} PR'

        total_cal  += int(a["total_calories"])
        total_re   += re_val
        total_dist += dist

        hr_bar = ""
        if a.get("avg_hr"):
            pct = int(a["avg_hr"] / 200 * 100)
            hr_bar = f'<div class="bar-wrap">{hr_avg} {bar(pct, "blue")}</div>'
        else:
            hr_bar = "—"

        html += f"""
        <tr>
          <td>{ro_date(dt)} {dt.year}</td>
          <td>{sport_label(a)}</td>
          <td>{fmt_min(a['moving_time'])}</td>
          <td>{int(a['total_calories'])}</td>
          <td>{hr_bar}</td>
          <td>{hr_max}</td>
          <td>RE {re_val}</td>
          <td>{note}</td>
        </tr>"""

    html += f"""
        <tr style="font-weight:700;background:#edf2f7;">
          <td>TOTAL</td>
          <td>{len(real)} sesiuni reale</td>
          <td>{fmt_min(sum(a['moving_time'] for a in real))}</td>
          <td>{total_cal}</td>
          <td>—</td><td>—</td>
          <td>RE {total_re}</td>
          <td>{fmt_km(total_dist)}</td>
        </tr>
      </tbody>
    </table>
  </div>"""
    return html


def build_insights(s):
    dw = s["delta_greutate"]
    prot_gap = s["avg_prot"] < s["prot_opt_low"]
    big_break = s["max_break"] and s["max_break"] >= BREAK_THRESH

    html = '<div class="insight-grid">'

    if big_break:
        d1 = ro_date(s["max_break_start"]) if s["max_break_start"] else "—"
        d2 = ro_date(s["max_break_end"])   if s["max_break_end"]   else "—"
        html += f"""
    <div class="insight red">
      <h3>Pauza de {s['max_break']} zile + posibil surplus caloric</h3>
      <p>Absenta antrenamentului intre <strong>{d1} si {d2}</strong>, combinata cu un aport caloric
      probabil mai mare decat cel logat, a dus la crestere in greutate. Fara stimulul mecanic al
      antrenamentului, surplusul caloric se depune preferential ca grasime.</p>
    </div>"""

    if dw > 0.5 and s["avg_kcal"] > 0 and s["avg_kcal"] < s["tdee"]:
        html += f"""
    <div class="insight red">
      <h3>Logul de nutritie este incomplet</h3>
      <p>Aplicatia arata ~{s['avg_kcal']:.0f} kcal/zi medie, dar greutatea a crescut cu
      <strong>+{dw} kg</strong> in {s['period_days']} zile. Daca aportul real ar fi sub TDEE
      (~{s['tdee']:.0f} kcal), greutatea ar fi trebuit sa scada.
      Fara date reale, nu poti sti daca esti in deficit sau surplus.</p>
    </div>"""

    if prot_gap:
        html += f"""
    <div class="insight red">
      <h3>Proteina — principala problema a nutritiei loggate</h3>
      <p>Media de <strong>~{s['avg_prot']:.0f}g proteina/zi</strong> este sub optimul de
      <strong>{s['prot_opt_low']:.0f}–{s['prot_opt_high']:.0f}g/zi</strong>.
      Insuficienta proteinei in combinatie cu pauze de antrenament creste riscul de catabolism muscular.</p>
    </div>"""

    # Find best activity
    best = max(s["real"], key=lambda a: a.get("relative_effort") or 0) if s["real"] else None
    if best and (best.get("relative_effort") or 0) > 50:
        html += f"""
    <div class="insight green">
      <h3>Sesiunea de varf: {best['name']}</h3>
      <p>Cu <strong>RE {int(best['relative_effort'])}</strong>
      {'si FC maxima de ' + str(int(best['max_hr'])) + ' bpm' if best.get('max_hr') else ''},
      {('si ' + str(best['pr_count']) + ' PR-uri') if best.get('pr_count') else ''}
      aceasta sesiune demonstreaza capacitate cardiovasculara excelenta. Nivelul aerobic este un atu real.</p>
    </div>"""

    html += "</div>"
    return html


def build_recommendations(s):
    prot_needed = int(math.ceil(s["prot_opt_low"]))

    html = '<div class="insight-grid">'
    html += f"""
    <div class="insight red">
      <h3>1. Reia antrenamentul — consecventa 4x/saptamana</h3>
      <p>Obiectiv realist: <strong>Push + Pull + Legs + 1 Cycling</strong> pe saptamana.
      Fiecare zi de inactivitate, in combinatie cu un surplus caloric, accelereaza acumularea de grasime.</p>
    </div>
    <div class="insight red">
      <h3>2. Proteina: minimum {prot_needed}g in fiecare zi</h3>
      <p>Obiectiv imediat: <strong>≥ {prot_needed}g proteina zilnic</strong>, indiferent de calorii.
      Surse recomandate la fiecare masa: oua, piept pui, branza cottage, ton, shake proteic.
      Nu mai accepta nicio zi sub 100g.</p>
    </div>
    <div class="insight orange">
      <h3>3. Logheza tot ce mananci — onest si complet</h3>
      <p>Datele actuale sugereaza un log incomplet. Un deficit real nu poate fi gestionat fara
      date reale. Chiar daca numarul e mare, datele corecte sunt mai valoroase decat datele
      care "arata bine".</p>
    </div>
    <div class="insight green">
      <h3>4. Mentine ciclismul — cel mai bun instrument cardio</h3>
      <p>Sesiunile de cycling au generat cel mai mare efort relativ si PR-uri, cu impact
      cardiovascular exceptional. O sesiune/saptamana de ciclism compenseaza 2 sesiuni de sala
      din punct de vedere cardiovascular.</p>
    </div>"""

    # Weight target
    target_w = round(s["start"]["greutate"] or 78, 1)
    target_g  = round((s["start"]["grasime_proc"] or 22) - 0.5, 1)
    html += f"""
    <div class="insight purple">
      <h3>Obiectiv realist: 4–6 saptamani</h3>
      <p>Cu antrenament consistent 4×/saptamana, proteina ≥{prot_needed}g/zi si log alimentar complet:
      <strong>Greutate tinta: {target_w} kg</strong> ·
      Grasime corporala sub <strong>{target_g}%</strong> ·
      Body Score revenire la <strong>{int((s['start']['body_score'] or 80)+1)}</strong>.
      Sunt realizabile, dar necesita consecventa reala.</p>
    </div>"""

    html += "</div>"
    return html

# ─── Main ─────────────────────────────────────────────────────────────────────

def generate():
    corp       = load_corp()
    nutritie   = load_nutritie()
    activitati = load_activitati()

    s = analyze(corp, nutritie, activitati)

    start_str = f"{ro_date(s['start']['data'])} {s['start']['data'].year}"
    end_str   = f"{ro_date(s['end']['data'])} {s['end']['data'].year}"
    today     = datetime.now().strftime("%d %B %Y")

    nut_range = ""
    if nutritie:
        nut_range = f" · Nutritie {ro_date(nutritie[0]['data'])}–{ro_date(nutritie[-1]['data'])}"

    html = f"""<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Raport Sanatate — {s['end']['data'].strftime('%d %b %Y')}</title>
<style>
{CSS}
</style>
</head>
<body>

<div class="header">
  <h1>Raport Sanatate &amp; Performanta</h1>
  <p>Persa Radu · Perioada: {start_str} → {end_str} · {len(corp)} masuratori corporale · {len(s['real'])} antrenamente reale</p>
  <span class="badge">Actualizat {today}{nut_range} &amp; activitate Strava</span>
</div>

<div class="container">
"""

    # Alerts
    html += build_alerts(s, corp, nutritie)

    # KPI
    html += f'\n  <div class="section-title blue" style="margin-top:32px;">Evolutie globala ({ro_date(s["start"]["data"])} = start → {ro_date(s["end"]["data"])} = actual)</div>'
    html += build_kpi_grid(s)

    # Body composition
    html += '\n  <div class="section-title">Compozitie corporala — evolutie cronologica</div>'
    html += build_corp_table(corp)
    html += f"""
  <p style="font-size:11px;color:#a0aec0;margin-top:8px;padding-left:4px;">★ Ultima masurare. Valorile marcate cu ~ sunt estimate pe baza tendintei anterioare.</p>"""

    # Nutrition
    if nutritie:
        html += f'\n  <div class="section-title green">Nutritie — Analiza zilnica {ro_date(nutritie[0]["data"])}–{ro_date(nutritie[-1]["data"])}</div>'
        html += build_nutrition_section(nutritie, s)

    # Activity timeline
    if activitati:
        html += f'\n  <div class="section-title blue">Activitati fizice — {ro_date(s["start"]["data"])}–{ro_date(s["end"]["data"])}</div>'
        html += build_activity_timeline(activitati, s)

    # Activity table
    if s["real"]:
        html += '\n  <div class="section-title blue">Rezumat sesiuni reale</div>'
        html += build_activity_table(s)

    # Insights
    html += '\n  <div class="section-title orange">Correlatii &amp; Interpretari</div>'
    html += build_insights(s)

    # Recommendations
    html += '\n  <div class="section-title blue">Plan de actiune — Urmatoarele 2 saptamani</div>'
    html += build_recommendations(s)

    html += "\n</div>\n"
    html += f"""
<footer>
  Raport generat {today} · Surse: corp.csv ({len(corp)} masuratori) · activitati.json ({len(activitati)} activitati Strava) · nutritie.csv ({len(nutritie)} zile)
</footer>
</body>
</html>"""

    OUT.write_text(html, encoding="utf-8")
    print(f"✓ Generat: {OUT}")
    print(f"  Perioada: {start_str} → {end_str}")
    print(f"  Corp: {len(corp)} masuratori · Activitati: {len(s['real'])} reale + {len(s['morning'])} morning")
    print(f"  Nutritie: {len(nutritie)} zile ({len(s['complete_nut'])} complete)")

if __name__ == "__main__":
    generate()
