#!/usr/bin/env python3
"""
Raport Evolutie Exercitii
Citeste fisiere .fit din data/fit/ si genereaza evolutie.html

Ruleaza:  python3 evolutie.py
Cerinte:  pip install garmin-fit-sdk
"""

import json, math, os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
FIT  = ROOT / "data" / "fit"
OUT  = ROOT / "evolutie.html"

# ─── FIT profile lookups ──────────────────────────────────────────────────────

def _build_lookups():
    try:
        import garmin_fit_sdk.profile as p
    except ImportError:
        return {}, {}
    types = p.Profile.get("types", {})
    cat_map  = types.get("exercise_category", {})           # {0: 'bench_press', ...}
    sub_maps = {
        cat: types.get(f"{cat}_exercise_name", {})
        for cat in cat_map.values()
    }
    return cat_map, sub_maps

CAT_MAP, SUB_MAPS = _build_lookups()

RO_EXERCISE = {
    # Presa piept
    "bench_press":                      "Presa piept",
    "barbell_bench_press":              "Presa piept bara",
    "dumbbell_bench_press":             "Presa piept gantere",
    "incline_barbell_bench_press":      "Presa inclinata bara",
    "incline_dumbbell_bench_press":     "Presa inclinata gantere",
    "decline_dumbbell_bench_press":     "Presa declinata gantere",
    "close_grip_barbell_bench_press":   "Presa piept priza ingusta",
    # Umeri / impingere
    "push_up":                          "Flotari",
    "shoulder_press":                   "Presa umeri",
    "barbell_shoulder_press":           "Presa umeri bara",
    "overhead_barbell_press":           "Presa umeri bara",
    "dumbbell_shoulder_press":          "Presa umeri gantere",
    "overhead_dumbbell_press":          "Presa umeri gantere",
    "lateral_raise":                    "Ridicari laterale",
    "dumbbell_lateral_raise":           "Ridicari laterale gantere",
    "front_raise":                      "Ridicari frontale",
    "dumbbell_front_raise":             "Ridicari frontale gantere",
    "triceps_extension":                "Extensie triceps",
    "cable_triceps_extension":          "Extensie triceps scripete",
    "ez_bar_overhead_triceps_extension":"Extensie triceps EZ",
    "overhead_triceps_extension":       "Extensie triceps deasupra",
    # Tractiune / spate
    "row":                              "Vaslit",
    "barbell_row":                      "Vaslit bara",
    "dumbbell_row":                     "Vaslit gantere",
    "seated_cable_row":                 "Vaslit scripete",
    "pull_up":                          "Tractiuni",
    "chin_up":                          "Tractiuni supinatie",
    "lat_pulldown":                     "Tractiuni scripete",
    "close_grip_lat_pulldown":          "Tractiuni scripete priza ingusta",
    "curl":                             "Flexii biceps",
    "barbell_curl":                     "Flexii bara",
    "dumbbell_curl":                    "Flexii gantere",
    "hammer_curl":                      "Flexii hammer",
    "shrug":                            "Ridicari umeri",
    "barbell_shrug":                    "Ridicari umeri bara",
    "dumbbell_shrug":                   "Ridicari umeri gantere",
    # Picioare
    "squat":                            "Genuflexiuni",
    "barbell_squat":                    "Genuflexiuni bara",
    "back_squat":                       "Genuflexiuni bara spate",
    "front_squat":                      "Genuflexiuni bara fata",
    "goblet_squat":                     "Genuflexiuni goblet",
    "leg_press":                        "Presa picioare",
    "deadlift":                         "Indreptari",
    "barbell_deadlift":                 "Indreptari bara",
    "romanian_deadlift":                "Indreptari romanesti",
    "sumo_deadlift":                    "Indreptari sumo",
    "leg_curl":                         "Flexii picioare",
    "leg_extension":                    "Extensii picioare",
    "calf_raise":                       "Ridicari pe varfuri",
    "standing_calf_raise":              "Ridicari pe varfuri",
    "seated_calf_raise":                "Ridicari pe varfuri asezat",
    "lunge":                            "Fandari",
    "barbell_lunge":                    "Fandari bara",
    "dumbbell_lunge":                   "Fandari gantere",
    "hip_raise":                        "Ridicari solduri",
    "barbell_hip_thrust":               "Impingeri solduri bara",
    # Core
    "plank":                            "Plank",
    "crunch":                           "Abdomen",
    "sit_up":                           "Abdomene",
    "leg_raise":                        "Ridicari picioare",
    "hanging_leg_raise":                "Ridicari picioare agatat",
    # Fluturari
    "flye":                             "Fluturari",
    "cable_fly":                        "Fluturari scripete",
    "dumbbell_fly":                     "Fluturari gantere",
    "dumbbell_flye":                    "Fluturari gantere",
    "cable_crossover":                  "Fluturari scripete",
    # Olympic / functional
    "olympic_lift":                     "Ridicare olimpica",
    "power_clean":                      "Power clean",
    "clean_and_jerk":                   "Clean & jerk",
    "snatch":                           "Smuls",
    "kettlebell_swing":                 "Kettlebell swing",
    # Altele
    "core":                             "Core",
    "cardio":                           "Cardio",
    "banded_exercises":                 "Exercitii cu banda",
    "pull_apart":                       "Band pull-apart",
    "warm_up":                          "Incalzire",
}

