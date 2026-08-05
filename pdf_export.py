"""Génère la fiche PDF « Note de calcul » d'un dossier agriculteur (reportlab),
au même format que le document officiel utilisé par le bureau (N.C. KHARBACH)."""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, PageBreak)

from calc import (culture_derived, compute_postes, compute_var_r, compute_var_pr,
                   compute_principale_row, compute_asec_row, diam_for_flow,
                   compute_tableaux_full, get_unit_data)

OLIVE_DEEP = colors.HexColor("#123D1C")
OLIVE = colors.HexColor("#1E7D32")
INK = colors.HexColor("#14211A")
ROW_ALT = colors.HexColor("#F2F9F3")
GREY = colors.HexColor("#6B6B6B")


def _fmt(n, d=2):
    if n is None:
        return "–"
    try:
        return f"{n:,.{d}f}".replace(",", " ").replace(".", ",")
    except Exception:
        return str(n)


def _blank(v):
    return v if (v not in (None, "", 0, 0.0)) else "…………………"


def _table(data, col_widths=None, header=True):
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8DDD0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), OLIVE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT]),
        ]
    t.setStyle(TableStyle(style))
    return t


def generate_pdf(state, chef_name=None):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=14 * mm, bottomMargin=16 * mm,
                             leftMargin=16 * mm, rightMargin=16 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleKh", parent=styles["Normal"], fontSize=13, fontName="Helvetica-Bold",
                                  alignment=1, textColor=OLIVE_DEEP)
    h1_style = ParagraphStyle("H1Kh", parent=styles["Heading1"], textColor=colors.white,
                               backColor=OLIVE_DEEP, fontSize=12, leftIndent=4, spaceBefore=0,
                               spaceAfter=0, borderPadding=(5, 4, 5, 4))
    h2_style = ParagraphStyle("H2Kh", parent=styles["Normal"], fontSize=10.5, fontName="Helvetica-Bold",
                               textColor=OLIVE_DEEP, spaceBefore=4, spaceAfter=2)
    body = ParagraphStyle("BodyKh", parent=styles["Normal"], fontSize=9, leading=12)
    small_italic = ParagraphStyle("SmallItalic", parent=styles["Normal"], fontSize=8, leading=11,
                                   textColor=GREY, fontName="Helvetica-Oblique")

    story = []
    profile = state.get("profile", {})
    date_str = datetime.now().strftime("%d/%m/%Y")

    # ---- En-tête ----
    story.append(_table(
        [[Paragraph("<b>NOTE DE CALCUL</b>", title_style),
          Paragraph("<b>PROJET D'ÉQUIPEMENT EN MATÉRIEL<br/>D'IRRIGATION LOCALISÉE</b>", title_style)]],
        col_widths=[60 * mm, 118 * mm], header=False))
    story.append(Spacer(1, 4))
    story.append(_table([["Date :", date_str]], col_widths=[30 * mm, 148 * mm], header=False))
    story.append(Spacer(1, 10))

    # ============================================================
    # 1. Identification de l'exploitation
    # ============================================================
    story.append(Paragraph("1. Identification de l'exploitation", h1_style))
    story.append(Spacer(1, 6))
    story.append(_table([
        ["Représentant (Nom et prénom)", _blank(profile.get("nom"))],
        ["Raison sociale", _blank(profile.get("raison_sociale"))],
        ["Référence foncière", _blank(profile.get("ref_fonciere"))],
        ["Téléphone", _blank(profile.get("tel"))],
        ["CIN", _blank(profile.get("cin"))],
        ["Adresse complète de l'exploitation", _blank(profile.get("adresse") or profile.get("localite"))],
    ], col_widths=[70 * mm, 108 * mm], header=False))
    story.append(Spacer(1, 10))

    # ============================================================
    # 2. Données de base
    # ============================================================
    story.append(Paragraph("2. Données de base", h1_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Superficie totale de l'exploitation :</b> "
                            f"{_fmt(profile.get('superficie_totale') or 0, 2)} ha", body))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Cultures à irriguer :", h2_style))
    pt = compute_postes(state)
    cult_rows = [["Culture", "Superficie (ha)", "E.L", "E.A", "Observations"]]
    total_ha = 0.0
    for i, c in enumerate(state["cultures"]):
        if not (c["name"] and c["EL"] > 0):
            continue
        sup_ha = pt["sup_par_culture"][i] / 10000.0
        total_ha += sup_ha
        cult_rows.append([c["name"], _fmt(sup_ha, 3), _fmt(c["EL"], 1), _fmt(c["EA"], 1),
                           c.get("observation") or "—"])
    if len(cult_rows) == 1:
        cult_rows.append(["—", "—", "—", "—", "—"])
    cult_rows.append(["Sup totale nette", _fmt(total_ha, 3), "", "", ""])
    story.append(_table(cult_rows, col_widths=[45 * mm, 30 * mm, 20 * mm, 20 * mm, 63 * mm]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Sol :", h2_style))
    story.append(Paragraph(f"Texture : {_blank(profile.get('texture_sol'))} &nbsp;&nbsp;&middot;&nbsp;&nbsp; "
                            f"Perméabilité : {_blank(profile.get('permeabilite'))}", body))
    story.append(Paragraph("Topographie : (voir plan côté ci-joint)", body))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Ressources en eau :", h2_style))
    forages = state.get("forages") or ([state["forage"]] if "forage" in state else [])
    forage_rows = [["Forage", "Débit (m3/h)", "Profondeur (m)", "Niv. statique (m)", "Niv. dynamique (m)",
                    "Calage pompe (m)", "Durée pompage (h/j)", "Volume dispo (m3/j)"]]
    total_vol = 0.0
    for i, forage in enumerate(forages, start=1):
        vol_i = forage["debit"] * forage["duree"]
        total_vol += vol_i
        forage_rows.append([
            f"Forage {i}", _fmt(forage["debit"], 1), _fmt(forage["prof"], 1), _fmt(forage["ns"], 1),
            _fmt(forage["nd"], 1), _fmt(forage["calage"], 1), _fmt(forage["duree"], 1), _fmt(vol_i, 1),
        ])
    if len(forages) > 1:
        forage_rows.append(["TOTAL", "", "", "", "", "", "", _fmt(total_vol, 1)])
    story.append(_table(forage_rows))
    story.append(PageBreak())

    # ============================================================
    # 3. Besoins en eau
    # ============================================================
    story.append(Paragraph("3. Besoins en eau", h1_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Besoin brut (Bb) en eau d'irrigation : Bb = Kc &times; ETo &times; Kr / Ea "
        "&nbsp;&nbsp;(jour de pointe)", body))
    story.append(Spacer(1, 6))

    rows = [["Culture", "Kc", "Kr", "ETO (mm/j)", "Ea", "Bn (mm/j)", "Bb (mm/j)"]]
    for c in state["cultures"]:
        if not (c["name"] and c["EL"] > 0):
            continue
        d = culture_derived(c)
        rows.append([c["name"], _fmt(c["kc"], 2), _fmt(c["kr"], 2), _fmt(c["eto"], 1),
                     _fmt(c["ea"], 2), _fmt(d["Bn"], 3), _fmt(d["Bb"], 3)])
    if len(rows) == 1:
        rows.append(["—"] * 7)
    story.append(_table(rows))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Bilan hydrique &mdash; besoin total au jour de pointe :", h2_style))
    rows = [["Cultures", "Bb (m3/ha/j)", "Superficie (ha)", "Volume (m3/j)"]]
    for b in pt["besoin_rows"]:
        rows.append([b["culture"], _fmt(b["bb"], 3), _fmt(b["sup_ha"], 3), _fmt(b["volume"], 3)])
    if len(rows) == 1:
        rows.append(["—"] * 4)
    rows.append(["BESOIN TOTAL / JOUR DE POINTE", "", "", _fmt(pt["total_volume"], 3) + " m3"])
    story.append(_table(rows))
    story.append(Spacer(1, 8))

    if total_vol:
        ratio = pt["total_volume"] / total_vol * 100
        if ratio <= 100:
            concl = ("Le bilan ressources-besoins est <b>positif</b> pendant le mois de pointe : "
                     "la ressource en eau existante suffit pour irriguer la superficie à équiper.")
        else:
            concl = ("Le bilan ressources-besoins est <b>négatif</b> pendant le mois de pointe : "
                     "la ressource en eau existante ne suffit pas pour irriguer la totalité de la "
                     "superficie à équiper &mdash; une réduction de la superficie ou un forage "
                     "complémentaire sont à envisager.")
    else:
        concl = "Volume disponible non renseigné &mdash; bilan ressources-besoins non calculable."
    story.append(Paragraph("<b>Conclusion :</b> " + concl, body))
    story.append(PageBreak())

    # ============================================================
    # 4. Calculs hydrauliques
    # ============================================================
    story.append(Paragraph("4. Calculs hydrauliques", h1_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("a. Distributeurs et écartements", h2_style))
    rows = [["Culture", "Goutteur", "Débit (l/h)", "Écartement (m)", "Nombre de rampes"]]
    for c in state["cultures"]:
        if not (c["name"] and c["EL"] > 0):
            continue
        rows.append([c["name"], c.get("modele_goutteur") or "—", _fmt(c["debitG"], 2),
                     _fmt(c["eDist"], 2), _fmt(c["nbRampes"], 0)])
    if len(rows) == 1:
        rows.append(["—"] * 5)
    story.append(_table(rows))
    story.append(Spacer(1, 10))

    story.append(Paragraph("b. Pluviométrie fictive (Pf) et durée d'irrigation par poste (T)", h2_style))
    story.append(Paragraph("Pf = qg / (El &times; Eg) &times; Nbre &nbsp;&nbsp;et&nbsp;&nbsp; T = Bb / Pf", body))
    rows = [["Culture", "Pf (mm/h)", "T (h/j)"]]
    for c in state["cultures"]:
        if not (c["name"] and c["EL"] > 0):
            continue
        d = culture_derived(c)
        rows.append([c["name"], _fmt(d["Pf"], 3), _fmt(d["duree"], 3)])
    if len(rows) == 1:
        rows.append(["—", "—", "—"])
    story.append(_table(rows))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Postes d'irrigation :", h2_style))
    rows = [["Poste", "Unité", "Culture", "Durée irr. (h/j)", "Superficie (m²)", "Débit (m3/h)"]]
    for pi, poste in enumerate(state["postes"]):
        for ui, u in enumerate(poste["unites"]):
            code = (pi + 1) * 10 + (ui + 1)
            lu = get_unit_data(state, code)
            if not lu:
                continue
            duree_txt = _fmt(culture_derived(lu["culture"])["duree"], 2) if ui == 0 else ""
            rows.append([str(pi + 1), str(code), lu["culture"]["name"], duree_txt,
                         _fmt(lu["sup_m2"], 0), _fmt(lu["debit_m3h"], 3)])
        pr_total = pt["poste_rows"][pi] if pi < len(pt["poste_rows"]) else None
        if pr_total:
            rows.append([f"Total {pi+1}", "", "", _fmt(pr_total["duree"], 2), _fmt(pr_total["sup"], 0),
                         _fmt(pr_total["debit"], 3)])
    if len(rows) == 1:
        rows.append(["—"] * 6)
    rows.append(["TOTAL", "", "", "", _fmt(pt["grand"]["sup"], 0), _fmt(pt["grand"]["debit"], 3)])
    story.append(_table(rows))
    story.append(PageBreak())

    story.append(Paragraph("c. Rampes, porte-rampes, antennes secondaires et conduite principale", h2_style))
    story.append(Paragraph(
        "Le calcul des diamètres se fait en respectant la règle de Christiansen sur la variation "
        "admissible de pression, qui limite la plage de variation du débit à 10 %, correspondant à une "
        "variation de pression de : &Delta;P = Pm &times; &Delta;q/q &nbsp;&mdash; avec Pm la pression "
        "nominale du distributeur et &Delta;q/q la variation admissible du débit (10 %).", body))
    story.append(Paragraph(
        "Yi = 0,478 &times; Qi<super rise=3 size=6>1,75</super> &times; "
        "Di<super rise=3 size=6>-4,75</super> &times; Li &times; 1,10 &nbsp;(perte de charge du "
        "tronçon i&nbsp;; Q en l/h, D en mm, L en m). Vitesse maximale admissible&nbsp;: 1,5 m/s au "
        "niveau des porte-rampes, antennes secondaires et conduites principales, 1 m/s au niveau des "
        "rampes.", small_italic))
    story.append(Spacer(1, 8))

    tx = compute_tableaux_full(state)
    story.append(Paragraph("Rampes :", h2_style))
    rows = [["Unité", "Lr (m)", "Qr (l/h)", "I (%)", "Dr (mm)", "Lpn (m)", "Lpx (m)", "ΔP (mCE)"]]
    for r in tx:
        rows.append([str(r["code"]), _fmt(r["r_lr"], 0), _fmt(r["r_qr"], 0), _fmt(r["r_i"], 1) + "%",
                     _fmt(r["r_dr"], 0), _fmt(r["r_lpn"], 0), _fmt(r["r_lpx"], 0), _fmt(r["r_dp"], 1)])
    if len(rows) == 1:
        rows.append(["—"] * 8)
    story.append(_table(rows))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Porte-rampes :", h2_style))
    rows = [["Unité", "Lpr (m)", "Qpr (m3/h)", "I (%)", "Lpn (m)", "Lpx (m)", "ΔP (mCE)", "El (m)"]]
    for r in tx:
        rows.append([str(r["code"]), _fmt(r["pr_lpr"], 0), _fmt(r["pr_qpr"], 1), _fmt(r["pr_i"], 1) + "%",
                     _fmt(r["pr_lpn"], 0), _fmt(r["pr_lpx"], 0), _fmt(r["pr_dp"], 1), _fmt(r["pr_el"], 2)])
    if len(rows) == 1:
        rows.append(["—"] * 8)
    story.append(_table(rows))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Antennes secondaires :", h2_style))
    rows = [["Poste", "Ls (m)", "Q (m3/h)", "Ds (mm)", "Δz (m)", "Y (mCE)", "ΔP (mCE)", "V (m/s)"]]
    for pi in range(len(state["postes"])):
        a = compute_asec_row(state, pi)
        rows.append([str(a["posteNum"]), _fmt(a["row"]["ls"], 1), _fmt(a["debit"], 2),
                     _fmt(a["D"], 1) if a["D"] else "–", _fmt(a["row"]["dz"], 1),
                     _fmt(a["dH"], 1) if a["D"] else "–", _fmt(a["dP"], 1) if a["D"] else "–",
                     _fmt(a["V"], 2) if a["D"] else "–"])
    if len(rows) == 1:
        rows.append(["—"] * 8)
    story.append(_table(rows))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Conduite(s) principale(s) :", h2_style))
    rows = [["Tronçon", "Q (m3/h)", "Φ (mm)", "V (m/s)"]]
    for t in state["principale"]:
        res = compute_principale_row(t)
        rows.append([t["name"], _fmt(t["q"], 2), _fmt(res["D"], 1) if res["D"] else "–",
                     _fmt(res["V"], 2) if res["D"] else "–"])
    if len(rows) == 1:
        rows.append(["—"] * 4)
    story.append(_table(rows))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "<i>Note : le dimensionnement du groupe motopompe et du bassin de stockage ne sont pas encore "
        "couverts par cette version de l'application ; ils devront être complétés séparément si le "
        "projet en comporte.</i>", small_italic))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
