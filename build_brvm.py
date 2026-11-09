#!/usr/bin/env python3
"""
Pipeline de données du Screener BRVM.

Usage : python3 -I build_brvm.py <dossier_depot_brvm-data-public> <page.html> [archive.csv]

- Lit l'historique quotidien (CSV par titre + indices), les fondamentaux, les dividendes
  et les suspensions du dépôt public BRVMetrics (github.com/harzat/brvm-data-public).
- Ajuste les cours des divisions / regroupements d'actions détectés automatiquement.
- Calcule les indicateurs techniques, de liquidité et fondamentaux de chaque titre.
- Injecte le résultat dans la page, entre <script id="brvm-data" type="application/json"> et </script>.
- Écrit (optionnel) l'archive des clôtures ajustées depuis 2016 au format CSV.
Affiche un rapport de contrôle ; sort avec un code 1 si la page n'a pas été mise à jour.
"""
import csv, json, math, os, re, sys, statistics
from datetime import datetime, timezone

REPO, PAGE = sys.argv[1], sys.argv[2]
ARCHIVE = sys.argv[3] if len(sys.argv) > 3 else None
TICKERS = ["ABJC","BICB","BICC","BNBC","BOAB","BOABF","BOAC","BOAM","BOAN","BOAS","CABC","CBIBF","CFAC","CIEC",
           "ECOC","ETIT","FTSC","LNBB","NEIC","NSBC","NTLC","ONTBF","ORAC","ORGT","PALC","PRSC","SAFC","SCRC",
           "SDCC","SDSC","SEMC","SGBC","SHEC","SIBC","SICC","SIVC","SLBC","SMBC","SNTS","SOGC","SPHC","STAC",
           "STBC","TTLC","TTLS","UNLC","UNXC","BBGC"]
NUM = re.compile(r"[\s  %]")

def num(s):
    s = NUM.sub("", (s or "")).replace(",", ".")
    try: return float(s) if s not in ("", "-", "—") else None
    except ValueError: return None

def read_series(path):
    """Retourne [(date_iso, close, volume_titres, valeur_fcfa, variation_pct)] trié par date."""
    rows = {}
    with open(path, encoding="utf-8-sig") as f:
        r = csv.reader(f, delimiter=";")
        next(r, None)
        for c in r:
            if len(c) < 8: continue
            try: d = datetime.strptime(c[0].strip(), "%d/%m/%Y").date().isoformat()
            except ValueError: continue
            close = num(c[1])
            if not close or close <= 0: continue
            rows[d] = (d, close, num(c[5]) or 0, num(c[6]) or 0, num(c[7]))
    return [rows[k] for k in sorted(rows)]

def detect_actions(s):
    """Divisions / regroupements : saut de cours non expliqué par la variation publiée et durable."""
    ev = []
    for i in range(1, len(s)):
        prev, (d, close, _, _, var) = s[i-1][1], s[i]
        if var is None: continue
        implied_prev = close / (1 + var / 100)
        f = prev / implied_prev
        if 0.6 < f < 1.6: continue
        nxt = [x[1] for x in s[i:i+5]]
        if len(nxt) < 2 or not (0.6 < (prev / statistics.median(nxt)) / f < 1.6): continue
        fr = round(f)
        if fr >= 2 and abs(f - fr) / fr < 0.05: f = float(fr)
        ev.append((d, round(f, 4)))
    return ev

def adjust(s, events):
    out = []
    for d, close, vol, val, var in s:
        fac = 1.0
        for ed, f in events:
            if d < ed: fac *= f
        out.append((d, close / fac, vol, val, var))
    return out

def sma(a, n): return sum(a[-n:]) / n if len(a) >= n else None
def rsi(a, n=14):
    if len(a) < n + 1: return None
    g = l = 0.0
    for i in range(1, n + 1):
        ch = a[i] - a[i-1]; g += max(ch, 0); l += max(-ch, 0)
    g /= n; l /= n
    for i in range(n + 1, len(a)):
        ch = a[i] - a[i-1]
        g = (g * (n - 1) + max(ch, 0)) / n; l = (l * (n - 1) + max(-ch, 0)) / n
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)
def perf(a, n): return (a[-1] / a[-1-n] - 1) * 100 if len(a) > n and a[-1-n] > 0 else None
def r2(x, k=2): return None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else round(x, k)

# ---- Calendrier : BRVM Composite
idx_s = read_series(os.path.join(REPO, "indices", "Indice_BRVMC.csv"))
cal = [x[0] for x in idx_s]
last_date = cal[-1]
idx_close = {x[0]: x[1] for x in idx_s}