def exercise_name(cat_raw, sub_raw):
    """Returneaza numele human-readable al exercitiului."""
    cat_str = str(cat_raw).lower().replace(" ", "_") if cat_raw is not None else ""

    # sub_raw poate fi int (index in profil) sau string deja rezolvat
    sub_str = ""
    if sub_raw is not None:
        if isinstance(sub_raw, int):
            # Lookup in profilul FIT: {category}_exercise_name[str(index)]
            resolved = SUB_MAPS.get(cat_str, {}).get(str(sub_raw))
            sub_str = resolved.lower().replace(" ", "_") if resolved else ""
        else:
            sub_str = str(sub_raw).lower().replace(" ", "_")

    # Incearca sub-tip mai specific intai, apoi categoria
    for key in (sub_str, cat_str):
        if key and key in RO_EXERCISE:
            return RO_EXERCISE[key]

    # Fallback: curata si capitalizeaza numele original
    name = sub_str or cat_str
    return name.replace("_", " ").title() if name else "Exercitiu necunoscut"

# ─── FIT parser ───────────────────────────────────────────────────────────────

FIT_EPOCH = datetime(1989, 12, 31, 0, 0, 0)

def fit_ts(raw):
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return FIT_EPOCH + timedelta(seconds=raw)
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=None) if raw.tzinfo else raw
    try:
        return datetime.fromisoformat(str(raw))
    except Exception:
        return None

