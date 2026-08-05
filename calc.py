"""
Moteur de calcul — Projet d'équipement en matériel d'irrigation localisée
Reconstitution fidèle des formules du classeur Excel (POSTES, variation.R,
variation PR, TABLEAUX, PRINCIPALE, A.secondaires).

Toutes les fonctions ici sont pures (pas d'effets de bord, pas de Streamlit)
afin de pouvoir être testées indépendamment de l'interface.
"""
import math


# ---------------------------------------------------------------------------
# Valeurs par défaut / fabriques d'état
# ---------------------------------------------------------------------------

def blank_culture(i):
    return {
        "name": "Culture 1" if i == 0 else f"Culture {i+1}",
        "EL": 0.0, "EA": 0.0, "kc": 0.0, "kr": 0.0, "eto": 0.0, "ea": 1.0,
        "debitG": 0.0, "eDist": 0.0, "nbRampes": 0.0,
        "modele_goutteur": "", "observation": "",
    }


def blank_forage():
    return {"debit": 0.0, "prof": 0.0, "ns": 0.0, "nd": 0.0,
            "calage": 0.0, "duree": 0.0, "colonne": ""}


def ensure_profile_fields(state):
    """Backward-compat: add any new profile/culture keys missing from an older saved project."""
    defaults = {"nom": "", "cin": "", "tel": "", "localite": "", "parcelle": "",
                "raison_sociale": "PROPRIETAIRE", "ref_fonciere": "", "adresse": "",
                "superficie_totale": 0.0, "texture_sol": "", "permeabilite": ""}
    profile = state.setdefault("profile", {})
    for k, v in defaults.items():
        profile.setdefault(k, v)
    for c in state.get("cultures", []):
        c.setdefault("modele_goutteur", "")
        c.setdefault("observation", "")
    return state


def ensure_forages(state):
    """Backward-compat: migrate an old single 'forage' dict to the 'forages' list."""
    if "forages" not in state:
        if "forage" in state:
            state["forages"] = [state["forage"]]
        else:
            state["forages"] = [blank_forage()]
    if not state["forages"]:
        state["forages"] = [blank_forage()]
    return state


def default_state():
    return {
        "cultures": [blank_culture(i) for i in range(4)],
        "postes": [],                 # [{"unites": [{"culture":1,"sup":m2}, ...]}, ...]
        "principale": [],             # [{"name":..., "q":..., "mode":"normal"|"up"}]
        "asecondaires": {},           # {"1": {"ls":70,"dz":0,"mode":"normal"}, ...}
        "forages": [{"debit": 14.0, "prof": 84.0, "ns": 30.0, "nd": 65.0,
                     "calage": 75.0, "duree": 20.0, "colonne": 'TUBE UPVC DN 2"'}],
        "diam_ref": [118.8, 104.2, 84.0, 70.0, 59.0, 46.4],
        "varr": {"unite": 11, "lr": 55.0, "phi": 17.0, "hentree": 10.0, "dz": 0.5, "doubleface": False},
        "varpr": {"unite": 11, "lpr": 114.0, "hentree": 17.2, "dz": 9.0, "doubleface": False,
                  "alloc": [0, 0, 0, 0, 0, 0]},
        "tableaux": {"pn": 10.0, "tol": 20.0},
        "profile": {"nom": "", "cin": "", "tel": "", "localite": "", "parcelle": "",
                    "raison_sociale": "PROPRIETAIRE", "ref_fonciere": "", "adresse": "",
                    "superficie_totale": 0.0, "texture_sol": "", "permeabilite": ""},
    }


# ---------------------------------------------------------------------------
# Cultures / POSTES
# ---------------------------------------------------------------------------