def index_snapshot(code):
    s = read_series(os.path.join(REPO, "indices", f"Indice_{code}.csv"))
    return {"v": r2(s[-1][1]), "chg": r2((s[-1][1] / s[-2][1] - 1) * 100), "d": s[-1][0]} if len(s) > 1 else None

actions = {a["ticker"]: a for a in json.load(open(os.path.join(REPO, "actions.json"), encoding="utf-8"))["actions"]}
fund = json.load(open(os.path.join(REPO, "fundamentals.json"), encoding="utf-8"))
divs = json.load(open(os.path.join(REPO, "dividendes.json"), encoding="utf-8"))["all"]
try: susp = {k: v for k, v in json.load(open(os.path.join(REPO, "trading_status.json"), encoding="utf-8")).items() if k != "_meta"}
except Exception: susp = {}

ytd_start = max([d for d in cal if d < last_date[:4] + "-01-01"] or [cal[0]])
cal1y = cal[-253:]
idx_ret = {cal1y[i]: idx_close[cal1y[i]] / idx_close[cal1y[i-1]] - 1 for i in range(1, len(cal1y))}

out, report, archive_cols = {}, [], {}
for t in TICKERS:
    a = actions.get(t)
    if not a: report.append(f"{t}: absent du registre"); continue
    p = os.path.join(REPO, a["csv"] + ".csv")
    if not os.path.exists(p): report.append(f"{t}: fichier d'historique manquant"); continue
    raw = read_series(p)
    if not raw: report.append(f"{t}: historique vide"); continue
    ev = detect_actions(raw)
    for d, f in ev: report.append(f"{t}: opération sur titre détectée le {d}, facteur {f}")
    s = adjust(raw, ev)
    by = {x[0]: x for x in s}
    # alignement sur le calendrier du marché (report du dernier cours), à partir de la 1re cotation
    first = s[0][0]; closes, vols, vals, last = [], [], [], None
    for d in cal:
        if d < first: continue
        if d in by: last = by[d][1]; vols.append(by[d][2]); vals.append(by[d][3])
        else: vols.append(0); vals.append(0)
        closes.append(last)
    archive_cols[t] = {d: c for d, c in zip([d for d in cal if d >= first], closes)}
    lastrow = raw[-1]
    px = lastrow[1]
    stale = lastrow[0] != last_date
    chg = 0.0 if stale else (lastrow[4] if lastrow[4] is not None else perf(closes, 1))
    c1y = closes[-253:]
    hi52, lo52 = max(c1y), min(c1y)
    rets = [closes[i] / closes[i-1] - 1 for i in range(max(1, len(closes) - 63), len(closes))]
    vol3m = statistics.pstdev(rets) * math.sqrt(252) * 100 if len(rets) > 20 else None
    # bêta 1 an contre le BRVM Composite
    cal_t = [d for d in cal if d >= first][-253:]
    pr = {cal_t[i]: c1y[i] / c1y[i-1] - 1 for i in range(1, len(c1y)) if i < len(cal_t)}
    common = [d for d in pr if d in idx_ret]
    beta = None
    if len(common) > 120:
        xs = [idx_ret[d] for d in common]; ys = [pr[d] for d in common]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        vx = sum((x - mx) ** 2 for x in xs)
        beta = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / vx if vx else None
    peak, mdd = c1y[0], 0.0
    for c in c1y: peak = max(peak, c); mdd = min(mdd, c / peak - 1)
    v63 = vols[-63:]
    ytd_c = archive_cols[t].get(ytd_start)
    # ---- fondamentaux
    fu = fund.get(t, {}) or {}
    se = fu.get("series", {}) or {}
    def lastv(k):
        d = se.get(k) or {}
        ks = sorted(d, key=int)
        return (d[ks[-1]], int(ks[-1])) if ks else (None, None)
    def prevv(k, y):
        d = se.get(k) or {}
        return d.get(str(y - 1)) if y else None
    bnpa = fu.get("bnpa")
    rn, yr = lastv("resultat_net"); ca, yca = lastv("ca"); cp, _ = lastv("capitaux_propres")
    shares = fu.get("nb_titres")
    # cohérence nb de titres / BNPA / résultat (rattrape une division non répercutée)
    if rn and bnpa and bnpa > 0:
        implied = rn * 1e6 / bnpa
        if not shares: shares = implied
        elif ev:  # uniquement si une division / un regroupement a été détecté sur le cours
            k = implied / shares
            if k > 1.6 or k < 0.6:
                shares = shares * round(k) if round(k) >= 2 else implied
                report.append(f"{t}: nombre de titres corrigé ({int(fu.get('nb_titres') or 0):,} → {int(shares):,})")
    split_after = lambda d: math.prod(f for ed, f in ev if d and d < ed) if ev else 1.0
    dv = sorted([x for x in divs if x.get("ticker") == t and x.get("dividende")],
                key=lambda x: (x.get("exercice") or 0, x.get("date_detachement") or ""))
    div_net = div_date = div_ex = None
    if dv:
        z = dv[-1]
        div_net = z["dividende"] / split_after(z.get("date_detachement"))
        div_date, div_ex = z.get("date_detachement"), z.get("exercice")
    cap = px * shares / 1e9 if shares else None
    rn_prev = prevv("resultat_net", yr); ca_prev = prevv("ca", yca)
    rn3 = (se.get("resultat_net") or {}).get(str(yr - 3)) if yr else None
    roe, _ = lastv("roe"); mn, _ = lastv("marge_nette"); coex, _ = lastv("coefficient_d_exploitation")
    per = px / bnpa if bnpa and bnpa > 0 else None
    out[t] = {
        "px": px, "d": lastrow[0], "stale": stale, "chg": r2(chg), "vol": int(lastrow[2]) if not stale else 0,
        "val": round(lastrow[3] / 1000) if not stale else 0,
        "cap": r2(cap, 1), "shares": int(shares) if shares else None, "float": fu.get("flottant"),
        "per": r2(per), "bnpa": r2(bnpa, 1), "div": r2(div_net), "divDate": div_date, "divEx": div_ex,
        "rdt": r2(div_net / px * 100) if div_net and px else None,
        "pbr": r2(cap * 1000 / cp) if cap and cp and cp > 0 else None,
        "roe": r2(roe), "mn": r2(mn), "coex": r2(coex), "fy": yr,
        "gRN": r2((rn / rn_prev - 1) * 100) if rn and rn_prev and rn_prev > 0 else None,
        "gCA": r2((ca / ca_prev - 1) * 100) if ca and ca_prev and ca_prev > 0 else None,
        "cagrRN3": r2(((rn / rn3) ** (1 / 3) - 1) * 100) if rn and rn3 and rn3 > 0 and rn > 0 else None,
        "p1w": r2(perf(closes, 5)), "p1m": r2(perf(closes, 21)), "p3m": r2(perf(closes, 63)),
        "p6m": r2(perf(closes, 126)), "p1y": r2(perf(closes, 252)),
        "ytd": r2((closes[-1] / ytd_c - 1) * 100) if ytd_c else None,
        "sma20": r2(sma(closes, 20)), "sma50": r2(sma(closes, 50)), "sma200": r2(sma(closes, 200)),
        "rsi": r2(rsi(closes[-300:]), 1), "hi52": r2(hi52), "lo52": r2(lo52),
        "dHi": r2((closes[-1] / hi52 - 1) * 100), "dLo": r2((closes[-1] / lo52 - 1) * 100),
        "volat": r2(vol3m, 1), "beta": r2(beta), "mdd": r2(mdd * 100, 1),
        "adv20": round(sum(vals[-20:]) / 20 / 1e6, 2), "tradeDays": r2(sum(1 for v in v63 if v > 0) / max(1, len(v63)) * 100, 0),
        "susp": t in susp, "spark": [float(f"{c:.4g}") for c in closes[-253:]],
        "events": [{"d": d, "f": f} for d, f in ev],
    }
    if stale and t not in susp: report.append(f"{t}: pas de cotation le {last_date} (dernier cours {lastrow[0]})")