def parse_sets_from_fit(path: Path) -> list[dict]:
    """
    Extrage toate seturile active dintr-un fisier .fit.
    Returneaza lista de dicts: {date, exercise, category, sub_category,
                                reps, weight_kg, duration_s, session_date}
    """
    try:
        from garmin_fit_sdk import Decoder, Stream
        stream  = Stream.from_file(str(path))
        decoder = Decoder(stream)
        messages, errors = decoder.read(
            apply_scale_and_offset=True,
            convert_datetimes_to_dates=False,
            convert_types_to_strings=True,
            merge_heart_rates=False,
        )
    except Exception as e:
        print(f"  [!] {path.name}: {e}")
        return []

    # Data sesiunii din session_mesgs sau activity_mesgs
    session_dt = None
    for s in messages.get("session_mesgs", []):
        ts = fit_ts(s.get("start_time") or s.get("timestamp"))
        if ts:
            session_dt = ts
            break
    if not session_dt:
        for a in messages.get("activity_mesgs", []):
            ts = fit_ts(a.get("local_timestamp") or a.get("timestamp"))
            if ts:
                session_dt = ts
                break
    if not session_dt:
        # fallback: foloseste data fisierului
        session_dt = datetime.fromtimestamp(path.stat().st_mtime)

    # Workout step index → exercise name (din workout_step_mesgs)
    step_map = {}
    for ws in messages.get("workout_step_mesgs", []):
        idx  = ws.get("message_index")
        name = ws.get("wkt_step_name") or ""
        cat  = ws.get("exercise_category")
        sub  = ws.get("exercise_name")
        if idx is not None:
            step_map[idx] = {"name": name, "cat": cat, "sub": sub}

    sets = []
    for sm in messages.get("set_mesgs", []):
        set_type = str(sm.get("set_type", "")).lower()
        if "rest" in set_type:
            continue

        reps   = sm.get("repetitions") or 0
        weight = sm.get("weight")       # kg, deja in metric cu apply_scale_and_offset
        dur    = sm.get("duration")     # secunde
        ts     = fit_ts(sm.get("start_time") or sm.get("timestamp"))

        # Categorie exercitiu
        cat_raw = sm.get("category")
        sub_raw = sm.get("category_subtype")

        # category poate fi lista sau valoare singulara
        if isinstance(cat_raw, list):
            cat_raw = cat_raw[0] if cat_raw else None
        if isinstance(sub_raw, list):
            sub_raw = sub_raw[0] if sub_raw else None

        # Daca categoria nu e in set, incearca din workout_step
        if cat_raw is None:
            step_idx = sm.get("wkt_step_index")
            if step_idx is not None and step_idx in step_map:
                info = step_map[step_idx]
                cat_raw = info.get("cat")
                sub_raw = info.get("sub")

        ex_name = exercise_name(cat_raw, sub_raw)

        sets.append({
            "session_date": session_dt.date().isoformat(),
            "session_dt":   session_dt,
            "timestamp":    ts.isoformat() if ts else session_dt.isoformat(),
            "exercise":     ex_name,
            "category":     str(cat_raw) if cat_raw else "",
            "sub_category": str(sub_raw) if sub_raw else "",
            "reps":         int(reps),
            "weight_kg":    round(float(weight), 2) if weight is not None else 0.0,
            "duration_s":   round(float(dur), 1) if dur is not None else 0.0,
            "source_file":  path.name,
        })

    return sets

def load_all_sets() -> tuple[list[dict], list[str]]:
    """Incarca toate seturile din data/fit/*.fit."""
    if not FIT.exists():
        return [], []

    fit_files = sorted(FIT.glob("*.fit"))
    all_sets  = []
    sessions  = []

    for f in fit_files:
        sets = parse_sets_from_fit(f)
        if sets:
            session_date = sets[0]["session_date"]
            n_sets = len(sets)
            total_vol = sum(s["reps"] * s["weight_kg"] for s in sets)
            sessions.append({
                "file": f.name,
                "date": session_date,
                "n_sets": n_sets,
                "volume_kg": round(total_vol, 1),
            })
            all_sets.extend(sets)
            print(f"  + {f.name} → {session_date}: {n_sets} seturi, volum {total_vol:.0f} kg")
        else:
            sessions.append({"file": f.name, "date": "—", "n_sets": 0, "volume_kg": 0})
            print(f"  - {f.name} → fara seturi de forta (posibil cardio/cycling)")

    return all_sets, sessions

# ─── Analysis ─────────────────────────────────────────────────────────────────