def culture_derived(c):
    Bn = c["kc"] * c["kr"] * c["eto"]
    Bb = Bn / c["ea"] if c["ea"] else 0.0
    Elignes = c["EL"]
    denom = c["eDist"] * Elignes
    Pf = (c["debitG"] * c["nbRampes"]) / denom if denom else 0.0
    duree = Bb / Pf if Pf else 0.0
    return {"Bn": Bn, "Bb": Bb, "Elignes": Elignes, "Pf": Pf, "duree": duree}


def get_unit_data(state, code):
    """Equivalent of the Excel VLOOKUP(code, POSTES!R:AD, ...) used by variation.R / PR."""
    code = int(code or 0)
    poste_num = code // 10
    unite_num = code % 10
    if poste_num < 1 or unite_num < 1:
        return None
    postes = state["postes"]
    if poste_num - 1 >= len(postes):
        return None
    poste = postes[poste_num - 1]
    unites = poste["unites"]
    if unite_num - 1 >= len(unites):
        return None
    u = unites[unite_num - 1]
    cultures = state["cultures"]
    if u["culture"] - 1 >= len(cultures):
        return None
    c = cultures[u["culture"] - 1]
    d = culture_derived(c)
    denom = c["eDist"] * d["Elignes"]
    nb = (u["sup"] / denom) * c["nbRampes"] if denom else 0.0
    debit_m3h = nb * c["debitG"] / 1000.0
    return {
        "posteNum": poste_num, "uniteNum": unite_num, "culture": c, "sup_m2": u["sup"],
        "debitG": c["debitG"], "eDist": c["eDist"], "eLignes": d["Elignes"],
        "debit_m3h": debit_m3h,
    }


def get_poste_total(state, pi):
    """Sum of area / discharge for every unit inside poste index pi (0-based)."""
    debit = 0.0
    sup = 0.0
    postes = state["postes"]
    if pi >= len(postes):
        return {"sup": 0.0, "debit": 0.0}
    for u in postes[pi]["unites"]:
        ci = u["culture"] - 1
        if ci < 0 or ci >= len(state["cultures"]):
            continue
        c = state["cultures"][ci]
        d = culture_derived(c)
        denom = c["eDist"] * d["Elignes"]
        nb = (u["sup"] / denom) * c["nbRampes"] if denom else 0.0
        debit += nb * c["debitG"] / 1000.0
        sup += u.get("sup", 0.0)
    return {"sup": sup, "debit": debit}


def compute_postes(state):
    """Full POSTES-tab computation: per-culture superficie/Bb, per-poste totals,
    overall grand total, bilan des besoins en eau, and forage volume disponible."""
    cultures = state["cultures"]
    postes = state["postes"]

    sup_par_culture = [0.0] * len(cultures)
    for p in postes:
        for u in p["unites"]:
            ci = u["culture"] - 1
            if 0 <= ci < len(cultures):
                sup_par_culture[ci] += u.get("sup", 0.0)

    poste_rows = []
    grand = {"sup": 0.0, "nb": 0.0, "debit": 0.0}
    for pi, p in enumerate(postes):
        sub = {"sup": 0.0, "nb": 0.0, "debit": 0.0, "cultures": set(), "duree": 0.0}
        for u in p["unites"]:
            ci = u["culture"] - 1
            if not (0 <= ci < len(cultures)):
                continue
            c = cultures[ci]
            d = culture_derived(c)
            denom = c["eDist"] * d["Elignes"]
            nb = (u["sup"] / denom) * c["nbRampes"] if denom else 0.0
            debit = nb * c["debitG"] / 1000.0
            sub["sup"] += u.get("sup", 0.0)
            sub["nb"] += nb
            sub["debit"] += debit
            sub["cultures"].add(u["culture"])
            sub["duree"] = max(sub["duree"], d["duree"])
        grand["sup"] += sub["sup"]
        grand["nb"] += sub["nb"]
        grand["debit"] += sub["debit"]
        poste_rows.append({"poste": pi + 1, **sub})

    besoin_rows = []
    total_volume = 0.0
    for i, c in enumerate(cultures):
        sup_ha = sup_par_culture[i] / 10000.0
        if sup_ha <= 0 and not (c["EL"] > 0):
            continue
        d = culture_derived(c)
        bb_m3_ha_j = d["Bb"] * 10.0
        volume = bb_m3_ha_j * sup_ha
        total_volume += volume
        besoin_rows.append({
            "culture": c["name"] or f"Culture {i+1}", "bb": bb_m3_ha_j,
            "sup_ha": sup_ha, "volume": volume,
        })

    forages = state.get("forages") or ([state["forage"]] if "forage" in state else [])
    vol_dispo = sum(f["debit"] * f["duree"] for f in forages)

    return {
        "sup_par_culture": sup_par_culture, "poste_rows": poste_rows, "grand": grand,
        "besoin_rows": besoin_rows, "total_volume": total_volume, "vol_dispo": vol_dispo,
    }