missing = [t for t in TICKERS if t not in out]
payload = {"asOf": last_date, "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
           "source": "BRVMetrics (github.com/harzat/brvm-data-public) : BRVM, SikaFinance, RicheBourse",
           "idx": {k: index_snapshot(k) for k in ("BRVMC", "BRVM30", "BRVMPR")},
           "cal": cal[-253:], "rows": out}
html = open(PAGE, encoding="utf-8").read()
pat = re.compile(r'(<script id="brvm-data" type="application/json">)(.*?)(</script>)', re.S)
ok = len(missing) <= 5 and pat.search(html)
if ok:
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = pat.sub(lambda m: m.group(1) + blob + m.group(3), html, count=1)
    open(PAGE, "w", encoding="utf-8").write(html)
if ARCHIVE:
    days = [d for d in cal if d >= "2016-01-01"]
    with open(ARCHIVE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(["date"] + TICKERS)
        for d in days: w.writerow([d] + [("" if archive_cols.get(t, {}).get(d) is None else f"{archive_cols[t][d]:.6g}") for t in TICKERS])
print(json.dumps({"seance": last_date, "titres": len(out), "manquants": missing, "page_mise_a_jour": bool(ok),
                  "taille_donnees_ko": round(len(json.dumps(payload)) / 1024), "controles": report}, ensure_ascii=False, indent=1))
sys.exit(0 if ok else 1)