def analyze_evolution(all_sets: list[dict]) -> dict:
    """Grupeaza seturile pe exercitiu si calculeaza evolutia."""
    by_exercise = defaultdict(list)
    for s in all_sets:
        if s["reps"] > 0:
            by_exercise[s["exercise"]].append(s)

    evolution = {}
    for ex, sets in by_exercise.items():
        sets_sorted = sorted(sets, key=lambda x: x["timestamp"])

        # Grupeaza pe sesiune (data)
        by_date = defaultdict(list)
        for s in sets_sorted:
            by_date[s["session_date"]].append(s)

        dates = sorted(by_date.keys())

        # Metrici per sesiune
        sessions_data = []
        global_max_w  = 0
        for d in dates:
            day_sets  = by_date[d]
            max_w     = max(s["weight_kg"] for s in day_sets)
            total_vol = sum(s["reps"] * s["weight_kg"] for s in day_sets)
            total_reps = sum(s["reps"] for s in day_sets)
            n_sets    = len(day_sets)
            best_set  = max(day_sets, key=lambda x: x["reps"] * x["weight_kg"])

            is_pr = max_w > global_max_w
            if is_pr:
                global_max_w = max_w

            sessions_data.append({
                "date":       d,
                "max_weight": max_w,
                "volume":     round(total_vol, 1),
                "reps":       total_reps,
                "n_sets":     n_sets,
                "best_set":   best_set,
                "is_pr":      is_pr,
            })

        # Trend: compara prima si ultima sesiune
        first_w = sessions_data[0]["max_weight"]  if sessions_data else 0
        last_w  = sessions_data[-1]["max_weight"] if sessions_data else 0
        first_v = sessions_data[0]["volume"]      if sessions_data else 0
        last_v  = sessions_data[-1]["volume"]     if sessions_data else 0

        evolution[ex] = {
            "sessions": sessions_data,
            "total_sessions": len(sessions_data),
            "max_weight_ever": global_max_w,
            "delta_weight": round(last_w - first_w, 2),
            "delta_volume": round(last_v - first_v, 1),
            "first_w": first_w,
            "last_w":  last_w,
        }

    return evolution

# ─── HTML ─────────────────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       background: #f0f4f8; color: #1a202c; }

.header { background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
  color: white; padding: 40px 48px; }