def compute_postes_detail(state):
    """Tableau détaillé unité par unité (feuille POSTES d'origine) : une ligne par unité,
    avec les colonnes cumulées (Durée/SUP/Nb.deG/Débits CUMUL) qui s'accumulent au fil des
    unités d'un même poste, suivie d'une ligne « Total N » en fin de poste."""
    cultures = state["cultures"]
    rows = []
    for pi, poste in enumerate(state["postes"]):
        cum_sup = cum_nb = cum_debit = 0.0
        cum_duree = 0.0
        for ui, u in enumerate(poste["unites"]):
            ci = u["culture"] - 1
            c = cultures[ci] if 0 <= ci < len(cultures) else None
            if not c:
                continue
            d = culture_derived(c)
            denom = c["eDist"] * d["Elignes"]
            nb = (u["sup"] / denom) * c["nbRampes"] if denom else 0.0
            debit = nb * c["debitG"] / 1000.0
            duree = d["duree"]
            cum_sup += u.get("sup", 0.0)
            cum_nb += nb
            cum_debit += debit
            if ui == 0:
                cum_duree = duree
            rows.append({
                "type": "unite", "culture_code": u["culture"], "poste": pi + 1,
                "unite_idx": ui + 1, "unite_code": (pi + 1) * 10 + (ui + 1),
                "culture_nom": f"{c['name']} {c['EL']:g}x{c['EA']:g}" if c["name"] else "",
                "duree": duree if ui == 0 else None,
                "sup": u.get("sup", 0.0), "nb": nb, "debit": debit,
                "duree_cumul": cum_duree, "sup_cumul": cum_sup, "nb_cumul": cum_nb,
                "debit_cumul": cum_debit, "debit_g": c["debitG"], "ecart_g": c["eDist"],
            })
        if poste["unites"]:
            rows.append({
                "type": "total", "poste": pi + 1, "label": f"Total {pi+1}",
                "duree_cumul": cum_duree, "sup_cumul": cum_sup, "nb_cumul": cum_nb,
                "debit_cumul": cum_debit,
            })
    return rows


# ---------------------------------------------------------------------------
# variation.R — rampe
# ---------------------------------------------------------------------------

def _compute_var_r_core(state, code, Lr, phi, Hentree, dz_total, double_face):
    vmax = 1.0  # valeur fixe intégrée à la formule Excel (IF(H>1,...))

    lookup = get_unit_data(state, code)
    Qng = lookup["debitG"] if lookup else 0.0
    Eg = lookup["eDist"] if lookup else 0.0
    QngEff = Qng * 2 if double_face else Qng

    nb_troncons = (Lr / Eg) if Eg else 0.0
    Qr = nb_troncons * QngEff
    slope = (dz_total / Lr) if Lr else 0.0

    def velocity(q):
        return (q / 1000 / 3600) / (math.pow(phi / 2000, 2) * math.pi) if phi else 0.0

    rows = [{"i": 0, "Lcum": 0.0, "Q": Qr, "dH": 0.0, "dz": 0.0, "P": Hentree, "V": velocity(Qr)}]
    Q, P, i = Qr, Hentree, 0
    while i < nb_troncons - 1e-9 and i < 1000:
        i += 1
        Lcum = i * Eg
        if i > 1:
            Q = Q - QngEff
        dH = 1.1 * 0.478 * math.pow(Q, 1.75) * math.pow(phi, -4.75) * Eg if phi else 0.0
        dz = slope * Eg
        P = P - dz - dH
        rows.append({"i": i, "Lcum": Lcum, "Q": Q, "dH": dH, "dz": dz, "P": P, "V": velocity(Q)})

    Ps = [r["P"] for r in rows]
    Pmin = min(Ps) if Ps else Hentree
    Pmax = max(Ps) if Ps else Hentree
    dH_total = sum(r["dH"] for r in rows)
    Vmax = max((r["V"] for r in rows), default=0.0)
    dqq = ((Pmax - Pmin) / Hentree) if Qng and Hentree else 0.0
    # position (m cumulés) où survient la pression min / max — colonnes Lpn / Lpx du TABLEAUX
    Lpn = next((r["Lcum"] for r in rows if r["P"] == Pmin), 0.0)
    Lpx = next((r["Lcum"] for r in rows if r["P"] == Pmax), 0.0)

    return {
        "lookup": lookup, "Qng": Qng, "Eg": Eg, "nbTroncons": nb_troncons, "Qr": Qr,
        "rows": rows, "Pmin": Pmin, "Pmax": Pmax, "dHTotal": dH_total, "Vmax": Vmax,
        "vmax": vmax, "dqq": dqq, "slope": slope, "Lpn": Lpn, "Lpx": Lpx,
        "DP": Pmax - Pmin,
    }


def compute_var_r(state):
    p = state["varr"]
    code = int(p.get("unite") or 0)
    return _compute_var_r_core(
        state, code, p.get("lr") or 0.0, p.get("phi") or 0.0,
        p.get("hentree") or 0.0, p.get("dz") or 0.0, bool(p.get("doubleface")),
    )




# --- Paramètres de rampe par unité (pour le module TABLEAUX complet) -------
# Chaque unité a 2 "scénarios" (aller/retour, ou k/x dans le classeur d'origine) :
# la feuille TABLEAUX du classeur affiche pour chaque unité une ligne par scénario
# (typiquement pente positive puis pente négative pour la même rampe).
def get_varr_for_unit(state, code, scenario=0):
    store = state.setdefault("varr_units", {})
    key = str(int(code))
    if key not in store or not isinstance(store[key], list):
        store[key] = [
            {"lr": 50.0, "phi": 17.0, "hentree": 10.0, "dz": 0.0, "doubleface": False},
            {"lr": 50.0, "phi": 17.0, "hentree": 10.0, "dz": 0.0, "doubleface": False},
        ]
    return store[key][scenario]


def compute_var_r_for_unit(state, code, scenario=0):
    p = get_varr_for_unit(state, code, scenario)
    return _compute_var_r_core(
        state, code, p.get("lr") or 0.0, p.get("phi") or 0.0,
        p.get("hentree") or 0.0, p.get("dz") or 0.0, bool(p.get("doubleface")),
    )


# ---------------------------------------------------------------------------
# variation PR — porte-rampe
# ---------------------------------------------------------------------------

PR_DIAMS = [121.6, 107.0, 87.0, 72.5, 60.8, 48.2]