.header h1 { font-size: 28px; font-weight: 700; }
.header p  { margin-top: 6px; color: #a0aec0; font-size: 14px; }
.badge { display: inline-block; margin-top: 12px; font-size: 11px; font-weight: 600;
  background: rgba(255,255,255,0.15); padding: 4px 12px; border-radius: 12px; color: #e2e8f0; }

.container { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }

.section-title { font-size: 18px; font-weight: 700; color: #2d3748;
  margin: 36px 0 16px; border-left: 4px solid #4299e1; padding-left: 12px; }
.section-title.green  { border-left-color: #48bb78; }
.section-title.orange { border-left-color: #ed8936; }
.section-title.red    { border-left-color: #fc8181; }

/* KPI */
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; }
.kpi-card { background: white; border-radius: 12px; padding: 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
.kpi-label { font-size: 11px; text-transform: uppercase; letter-spacing: .6px; color: #718096; }
.kpi-value { font-size: 28px; font-weight: 700; color: #2d3748; margin: 6px 0 2px; }
.kpi-sub   { font-size: 12px; color: #718096; }
.pos { color: #48bb78; } .neg { color: #fc8181; } .neu { color: #a0aec0; }

/* Exercise card */
.ex-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 20px; }
.ex-card { background: white; border-radius: 12px; padding: 0;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08); overflow: hidden; }
.ex-header { padding: 16px 20px 12px; border-bottom: 1px solid #f7fafc; }
.ex-name  { font-size: 16px; font-weight: 700; color: #2d3748; }
.ex-meta  { font-size: 12px; color: #718096; margin-top: 3px; }
.ex-stats { display: flex; gap: 16px; padding: 12px 20px; background: #f7fafc; }
.ex-stat  { text-align: center; }
.ex-stat-val   { font-size: 20px; font-weight: 700; color: #2d3748; }
.ex-stat-label { font-size: 10px; text-transform: uppercase; letter-spacing: .5px; color: #718096; }
.ex-chart { padding: 12px 20px 16px; }
.ex-chart-title { font-size: 10px; text-transform: uppercase; letter-spacing: .5px;
  color: #a0aec0; margin-bottom: 8px; }

/* Session bars in exercise card */
.sess-row { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; }
.sess-date { font-size: 11px; color: #718096; width: 60px; flex-shrink: 0; }
.sess-bar-wrap { flex: 1; position: relative; }
.sess-bar-bg   { background: #edf2f7; border-radius: 3px; height: 20px; position: relative; overflow: hidden; }
.sess-bar-fill { height: 100%; border-radius: 3px; transition: width .3s; }
.sess-bar-label { position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
  font-size: 11px; font-weight: 600; color: #2d3748; }
.sess-badge { font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 8px;
  white-space: nowrap; flex-shrink: 0; }
.pr-badge  { background: #fefcbf; color: #744210; }
.vol-badge { background: #ebf8ff; color: #2b6cb0; font-weight: 400; }

/* Table */
.table-wrap { background: white; border-radius: 12px; overflow-x: auto;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #edf2f7; padding: 11px 16px; text-align: left; font-size: 11px;
  text-transform: uppercase; letter-spacing: .5px; color: #718096; }
td { padding: 10px 16px; border-top: 1px solid #f7fafc; }
tr:hover td { background: #f7fafc; }
.row-pr { background: #fffff0 !important; }

/* Trend arrow */
.trend-up   { color: #48bb78; font-weight: 700; }
.trend-down { color: #fc8181; font-weight: 700; }
.trend-flat { color: #a0aec0; }

.alert { background: #ebf8ff; border-left: 4px solid #4299e1; border-radius: 8px;
  padding: 14px 18px; margin-bottom: 8px; }
.alert h3 { font-size: 14px; font-weight: 700; color: #2b6cb0; margin-bottom: 4px; }
.alert p  { font-size: 13px; color: #718096; line-height: 1.6; }

footer { text-align: center; padding: 32px; color: #a0aec0; font-size: 12px; }
"""

MONTHS = ["","Ian","Feb","Mar","Apr","Mai","Iun","Iul","Aug","Sep","Oct","Nov","Dec"]

def ro_date(d: str) -> str:
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
        return f"{dt.day} {MONTHS[dt.month]}"
    except Exception:
        return d

def bar_color(delta):
    if delta > 0: return "#48bb78"
    if delta < 0: return "#fc8181"
    return "#4299e1"

def exercise_card(ex_name: str, data: dict, max_weight_global: float) -> str:
    sessions = data["sessions"]
    dw = data["delta_weight"]
    dw_str = (f'<span class="trend-up">▲ +{dw:.1f} kg</span>' if dw > 0
              else f'<span class="trend-down">▼ {dw:.1f} kg</span>' if dw < 0
              else '<span class="trend-flat">= stabil</span>')

    # Barele de greutate max per sesiune
    max_w = data["max_weight_ever"] or 1
    bars  = ""
    for s in sessions[-8:]:   # ultimele 8 sesiuni
        w    = s["max_weight"]
        pct  = int(w / max_w * 100) if max_w else 0
        color = "#fbd38d" if s["is_pr"] else "#4299e1"
        pr_tag = '<span class="sess-badge pr-badge">PR</span>' if s["is_pr"] else ""
        vol_tag = f'<span class="sess-badge vol-badge">{s["n_sets"]}×{s["reps"]//s["n_sets"] if s["n_sets"] else 0} rep · {s["volume"]:.0f} kg vol</span>'
        bars += f"""
        <div class="sess-row">
          <div class="sess-date">{ro_date(s['date'])}</div>
          <div class="sess-bar-wrap">
            <div class="sess-bar-bg">
              <div class="sess-bar-fill" style="width:{pct}%;background:{color};"></div>
              <span class="sess-bar-label">{"0" if w==0 else f"{w:.1f}" if w<100 else f"{w:.0f}"} kg</span>
            </div>
          </div>
          {pr_tag}{vol_tag}
        </div>"""

    n_pr = sum(1 for s in sessions if s["is_pr"])
    card = f"""
  <div class="ex-card">
    <div class="ex-header">
      <div class="ex-name">{ex_name}</div>
      <div class="ex-meta">{data['total_sessions']} sesiuni · {n_pr} PR-uri · {dw_str}</div>
    </div>
    <div class="ex-stats">
      <div class="ex-stat">
        <div class="ex-stat-val">{data['last_w']:.1f} kg</div>
        <div class="ex-stat-label">Greutate actuala</div>
      </div>
      <div class="ex-stat">
        <div class="ex-stat-val">{data['max_weight_ever']:.1f} kg</div>
        <div class="ex-stat-label">Max ever</div>
      </div>
      <div class="ex-stat">
        <div class="ex-stat-val">{data['delta_volume']:+.0f} kg</div>
        <div class="ex-stat-label">Δ Volum</div>
      </div>
    </div>
    <div class="ex-chart">
      <div class="ex-chart-title">Greutate max per sesiune</div>
      {bars}
    </div>
  </div>"""
    return card

def build_summary_table(evolution: dict) -> str:
    html = """
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Exercitiu</th><th>Sesiuni</th><th>Prima sesiune</th>
          <th>Prima greutate</th><th>Ultima greutate</th><th>Δ Greutate</th>
          <th>Max ever</th><th>PR-uri</th><th>Trend</th>
        </tr>
      </thead>
      <tbody>"""

    for ex, d in sorted(evolution.items(), key=lambda x: -x[1]["max_weight_ever"]):
        dw = d["delta_weight"]
        n_pr = sum(1 for s in d["sessions"] if s["is_pr"])
        first_date = d["sessions"][0]["date"] if d["sessions"] else "—"
        trend = ("▲" if dw > 0 else "▼" if dw < 0 else "=")
        trend_cls = "trend-up" if dw > 0 else "trend-down" if dw < 0 else "trend-flat"
        html += f"""
        <tr>
          <td><strong>{ex}</strong></td>
          <td>{d['total_sessions']}</td>
          <td>{ro_date(first_date)}</td>
          <td>{d['first_w']:.1f} kg</td>
          <td>{d['last_w']:.1f} kg</td>
          <td class="{trend_cls}">{'+' if dw>0 else ''}{dw:.1f} kg</td>
          <td><strong>{d['max_weight_ever']:.1f} kg</strong></td>
          <td>{n_pr}</td>
          <td class="{trend_cls} ">{trend}</td>
        </tr>"""

    html += """
      </tbody>
    </table>
  </div>"""
    return html

def generate():
    print("Citesc fisiere .fit din data/fit/...")
    all_sets, sessions = load_all_sets()

    if not all_sets:
        print("  [!] Nicio sesiune cu seturi de forta gasita.")
        print("      Asigura-te ca fisierele .fit sunt in data/fit/ si contin antrenamente de sala.")
        # Scriem totusi un HTML cu instructiuni
        OUT.write_text(f"""<!DOCTYPE html><html><head><meta charset='UTF-8'>
<title>Evolutie Exercitii</title></head><body style='font-family:sans-serif;padding:40px;'>
<h1>Nicio data gasita</h1>
<p>Adauga fisiere .fit in <code>raport-sanatate/data/fit/</code> si ruleaza din nou.</p>
<p>Fisierele trebuie sa fie antrenamente de sala cu seturi si repetari inregistrate.</p>
</body></html>""", encoding="utf-8")
        return

    evolution = analyze_evolution(all_sets)

    today = datetime.now().strftime("%d %B %Y")
    dates = sorted({s["session_date"] for s in all_sets})
    total_vol = sum(s["reps"] * s["weight_kg"] for s in all_sets)
    total_sets = len(all_sets)
    n_exercises = len(evolution)

    # Cel mai mare PR
    all_sessions_flat = [s for d in evolution.values() for s in d["sessions"]]
    prs = [s for s in all_sessions_flat if s["is_pr"]]

    # Exercitii cu cel mai mare progres procentual
    improved = sorted(
        [(ex, d) for ex, d in evolution.items() if d["total_sessions"] >= 2],
        key=lambda x: x[1]["delta_weight"], reverse=True
    )

    max_w_global = max((d["max_weight_ever"] for d in evolution.values()), default=1)

    html = f"""<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Evolutie Exercitii</title>
<style>{CSS}</style>
</head>
<body>

<div class="header">
  <h1>Raport Evolutie Exercitii</h1>
  <p>Persa Radu · {len(dates)} sesiuni analizate · {dates[0] if dates else '—'} → {dates[-1] if dates else '—'}</p>
  <span class="badge">Generat {today} · {n_exercises} exercitii · {total_sets} seturi totale</span>
</div>

<div class="container">

  <div class="section-title" style="margin-top:24px;">Sumar global</div>
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">Sesiuni analizate</div>
      <div class="kpi-value">{len(dates)}</div>
      <div class="kpi-sub">{dates[0] if dates else '—'} → {dates[-1] if dates else '—'}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Exercitii unice</div>
      <div class="kpi-value">{n_exercises}</div>
      <div class="kpi-sub">din fisierele .fit</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Total seturi</div>
      <div class="kpi-value">{total_sets}</div>
      <div class="kpi-sub">exclusiv pauze</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Volum total</div>
      <div class="kpi-value">{total_vol/1000:.1f}t</div>
      <div class="kpi-sub">{total_vol:.0f} kg ridicate</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">PR-uri setate</div>
      <div class="kpi-value">{len(prs)}</div>
      <div class="kpi-sub">record personal per exercitiu</div>
    </div>
  </div>"""

    if improved:
        best_ex, best_d = improved[0]
        html += f"""
  <div style="margin-top:20px;" class="alert">
    <h3>Cel mai mare progres: {best_ex}</h3>
    <p>De la <strong>{best_d['first_w']:.1f} kg</strong> la <strong>{best_d['last_w']:.1f} kg</strong>
    (+{best_d['delta_weight']:.1f} kg) in {best_d['total_sessions']} sesiuni.</p>
  </div>"""

    # Exercitii in regres
    regressed = [(ex, d) for ex, d in improved if d["delta_weight"] < 0]
    if regressed:
        html += '<div style="margin-top:8px;">'
        for ex, d in regressed[:3]:
            html += f"""
  <div class="alert" style="background:#fff5f5;border-left-color:#fc8181;">
    <h3 style="color:#c53030;">Regres: {ex}</h3>
    <p>De la {d['first_w']:.1f} kg la {d['last_w']:.1f} kg ({d['delta_weight']:.1f} kg).
    Verifica tehnica sau creste recuperarea.</p>
  </div>"""
        html += "</div>"

    html += '\n  <div class="section-title green">Evolutie per exercitiu</div>'
    html += '\n  <div class="ex-grid">'
    for ex, d in sorted(evolution.items(), key=lambda x: -x[1]["max_weight_ever"]):
        html += exercise_card(ex, d, max_w_global)
    html += "\n  </div>"

    html += '\n  <div class="section-title orange">Tabel sumar comparativ</div>'
    html += build_summary_table(evolution)

    html += "\n</div>"
    html += f"""
<footer>
  Evolutie generata {today} · {len(sessions)} fisiere .fit procesate · {total_sets} seturi active
</footer>
</body>
</html>"""

    OUT.write_text(html, encoding="utf-8")
    print(f"✓ Generat: {OUT}")
    print(f"  {n_exercises} exercitii · {total_sets} seturi · volum total {total_vol:.0f} kg")

if __name__ == "__main__":
    generate()