def _compute_var_pr_core(state, code, Lpr, Hentree, dz_total, double_face, alloc):
    vmax = 1.5  # valeur fixe intégrée à la formule Excel (IF(J>1.5,...))

    lookup = get_unit_data(state, code)
    El = lookup["eLignes"] if lookup else 0.0
    Qpr_total = (lookup["debit_m3h"] * 1000) if lookup else 0.0

    nb_troncons = (Lpr / El) if El else 0.0
    slope = (dz_total / Lpr) if Lpr else 0.0
    Qrampe = (Qpr_total / nb_troncons) if nb_troncons else 0.0
    Qrampe_eff = Qrampe * 2 if double_face else Qrampe

    cum = []
    running = 0.0
    for a in alloc:
        running += a
        cum.append(running)

    def diam_for_lcum(lcum):
        for i in range(5):
            if cum[i] > 0 and cum[i] >= lcum:
                return PR_DIAMS[i]
        return PR_DIAMS[5]

    def velocity(q, D):
        return (q / 1000 / 3600) / (math.pow(D / 2000, 2) * math.pi) if D else 0.0

    rows = [{"i": 0, "Lcum": 0.0, "D": PR_DIAMS[5], "Q": Qpr_total, "dH": 0.0, "dz": 0.0,
             "H": Hentree, "V": 0.0}]
    Q, H, i = Qpr_total, Hentree, 0
    while i < nb_troncons - 1e-9 and i < 1000:
        i += 1
        Lcum = i * El
        D = diam_for_lcum(Lcum)
        if i > 1:
            Q = max(0.0, Q - Qrampe_eff)
        dH = 1.1 * 0.478 * math.pow(Q, 1.75) * math.pow(D, -4.75) * El if D else 0.0
        dz = slope * El
        H = H - dz - dH
        rows.append({"i": i, "Lcum": Lcum, "D": D, "Q": Q, "dH": dH, "dz": dz, "H": H,
                      "V": velocity(Q, D)})

    Hs = [r["H"] for r in rows]
    Pmin = min(Hs) if Hs else Hentree
    Pmax = max(Hs) if Hs else Hentree
    dH_total = sum(r["dH"] for r in rows)
    dz_sum = sum(r["dz"] for r in rows)
    Vmax = max((r["V"] for r in rows), default=0.0)
    Lpn = next((r["Lcum"] for r in rows if r["H"] == Pmin), 0.0)
    Lpx = next((r["Lcum"] for r in rows if r["H"] == Pmax), 0.0)

    return {
        "lookup": lookup, "El": El, "QprTotal": Qpr_total, "nbTroncons": nb_troncons,
        "Qrampe": Qrampe, "rows": rows, "Pmin": Pmin, "Pmax": Pmax, "dHTotal": dH_total,
        "dzSum": dz_sum, "Vmax": Vmax, "vmax": vmax, "slope": slope,
        "Lpn": Lpn, "Lpx": Lpx, "DP": Pmax - Pmin, "alloc": list(alloc),
    }


def compute_var_pr(state):
    p = state["varpr"]
    code = int(p.get("unite") or 0)
    alloc = list(p.get("alloc") or [0, 0, 0, 0, 0, 0])
    return _compute_var_pr_core(
        state, code, p.get("lpr") or 0.0, p.get("hentree") or 0.0,
        p.get("dz") or 0.0, bool(p.get("doubleface")), alloc,
    )


# --- Paramètres de porte-rampe par unité (pour le module TABLEAUX complet) -
def get_varpr_for_unit(state, code, scenario=0):
    store = state.setdefault("varpr_units", {})
    key = str(int(code))
    if key not in store or not isinstance(store[key], list):
        store[key] = [
            {"lpr": 100.0, "hentree": 15.0, "dz": 0.0, "doubleface": False, "alloc": [0, 0, 0, 0, 0, 0]},
            {"lpr": 100.0, "hentree": 15.0, "dz": 0.0, "doubleface": False, "alloc": [0, 0, 0, 0, 0, 0]},
        ]
    return store[key][scenario]


def compute_var_pr_for_unit(state, code, scenario=0):
    p = get_varpr_for_unit(state, code, scenario)
    alloc = list(p.get("alloc") or [0, 0, 0, 0, 0, 0])
    return _compute_var_pr_core(
        state, code, p.get("lpr") or 0.0, p.get("hentree") or 0.0,
        p.get("dz") or 0.0, bool(p.get("doubleface")), alloc,
    )


# --- Synthèse complète (feuille TABLEAUX : RAMPES | PORTES RAMPES) ---------
# Reproduit la double ligne par unité du classeur Excel (2 scénarios : typiquement
# pente positive / pente négative pour vérifier la pression aux deux extrémités).
def compute_tableaux_full(state):
    rows = []
    for pi, poste in enumerate(state["postes"]):
        for ui in range(len(poste["unites"])):
            code = (pi + 1) * 10 + (ui + 1)
            lookup = get_unit_data(state, code)
            if not lookup:
                continue
            for sc in (0, 1):
                r = compute_var_r_for_unit(state, code, sc)
                pr = compute_var_pr_for_unit(state, code, sc)
                rp = get_varr_for_unit(state, code, sc)
                pp = get_varpr_for_unit(state, code, sc)
                rows.append({
                    "code": code, "scenario": sc + 1,
                    # RAMPES
                    "r_lr": rp["lr"], "r_qr": r["Qr"], "r_i": r["slope"] * 100,
                    "r_dr": rp["phi"], "r_lpn": r["Lpn"], "r_lpx": r["Lpx"],
                    "r_dp": r["DP"], "r_ok": r["Vmax"] <= r["vmax"],
                    # PORTES RAMPES
                    "pr_lpr": pp["lpr"], "pr_qpr": pr["QprTotal"] / 1000.0, "pr_i": pr["slope"] * 100,
                    "pr_alloc": pr["alloc"], "pr_lpn": pr["Lpn"], "pr_lpx": pr["Lpx"],
                    "pr_dp": pr["DP"], "pr_ok": pr["Vmax"] <= pr["vmax"], "pr_el": pr["El"],
                })
    return rows


# ---------------------------------------------------------------------------
# PRINCIPALE — diamètre normalisé / vitesse pour un débit donné
# ---------------------------------------------------------------------------

_DIAM_TABLE_NORMAL = [(10, 48.2), (15, 60.8), (20, 72.5), (30, 87.0), (45, 107.0), (60, 121.6)]
_DIAM_TABLE_UP     = [(10, 60.8), (15, 72.5), (20, 87.0), (30, 107.0), (45, 121.6), (60, 121.6)]


def diam_for_flow(q, mode):
    table = _DIAM_TABLE_UP if mode == "up" else _DIAM_TABLE_NORMAL
    for lim, d in table:
        if q < lim:
            return d
    return None


def compute_principale_row(t):
    D = diam_for_flow(t["q"], t.get("mode", "normal"))
    V = (t["q"] / 3600) / (3.14 * math.pow(D / 2000, 2)) if D else 0.0
    ok = bool(D) and 0.3 <= V <= 1.8
    return {"D": D, "V": V, "ok": ok}


# ---------------------------------------------------------------------------
# A.secondaires — antennes secondaires (une ligne par poste)
# ---------------------------------------------------------------------------

def get_asec_row(state, poste_num):
    key = str(poste_num)
    if key not in state["asecondaires"]:
        state["asecondaires"][key] = {"ls": 70.0, "dz": 0.0, "mode": "normal"}
    return state["asecondaires"][key]


def compute_asec_row(state, pi):
    poste_num = pi + 1
    row = get_asec_row(state, poste_num)
    total = get_poste_total(state, pi)
    debit = total["debit"]
    D = diam_for_flow(debit, row.get("mode", "normal"))
    dH = 1.1 * 0.478 * math.pow(debit * 1000, 1.75) * math.pow(D, -4.75) * row["ls"] if D else 0.0
    dP = row["dz"] + dH
    V = (debit / 3600) / (3.14 * math.pow(D / 2000, 2)) if D else 0.0
    ok = bool(D) and 0.3 <= V <= 1.8
    return {"posteNum": poste_num, "debit": debit, "row": row, "D": D, "dH": dH, "dP": dP,
            "V": V, "ok": ok}
