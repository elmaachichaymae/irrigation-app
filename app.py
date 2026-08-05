"""
PROJET D'ÉQUIPEMENT EN MATÉRIEL D'IRRIGATION LOCALISÉE — application (Streamlit)

Lancer avec :  streamlit run app.py
"""
import copy
from datetime import datetime

import streamlit as st
import plotly.graph_objects as go

import storage
from calc import (
    default_state, blank_culture, blank_forage, ensure_forages, ensure_profile_fields,
    culture_derived, get_unit_data, get_poste_total,
    compute_postes, compute_postes_detail, compute_var_r, compute_var_pr, diam_for_flow,
    compute_principale_row, compute_asec_row, get_asec_row,
    get_varr_for_unit, get_varpr_for_unit, compute_var_r_for_unit, compute_var_pr_for_unit,
    compute_tableaux_full,
)
from pdf_export import generate_pdf

st.set_page_config(page_title="Irrigation Localisée", page_icon="💧", layout="wide")

PR_DIAM_LABELS = ["121,6", "107", "87", "72,5", "60,8", "48,2"]
PR_DIAM_RANGES = ["45–60", "30–45", "20–30", "15–20", "10–15", "0–10"]

# ---------------------------------------------------------------------------
# CSS — palette verte et blanche, sobre et professionnelle
# ---------------------------------------------------------------------------
st.markdown("""
<style>
:root{
  --green:#1e7d32; --green-deep:#123d1c; --green-soft:#e8f3ea; --green-line:#cfe3d1;
  --clay:#b3261e; --clay-soft:#fbeceb;
}
.stApp { background-color: #ffffff; }
h1, h2, h3 { color: var(--green-deep) !important; }
[data-testid="stSidebar"] { background-color: #f4faf5; border-right: 1px solid var(--green-line); }
.kh-badge{ background:var(--green-deep); color:white; padding:2px 10px; border-radius:12px;
  font-size:12px; font-family:monospace; }
.kh-flag-ok{ background:var(--green-soft); color:var(--green-deep); padding:2px 10px; border-radius:12px; font-size:12px;}
.kh-flag-warn{ background:var(--clay-soft); color:var(--clay); padding:2px 10px; border-radius:12px; font-size:12px;}
.kh-computed{ background:var(--green-soft); border:1px solid var(--green-line); border-radius:6px; padding:10px 14px; }
.kh-lookup{ background:#f4faf5; border:1px dashed var(--green); border-radius:6px; padding:10px 14px; }
.stButton>button[kind="primary"]{
  background-color: var(--green) !important;
  border-color: var(--green) !important;
  color: #ffffff !important;
}
.stButton>button[kind="primary"]:hover{
  background-color: var(--green-deep) !important;
  border-color: var(--green-deep) !important;
  color: #ffffff !important;
}
.stButton>button[kind="primary"] p{ color: #ffffff !important; }
.stFormSubmitButton>button[kind="primary"]{
  background-color: var(--green) !important;
  border-color: var(--green) !important;
  color: #ffffff !important;
}
.stFormSubmitButton>button[kind="primary"]:hover{
  background-color: var(--green-deep) !important;
  border-color: var(--green-deep) !important;
}
.stFormSubmitButton>button[kind="primary"] p{ color: #ffffff !important; }
.stTabs [aria-selected="true"]{ color: var(--green-deep) !important; border-bottom-color: var(--green) !important; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state bootstrap
# ---------------------------------------------------------------------------
def init_session():
    ss = st.session_state
    ss.setdefault("chef", None)          # nom du chef de service connecté
    ss.setdefault("agriculteur", None)        # dict {"cin":..., "nom":..., ...} du dossier ouvert
    ss.setdefault("proj", None)          # état complet du projet (voir calc.default_state)
    ss.setdefault("auth_mode", "login")
    ss.setdefault("show_new_agriculteur_form", False)


init_session()


def save_current_project():
    if st.session_state.agriculteur and st.session_state.proj:
        storage.save_agriculteur_project(st.session_state.agriculteur["cin"], st.session_state.proj)
        profile = st.session_state.proj.get("profile", {})
        rec = {
            "cin": st.session_state.agriculteur["cin"],
            "nom": profile.get("nom") or st.session_state.agriculteur.get("nom", ""),
            "tel": profile.get("tel") or "",
            "localite": profile.get("localite") or "",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        storage.upsert_agriculteur(rec)
        st.session_state.agriculteur = rec


# ---------------------------------------------------------------------------
# ÉCRAN 1 — connexion du chef de service
# ---------------------------------------------------------------------------
import base64
import os

def _bg_image_css():
    """Loads image1.jpg next to app.py as a full-bleed background (base64-embedded).
    Falls back to a soft green gradient if the file isn't present yet."""
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("image1.jpg", "image1.jpeg", "image1.png"):
        path = os.path.join(here, name)
        if os.path.exists(path):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            ext = "png" if name.endswith("png") else "jpeg"
            return (f"linear-gradient(rgba(255,255,255,0.10), rgba(255,255,255,0.35)), "
                    f"url('data:image/{ext};base64,{b64}')")
    # fallback: soft green-field-like gradient, used until image1.jpg is added
    return ("linear-gradient(180deg, #eaf3e3 0%, #d9ecd4 35%, #bfe0b8 70%, #9ecf95 100%)")


def render_login():
    st.markdown(f"""
    <style>
    .stApp {{
        background-image: {_bg_image_css()};
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    .login-title{{
        font-size: 2.4rem; font-weight: 800; line-height:1.15;
        color:#152420; margin-bottom:0.2rem;
    }}
    .login-title .accent{{ color:#1e7d32; }}
    .login-sub{{ color:#3a3a3a; font-size:0.95rem; margin-bottom:1.2rem; }}
    .st-key-login_card{{
        background: rgba(255,255,255,0.62);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255,255,255,0.7);
        border-radius: 14px;
        padding: 1.6rem 1.8rem 1.2rem;
    }}
    .stButton>button{{ border-radius: 8px; font-weight:600; }}
    .stButton>button[kind="secondary"]{{
        background:#ffffff !important; color:#1e7d32 !important; border:1.5px solid #1e7d32 !important;
    }}
    div[data-testid="stTextInput"] input{{ border-radius: 8px; }}
    .login-banner{{
        display:flex; align-items:center; gap:10px;
        background: rgba(255,255,255,0.55); border:1px solid rgba(255,255,255,0.7);
        border-radius: 10px; padding: 0.8rem 1rem; margin-top: 1rem;
        font-size: 0.92rem; color:#152420;
    }}
    .login-banner .dot{{
        flex:none; width:22px; height:22px; border-radius:50%;
        background:#1e7d32; color:white; display:flex; align-items:center; justify-content:center;
        font-size:12px;
    }}
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        "<div class='login-title'>Irrigation Localisée &nbsp; "
        "<span class='accent'>Gestion des dossiers techniques des agriculteurs</span></div>",
        unsafe_allow_html=True)
    st.markdown(
        "<div class='login-sub'>Espace chef de service — connecte-toi pour gérer les "
        "dossiers des agriculteurs.</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("  Se connecter", use_container_width=True,
                      type="primary" if st.session_state.auth_mode == "login" else "secondary"):
            st.session_state.auth_mode = "login"
    with col2:
        if st.button("  Créer un compte", use_container_width=True,
                      type="primary" if st.session_state.auth_mode == "signup" else "secondary"):
            st.session_state.auth_mode = "signup"

    with st.container(key="login_card"):
        with st.form("auth_form"):
            username = st.text_input("  Nom d'utilisateur")
            password = st.text_input("  Mot de passe", type="password")
            submitted = st.form_submit_button(
                ("  Se connecter" if st.session_state.auth_mode == "login" else "  Créer le compte"),
                use_container_width=True, type="primary")

    if submitted:
        if not username or not password:
            st.error("Merci de renseigner un nom et un mot de passe.")
        elif st.session_state.auth_mode == "signup":
            ok, err = storage.create_chef(username, password)
            if ok:
                st.session_state.chef = username.strip()
                st.rerun()
            else:
                st.error(err)
        else:
            ok, result = storage.verify_chef(username, password)
            if ok:
                st.session_state.chef = result
                st.rerun()
            else:
                st.error(result)

    st.markdown(
        "<div class='login-banner'><span class='dot'>i</span>"
        "Compte du chef de service du bureau d'études. Une fois connecté, tu retrouves la "
        "liste de tous les dossiers agriculteurs et peux en créer de nouveaux.</div>",
        unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Agrégation du portefeuille de dossiers (pour le tableau de bord)
# ---------------------------------------------------------------------------
# Coordonnées approximatives des localités courantes de la région de l'Oriental
# (utilisées pour la carte du tableau de bord — approximation par ville/commune,
# pas de géolocalisation précise de chaque parcelle).
LOCALITY_COORDS = {
    "oujda": (34.6814, -1.9086), "berkane": (34.9218, -2.3197), "nador": (35.1740, -2.9287),
    "taourirt": (34.4064, -2.8961), "jerada": (34.3103, -2.1636), "ahfir": (34.9500, -2.1000),
    "saidia": (35.0872, -2.2372), "guercif": (34.2333, -3.3500), "figuig": (32.1133, -1.2264),
    "bni drar": (34.7628, -1.9772), "bnidrar": (34.7628, -1.9772), "driouch": (34.9808, -3.3961),
    "el aioun": (34.5833, -2.5000), "taza": (34.2100, -4.0100), "selouane": (35.1167, -2.8333),
    "aklim": (34.5333, -2.0333), "sidi yahya": (34.6333, -2.0333), "naima": (34.6667, -1.9167),
    "labsara": (34.6167, -2.0500),
}


def locality_to_coords(name):
    if not name:
        return None
    key = name.strip().lower()
    if key in LOCALITY_COORDS:
        return LOCALITY_COORDS[key]
    for k, v in LOCALITY_COORDS.items():
        if k in key or key in k:
            return v
    return None


def compute_portfolio_stats(index):
    culture_totals = {}
    locality_counts = {}
    month_counts = {}
    rows = []
    for f in index:
        data = storage.load_agriculteur_project(f["cin"])
        state = data if data else default_state()
        ensure_forages(state)
        ensure_profile_fields(state)
        res = compute_postes(state)
        sup_ha_total = res["grand"]["sup"] / 10000.0
        for i, c in enumerate(state["cultures"]):
            ha = res["sup_par_culture"][i] / 10000.0
            if ha > 0:
                name = c["name"] or f"Culture {i+1}"
                culture_totals[name] = culture_totals.get(name, 0.0) + ha
        loc = f.get("localite") or "Non renseignée"
        locality_counts[loc] = locality_counts.get(loc, 0) + 1
        updated_at = f.get("updated_at", "")
        if updated_at:
            month_key = updated_at[:7]  # "YYYY-MM"
            month_counts[month_key] = month_counts.get(month_key, 0) + 1
        rows.append({
            "cin": f["cin"], "nom": f.get("nom") or "(sans nom)",
            "localite": f.get("localite", ""), "sup_ha": sup_ha_total,
            "nb_postes": len(state["postes"]), "debit": res["grand"]["debit"],
            "updated_at": updated_at,
        })
    totals = {
        "nb_agriculteurs": len(index),
        "sup_ha": sum(r["sup_ha"] for r in rows),
        "debit": sum(r["debit"] for r in rows),
        "nb_postes": sum(r["nb_postes"] for r in rows),
    }
    return {"culture_totals": culture_totals, "locality_counts": locality_counts,
            "month_counts": month_counts, "rows": rows, "totals": totals}


def render_sidebar():
    with st.sidebar:
        st.markdown(
            "<div style='display:flex;align-items:center;gap:8px;margin-bottom:1.2rem;'>"
            "<span style='font-size:1.6rem;'></span>"
            "<div><div style='font-weight:800;color:#123d1c;line-height:1.1;'>IRRIGATION</div>"
            "<div style='font-size:0.72rem;color:#1e7d32;letter-spacing:.05em;'>LOCALISÉE</div></div>"
            "</div>", unsafe_allow_html=True)
        st.markdown("######  Tableau de bord")
        if st.button("  Nouveau dossier", width='stretch'):
            st.session_state.show_new_agriculteur_form = True
        st.markdown("---")
        st.caption(f"Connecté : **{st.session_state.chef}**")
        if st.button("  Déconnexion", width='stretch'):
            st.session_state.chef = None
            st.session_state.agriculteur = None
            st.session_state.proj = None
            st.rerun()


# ---------------------------------------------------------------------------
# ÉCRAN 2 — tableau de bord (répertoire des agriculteurs)
# ---------------------------------------------------------------------------
def render_dashboard():
    render_sidebar()

    st.markdown("""
    <style>
    .dash-card{
        background:#ffffff; border:1px solid #e3ede4; border-radius:14px;
        padding:1.2rem 1.4rem; box-shadow:0 1px 3px rgba(18,61,28,0.06);
    }
    .dash-card h4{ margin:0 0 0.8rem; color:#123d1c; font-size:1rem; }
    .stat-card{
        background:#ffffff; border:1px solid #e3ede4; border-radius:14px;
        padding:1rem 1.2rem; box-shadow:0 1px 3px rgba(18,61,28,0.06);
    }
    .stat-card .icon{ font-size:1.4rem; }
    .stat-card .label{ font-size:0.78rem; color:#6b6b6b; margin-top:0.3rem; }
    .stat-card .value{ font-size:1.6rem; font-weight:800; color:#123d1c; line-height:1.2; }
    .avatar-dot{
        width:34px;height:34px;border-radius:50%;background:#e8f3ea;color:#1e7d32;
        display:flex;align-items:center;justify-content:center;font-weight:700;flex:none;
    }
    .mini-bar-bg{ background:#eef3ec; border-radius:6px; height:8px; width:100%; }
    .mini-bar-fill{ background:#1e7d32; border-radius:6px; height:8px; }
    </style>
    """, unsafe_allow_html=True)

    topL, topR = st.columns([3, 1.4])
    with topL:
        st.text_input("  Rechercher un dossier (nom ou CIN)…", key="dash_search",
                      label_visibility="collapsed", placeholder="  Rechercher un dossier (nom ou CIN)…")
    with topR:
        st.markdown(
            f"<div style='display:flex;align-items:center;justify-content:flex-end;gap:10px;height:38px;'>"
            f"<div class='avatar-dot'>{(st.session_state.chef or '?')[0].upper()}</div>"
            f"<b style='color:#123d1c;'>{st.session_state.chef}</b></div>",
            unsafe_allow_html=True)

    if st.session_state.show_new_agriculteur_form:
        with st.form("new_agriculteur_form"):
            st.markdown("**Nouveau dossier agriculteur**")
            fc1, fc2 = st.columns(2)
            nom = fc1.text_input("Nom complet")
            cin = fc2.text_input("CIN")
            tel = fc1.text_input("Téléphone")
            localite = fc2.text_input("Localité / Douar")
            b1, b2 = st.columns(2)
            create = b1.form_submit_button("Créer le dossier", type="primary", width='stretch')
            cancel = b2.form_submit_button("Annuler", width='stretch')
        if cancel:
            st.session_state.show_new_agriculteur_form = False
            st.rerun()
        if create:
            if not nom or not cin:
                st.error("Nom et CIN sont obligatoires.")
            else:
                cin_u = cin.strip().upper()
                index = storage.load_agriculteur_index()
                if any(f["cin"] == cin_u for f in index):
                    st.error("Un dossier existe déjà avec ce CIN.")
                else:
                    rec = {"cin": cin_u, "nom": nom.strip(), "tel": tel.strip(),
                            "localite": localite.strip(), "updated_at": datetime.now().isoformat(timespec="seconds")}
                    storage.upsert_agriculteur(rec)
                    open_agriculteur(rec)
                    st.session_state.show_new_agriculteur_form = False
                    st.rerun()

    index = storage.load_agriculteur_index()
    search = st.session_state.get("dash_search", "")
    filtered = index
    if search:
        s = search.lower()
        filtered = [f for f in index if s in f.get("nom", "").lower() or s in f.get("cin", "").lower()]

    if not index:
        st.info("Aucun dossier pour l'instant — clique sur « + Nouveau dossier » dans le menu de gauche.")
        return

    stats = compute_portfolio_stats(index)
    row_by_cin = {r["cin"]: r for r in stats["rows"]}
    tot = stats["totals"]

    # ---- 4 cartes statistiques ----
    st.write("")
    s1, s2, s3, s4 = st.columns(4)
    stat_defs = [
        (s1, "👤", "Agriculteurs", f"{tot['nb_agriculteurs']}"),
        (s2, "🌾", "Superficie totale", f"{tot['sup_ha']:.2f} ha"),
        (s3, "💧", "Débit total", f"{tot['debit']:.1f} m³/h"),
        (s4, "📍", "Postes", f"{tot['nb_postes']}"),
    ]
    for col, icon, label, value in stat_defs:
        col.markdown(f"<div class='stat-card'><span class='icon'>{icon}</span>"
                      f"<div class='value'>{value}</div><div class='label'>{label}</div></div>",
                      unsafe_allow_html=True)

    st.write("")
    cardL, cardR = st.columns([1, 1.2])

    # ---- Donut : répartition des superficies par culture ----
    with cardL:
        st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
        st.markdown("#### Aperçu du portefeuille")
        st.caption(f"{len(index)} dossier(s) · Répartition de la superficie par culture")
        if stats["culture_totals"]:
            labels = list(stats["culture_totals"].keys())
            values = list(stats["culture_totals"].values())
            palette = ["#1e7d32", "#f4a300", "#7fbf7f", "#123d1c", "#a3d9a5", "#d9c36a"]
            fig = go.Figure(data=[go.Pie(
                labels=labels, values=values, hole=0.62,
                marker=dict(colors=palette[:len(labels)]),
                textinfo="percent", textfont_size=12,
            )])
            fig.update_layout(showlegend=True, height=260,
                               margin=dict(l=0, r=0, t=10, b=0),
                               legend=dict(orientation="v", x=1, y=0.5))
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
        else:
            st.caption("Aucune culture renseignée pour le moment dans les dossiers existants.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ---- Carte des exploitations ----
    with cardR:
        st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
        st.markdown("#### Carte des exploitations")
        map_pts = []
        for r in stats["rows"]:
            coords = locality_to_coords(r["localite"])
            if coords:
                map_pts.append({"lat": coords[0], "lon": coords[1], "nom": r["nom"],
                                 "localite": r["localite"], "sup": r["sup_ha"]})
        if map_pts:
            fig_map = go.Figure(go.Scattermap(
                lat=[p["lat"] for p in map_pts], lon=[p["lon"] for p in map_pts],
                mode="markers", marker=dict(size=13, color="#1e7d32"),
                text=[f"{p['nom']} — {p['localite']} ({p['sup']:.2f} ha)" for p in map_pts],
                hoverinfo="text",
            ))
            fig_map.update_layout(
                map=dict(style="open-street-map",
                         center=dict(lat=map_pts[0]["lat"], lon=map_pts[0]["lon"]), zoom=6.2),
                height=260, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig_map, width='stretch', config={"displayModeBar": False})
        else:
            st.caption("Aucune localité reconnue pour le moment — renseigne la localité de "
                       "chaque dossier (ville/commune de la région).")
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    chartL, chartR = st.columns(2)

    # ---- Barres : dossiers par localité ----
    with chartL:
        st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
        st.markdown("#### Dossiers par localité")
        if stats["locality_counts"]:
            locs = list(stats["locality_counts"].keys())
            counts = list(stats["locality_counts"].values())
            fig2 = go.Figure(data=[go.Bar(x=locs, y=counts, marker_color="#1e7d32")])
            fig2.update_layout(height=230, margin=dict(l=0, r=0, t=10, b=0),
                                yaxis=dict(title="Dossiers", tick0=0, dtick=1))
            st.plotly_chart(fig2, width='stretch', config={"displayModeBar": False})
        else:
            st.caption("Pas encore de localité renseignée.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ---- Ligne : évolution des dossiers dans le temps ----
    with chartR:
        st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
        st.markdown("#### Évolution des dossiers")
        if stats["month_counts"]:
            months = sorted(stats["month_counts"].keys())
            cumulative, running = [], 0
            for m in months:
                running += stats["month_counts"][m]
                cumulative.append(running)
            fig3 = go.Figure(data=[go.Scatter(x=months, y=cumulative, mode="lines+markers",
                                               line=dict(color="#1e7d32", width=3),
                                               marker=dict(size=7))])
            fig3.update_layout(height=230, margin=dict(l=0, r=0, t=10, b=0),
                                yaxis=dict(title="Dossiers cumulés", tick0=0, dtick=1))
            st.plotly_chart(fig3, width='stretch', config={"displayModeBar": False})
        else:
            st.caption("Pas encore d'historique disponible.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ---- Table moderne des dossiers ----
    st.write("")
    st.markdown("<div class='dash-card'>", unsafe_allow_html=True)
    st.markdown("#### Dossiers agriculteurs")
    shown = sorted(filtered, key=lambda f: row_by_cin.get(f["cin"], {}).get("updated_at", ""), reverse=True)
    if not shown:
        st.caption("Aucun résultat." if search else "Aucun dossier.")
    else:
        table_data = []
        for f in shown:
            r = row_by_cin.get(f["cin"], {})
            table_data.append({
                "Nom": f.get("nom") or "(sans nom)", "CIN": f["cin"],
                "Localité": f.get("localite") or "—",
                "Superficie (ha)": round(r.get("sup_ha", 0), 2),
                "Postes": r.get("nb_postes", 0),
                "Débit (m³/h)": round(r.get("debit", 0), 2),
                "Dernière maj": (r.get("updated_at") or "")[:16].replace("T", " "),
            })
        st.dataframe(table_data, width='stretch', hide_index=True)

        st.markdown("###### Ouvrir ou supprimer un dossier")
        options = {f"{f.get('nom') or '(sans nom)'} — CIN {f['cin']}": f for f in shown}
        choice = st.selectbox("Dossier", list(options.keys()), label_visibility="collapsed")
        selected = options[choice]
        confirm_key = f"confirm_delete_{selected['cin']}"

        if st.session_state.get(confirm_key):
            st.warning(f"Supprimer définitivement le dossier de **{selected.get('nom') or selected['cin']}** ? "
                       "Cette action est irréversible.")
            cc1, cc2 = st.columns(2)
            if cc1.button("Oui, supprimer", key=f"confirmdel_{selected['cin']}", type="primary", width='stretch'):
                storage.delete_agriculteur(selected["cin"])
                st.session_state.pop(confirm_key, None)
                st.rerun()
            if cc2.button("Annuler", key=f"canceldel_{selected['cin']}", width='stretch'):
                st.session_state.pop(confirm_key, None)
                st.rerun()
        else:
            b1, b2 = st.columns(2)
            if b1.button("Ouvrir →", key=f"open_{selected['cin']}", type="primary", width='stretch'):
                open_agriculteur(selected)
                st.rerun()
            if b2.button("🗑 Supprimer", key=f"askdel_{selected['cin']}", width='stretch'):
                st.session_state[confirm_key] = True
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def open_agriculteur(rec):
    st.session_state.agriculteur = rec
    data = storage.load_agriculteur_project(rec["cin"])
    st.session_state.proj = data if data else default_state()
    ensure_forages(st.session_state.proj)
    ensure_profile_fields(st.session_state.proj)
    if not data:
        st.session_state.proj["profile"].update({
            "nom": rec.get("nom", ""), "cin": rec.get("cin", ""),
            "tel": rec.get("tel", ""), "localite": rec.get("localite", ""),
        })


# ---------------------------------------------------------------------------
# ÉCRAN 3 — application principale (projet agriculteur ouvert)
# ---------------------------------------------------------------------------
def render_topbar():
    cols = st.columns([2, 3, 2, 2])
    with cols[0]:
        if st.button("← Liste des agriculteurs"):
            save_current_project()
            st.session_state.agriculteur = None
            st.session_state.proj = None
            st.rerun()
    with cols[1]:
        profile = st.session_state.proj["profile"]
        label = profile.get("nom") or st.session_state.agriculteur["cin"]
        st.markdown(f"Dossier : **{label}** · CIN {st.session_state.agriculteur['cin']}")
    with cols[2]:
        if st.button("Enregistrer", width='stretch'):
            save_current_project()
            st.toast("✓ Projet enregistré")
    with cols[3]:
        pdf_bytes = generate_pdf(st.session_state.proj)
        st.download_button("⬇ Télécharger le PDF", data=pdf_bytes,
                            file_name=f"Fiche_irrigation_{(profile.get('nom') or st.session_state.agriculteur['cin']).replace(' ', '_')}.pdf",
                            mime="application/pdf", width='stretch')
    st.divider()


def tab_profile_and_forage(proj):
    st.markdown("#### 0 · Profil de l'agriculteur")
    st.caption("Ces informations apparaissent dans le PDF exporté (fiche « Note de calcul »).")
    p = proj["profile"]
    c1, c2 = st.columns(2)
    p["nom"] = c1.text_input("Nom complet (Représentant)", p.get("nom", ""))
    p["cin"] = c2.text_input("CIN", p.get("cin", "")).upper()
    c3, c4 = st.columns(2)
    p["tel"] = c3.text_input("Téléphone", p.get("tel", ""))
    p["localite"] = c4.text_input("Localité / Douar", p.get("localite", ""))
    c5, c6 = st.columns(2)
    p["raison_sociale"] = c5.text_input("Raison sociale", p.get("raison_sociale", "PROPRIETAIRE"))
    p["ref_fonciere"] = c6.text_input("Référence foncière (Titre Foncier)", p.get("ref_fonciere", ""))
    p["adresse"] = st.text_input("Adresse complète de l'exploitation (province, commune, douar, lieu-dit)",
                                  p.get("adresse", ""))
    p["parcelle"] = st.text_input("N° de parcelle / exploitation", p.get("parcelle", ""))

    st.markdown("#### 0bis · Données de base de l'exploitation")
    c7, c8, c9 = st.columns(3)
    p["superficie_totale"] = c7.number_input("Superficie totale de l'exploitation (ha)",
                                              value=float(p.get("superficie_totale") or 0.0), step=0.1)
    p["texture_sol"] = c8.text_input("Texture du sol", p.get("texture_sol", ""))
    p["permeabilite"] = c9.text_input("Perméabilité du sol", p.get("permeabilite", ""))

    st.markdown("#### 1 · Ressource en eau — Forage(s)")
    st.caption("Une exploitation peut disposer de plusieurs forages ; leurs débits journaliers s'additionnent.")
    ensure_forages(proj)
    ensure_profile_fields(proj)
    forages = proj["forages"]

    total_vol = 0.0
    for i, f in enumerate(list(forages)):
        with st.container():
            hc1, hc2 = st.columns([6, 1])
            hc1.markdown(f"**Forage {i+1}**")
            if len(forages) > 1:
                if hc2.button("🗑 Supprimer", key=f"del_forage_{i}"):
                    forages.pop(i)
                    st.rerun()
            c1, c2, c3 = st.columns(3)
            f["debit"] = c1.number_input("Débit d'exploitation (m³/h)", value=float(f["debit"]), step=0.1, key=f"fdebit_{i}")
            f["prof"] = c2.number_input("Profondeur totale (m)", value=float(f["prof"]), step=1.0, key=f"fprof_{i}")
            f["ns"] = c3.number_input("Niveau statique (m)", value=float(f["ns"]), step=1.0, key=f"fns_{i}")
            c4, c5, c6 = st.columns(3)
            f["nd"] = c4.number_input("Niveau dynamique (m)", value=float(f["nd"]), step=1.0, key=f"fnd_{i}")
            f["calage"] = c5.number_input("Calage pompe (m)", value=float(f["calage"]), step=1.0, key=f"fcalage_{i}")
            f["duree"] = c6.number_input("Durée max. pompage (h/j)", value=float(f["duree"]), step=1.0, key=f"fduree_{i}")
            f["colonne"] = st.text_input("Colonne montante", f["colonne"], key=f"fcolonne_{i}")
            vol_i = f["debit"] * f["duree"]
            total_vol += vol_i
            st.caption(f"Volume disponible de ce forage : {vol_i:,.1f} m³/j".replace(",", " "))
            st.divider()

    if st.button("➕ Ajouter un forage"):
        forages.append(blank_forage())
        st.rerun()

    st.markdown(
        f"<div class='kh-computed'><b>Volume disponible total / jour : {total_vol:,.1f} m³/j</b></div>".replace(",", " "),
        unsafe_allow_html=True)


def tab_cultures(proj):
    st.markdown("#### 2 · Cultures &amp; paramètres d'irrigation", unsafe_allow_html=True)
    st.caption("Jusqu'à 4 cultures. La superficie est calculée automatiquement depuis les postes.")
    pt = compute_postes(proj)
    names = [c["name"] or f"Culture {i+1}" for i, c in enumerate(proj["cultures"])]
    tabs = st.tabs(names)
    for i, tab in enumerate(tabs):
        with tab:
            c = proj["cultures"][i]
            c1, c2 = st.columns(2)
            c["name"] = c1.text_input("Nom de la culture", c["name"], key=f"cname_{i}")
            sup_ha = pt["sup_par_culture"][i] / 10000.0
            c2.markdown(f"<div class='kh-computed'>Superficie (ha) — auto<br><b>{sup_ha:.3f}</b></div>",
                        unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c["EL"] = c1.number_input("E.L — écart. lignes (m)", value=float(c["EL"]), step=0.1, key=f"el_{i}")
            c["EA"] = c2.number_input("E.A — écart. arbres (m)", value=float(c["EA"]), step=0.1, key=f"ea_{i}")
            c1, c2, c3 = st.columns(3)
            c["kc"] = c1.number_input("Kc", value=float(c["kc"]), step=0.01, key=f"kc_{i}")
            c["kr"] = c2.number_input("Kr", value=float(c["kr"]), step=0.01, key=f"kr_{i}")
            c["eto"] = c3.number_input("ETO (mm/j)", value=float(c["eto"]), step=0.1, key=f"eto_{i}")
            c["ea"] = st.number_input("Ea — efficience", value=float(c["ea"]), step=0.01, key=f"eaeff_{i}")
            c1, c2, c3 = st.columns(3)
            c["debitG"] = c1.number_input("Débit goutteur (l/h)", value=float(c["debitG"]), step=0.01, key=f"dg_{i}")
            c["eDist"] = c2.number_input("E. distributeurs (m)", value=float(c["eDist"]), step=0.01, key=f"ed_{i}")
            c["nbRampes"] = c3.number_input("Nb. de rampes", value=float(c["nbRampes"]), step=1.0, key=f"nr_{i}")
            c1, c2 = st.columns(2)
            c["modele_goutteur"] = c1.text_input("Modèle du goutteur (pour la fiche PDF)",
                                                  c.get("modele_goutteur", ""), key=f"modele_{i}")
            c["observation"] = c2.text_input("Observation (ex. Plantation existante / projetée)",
                                              c.get("observation", ""), key=f"obs_{i}")
            d = culture_derived(c)
            c1, c2 = st.columns(2)
            c1.markdown(f"<div class='kh-computed'>Bb — besoin brut<br><b>{d['Bb']:.3f} mm/j</b></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='kh-computed'>Durée d'irrigation<br><b>{d['duree']:.3f} h/j</b></div>", unsafe_allow_html=True)

    st.markdown("##### Table de sélection — Diamètres (référence)")
    cols = st.columns(6)
    labels = ["45–60", "30–45", "20–30", "15–20", "10–15", "0–10"]
    for i, col in enumerate(cols):
        proj["diam_ref"][i] = col.number_input(f"{labels[i]} m³/h", value=float(proj["diam_ref"][i]),
                                                step=0.1, key=f"diamref_{i}")


def tab_postes(proj):
    st.markdown("#### 3 · Postes d'irrigation")
    st.caption("Indique le nombre de postes, puis pour chaque poste le nombre d'unités.")
    nb_postes = st.number_input("Nombre de postes", min_value=0, step=1, value=len(proj["postes"]))
    nb_postes = int(nb_postes)
    while len(proj["postes"]) < nb_postes:
        proj["postes"].append({"unites": [{"culture": 1, "sup": 0.0}]})
    while len(proj["postes"]) > nb_postes:
        proj["postes"].pop()

    culture_options = {i + 1: (c["name"] or f"Culture {i+1}") for i, c in enumerate(proj["cultures"])}

    for pi, poste in enumerate(proj["postes"]):
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**Poste {pi+1}**")
            nb_unites = c2.number_input("Nb. d'unités", min_value=0, step=1,
                                         value=len(poste["unites"]), key=f"nbu_{pi}")
            nb_unites = int(nb_unites)
            while len(poste["unites"]) < nb_unites:
                poste["unites"].append({"culture": 1, "sup": 0.0})
            while len(poste["unites"]) > nb_unites:
                poste["unites"].pop()

            for ui, u in enumerate(poste["unites"]):
                cu1, cu2, cu3 = st.columns([1, 2, 2])
                cu1.markdown(f"`{pi+1}{ui+1}`")
                u["culture"] = cu2.selectbox(
                    "Culture", options=list(culture_options.keys()),
                    format_func=lambda k: f"{k} — {culture_options[k]}",
                    index=list(culture_options.keys()).index(u["culture"]) if u["culture"] in culture_options else 0,
                    key=f"ucult_{pi}_{ui}", label_visibility="collapsed")
                u["sup"] = cu3.number_input("Superficie (m²)", value=float(u["sup"]), step=10.0,
                                             key=f"usup_{pi}_{ui}", label_visibility="collapsed")

            total = get_poste_total(proj, pi)
            st.caption(f"Superficie {total['sup']:,.0f} m² · Débit {total['debit']:.3f} m³/h".replace(",", " "))

    st.markdown("##### 5 · Tableau détaillé des postes d'irrigation")
    st.caption("Reproduction du tableau de la feuille POSTES d'Excel — une ligne par unité, "
               "avec les colonnes cumulées par poste.")
    detail = compute_postes_detail(proj)
    if detail:
        header_cols = ["Culture", "Superficie (m²)", "Poste", "Unité", "Unité",
                        "Cultures", "Durée d'irrigation (h/j)", "Superficie (m²)",
                        "Nb. de goutteurs", "Débits (m³/h)", "Durée CUMUL", "SUP CUMUL",
                        "Nb. de G CUMUL", "Débits CUMUL", "Débits G", "Ecart G"]
        html = ["<div style='overflow-x:auto;'><table style='border-collapse:collapse;width:100%;font-size:12.5px;'>"]
        html.append("<tr>" + "".join(
            f"<th style='background:#1e7d32;color:white;padding:6px 8px;border:1px solid #cfe3d1;white-space:nowrap;'>{h}</th>"
            for h in header_cols) + "</tr>")
        for r in detail:
            if r["type"] == "unite":
                bg = "#fdf6d8" if r["culture_code"] else "#ffffff"
                cells = [
                    r["culture_code"], f"{r['sup']:,.0f}".replace(",", " "), r["poste"], r["unite_idx"],
                    r["unite_code"], r["culture_nom"],
                    f"{r['duree']:.2f}" if r["duree"] is not None else "",
                    f"{r['sup']:,.0f}".replace(",", " "), f"{r['nb']:,.0f}".replace(",", " "),
                    f"{r['debit']:.1f}", f"{r['duree_cumul']:.2f}", f"{r['sup_cumul']:,.0f}".replace(",", " "),
                    f"{r['nb_cumul']:,.0f}".replace(",", " "), f"{r['debit_cumul']:.1f}",
                    f"{r['debit_g']:.2f}", f"{r['ecart_g']:.2f}",
                ]
                html.append("<tr>" + "".join(
                    f"<td style='background:{bg};padding:5px 8px;border:1px solid #e3ede4;text-align:center;'>{c}</td>"
                    for c in cells) + "</tr>")
            else:
                cells = ["", "", r["label"], r["poste"], "", "",
                         f"{r['duree_cumul']:.2f}", "", "", "",
                         f"{r['duree_cumul']:.2f}", f"{r['sup_cumul']:,.0f}".replace(",", " "),
                         f"{r['nb_cumul']:,.0f}".replace(",", " "), f"{r['debit_cumul']:.1f}", "", ""]
                html.append("<tr>" + "".join(
                    f"<td style='background:#1e7d32;color:white;font-weight:700;padding:5px 8px;"
                    f"border:1px solid #123d1c;text-align:center;'>{c}</td>"
                    for c in cells) + "</tr>")
        html.append("</table></div>")
        st.markdown("".join(html), unsafe_allow_html=True)
    else:
        st.caption("Aucune unité définie pour le moment.")

    pt = compute_postes(proj)
    st.markdown("##### 6 · Résultats par poste")
    st.table([
        {"Poste": f"Poste {r['poste']}", "Superficie (m²)": f"{r['sup']:.0f}",
         "Nb. goutteurs": f"{r['nb']:.1f}", "Débit (m³/h)": f"{r['debit']:.3f}",
         "Durée (h/j)": f"{r['duree']:.3f}"}
        for r in pt["poste_rows"]
    ] or [{"Poste": "—", "Superficie (m²)": "—", "Nb. goutteurs": "—", "Débit (m³/h)": "—", "Durée (h/j)": "—"}])
    st.markdown(f"**TOTAL GÉNÉRAL** — Superficie {pt['grand']['sup']:.0f} m² · "
                f"Goutteurs {pt['grand']['nb']:.1f} · Débit {pt['grand']['debit']:.3f} m³/h")

    st.markdown("##### 7 · Bilan des besoins en eau")
    if pt["besoin_rows"]:
        st.table([
            {"Culture": b["culture"], "Bb (m³/ha/j)": f"{b['bb']:.3f}",
             "Superficie (ha)": f"{b['sup_ha']:.3f}", "Volume (m³/j)": f"{b['volume']:.3f}"}
            for b in pt["besoin_rows"]
        ])
    st.markdown(f"**Besoin total / jour de pointe : {pt['total_volume']:.3f} m³**")
    vol_dispo = sum(f["debit"] * f["duree"] for f in proj.get("forages", []))
    ratio = (pt["total_volume"] / vol_dispo * 100) if vol_dispo else 0
    if ratio <= 100:
        st.markdown(f"<span class='kh-flag-ok'>Ressource suffisante ({ratio:.1f}% du volume disponible)</span>",
                    unsafe_allow_html=True)
    else:
        st.markdown(f"<span class='kh-flag-warn'>Déficit — forage insuffisant ({ratio:.1f}%)</span>",
                    unsafe_allow_html=True)


def tab_variation_r(proj):
    st.markdown("#### Variation de régime — Rampe")
    st.caption("Renseigne le code d'unité (ex. 11) défini dans POSTES. Chaque unité conserve ses propres "
               "paramètres de rampe, **pour 2 scénarios** (ex. pente positive / pente négative — comme les "
               "2 lignes par unité de la feuille TABLEAUX du classeur Excel).")
    c0a, c0b = st.columns([2, 3])
    code = c0a.number_input("Code unité (POSTES)", value=int(proj["varr"].get("unite") or 11), step=1)
    proj["varr"]["unite"] = code
    scenario_label = c0b.radio("Scénario", ["Scénario 1", "Scénario 2"], horizontal=True, key=f"r_scenario_{code}")
    scenario = 0 if scenario_label == "Scénario 1" else 1
    p = get_varr_for_unit(proj, code, scenario)

    c1, c2, c3 = st.columns(3)
    p["lr"] = c1.number_input("Lr — longueur rampe (m)", value=float(p["lr"]), step=0.1, key=f"r_lr_{code}_{scenario}")
    p["phi"] = c2.number_input("Φ int — diamètre (mm)", value=float(p["phi"]), step=0.1, key=f"r_phi_{code}_{scenario}")
    p["hentree"] = c3.number_input("H entrée (m)", value=float(p["hentree"]), step=0.1, key=f"r_h_{code}_{scenario}")
    c4, c5 = st.columns(2)
    p["dz"] = c4.number_input("Δz — dénivelé total (m)", value=float(p["dz"]), step=0.01, key=f"r_dz_{code}_{scenario}")
    c5.markdown("<div class='kh-computed'>Vitesse max. admise<br><b>1,0 m/s</b><br>"
                "<span style='font-size:10px;'>valeur fixe (norme Excel)</span></div>", unsafe_allow_html=True)
    p["doubleface"] = st.checkbox(
        "Rampe à deux faces (goutteurs des deux côtés du même tronçon — double le débit prélevé à chaque nœud)",
        value=p["doubleface"], key=f"r_df_{code}_{scenario}")

    r = compute_var_r_for_unit(proj, code, scenario)
    if r["lookup"]:
        lu = r["lookup"]
        st.markdown(
            f"<div class='kh-lookup'>Culture : <b>{lu['culture']['name']}</b> &nbsp;·&nbsp; "
            f"Qng : <b>{r['Qng']:.2f} l/h</b> &nbsp;·&nbsp; Eg : <b>{r['Eg']:.2f} m</b> &nbsp;·&nbsp; "
            f"Superficie unité : <b>{lu['sup_m2']:.0f} m²</b> &nbsp;·&nbsp; "
            f"Débit unité (Qpr) : <b>{lu['debit_m3h']:.3f} m³/h</b></div>", unsafe_allow_html=True)
    else:
        st.warning("Aucune unité correspondante dans POSTES pour ce code.")

    if r["Vmax"] > r["vmax"]:
        st.markdown(f"<div class='kh-flag-warn'>⚠ Vitesse maximale dépassée ({r['Vmax']:.2f} m/s &gt; "
                    f"{r['vmax']} m/s)</div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("ΔH total (m)", f"{r['dHTotal']:.3f}")
    c2.metric("Δq/q (%)", f"{r['dqq']*100:.2f}")
    c3.metric("Vitesse max. (m/s)", f"{r['Vmax']:.3f}")
    c4, c5, c6 = st.columns(3)
    c4.metric("P min (mCE)", f"{r['Pmin']:.3f}")
    c5.metric("P max (mCE)", f"{r['Pmax']:.3f}")
    c6.metric("Nb. tronçons", f"{r['nbTroncons']:.2f}")

    with st.expander("Tableau des tronçons"):
        st.dataframe([
            {"N°": row["i"], "Lcum (m)": f"{row['Lcum']:.1f}", "Q (l/h)": f"{row['Q']:.1f}",
             "ΔH (m)": f"{row['dH']:.4f}" if row["i"] else "-", "Δz (m)": f"{row['dz']:.4f}" if row["i"] else "-",
             "P (mCE)": f"{row['P']:.3f}", "V (m/s)": f"{row['V']:.3f}",
             "Vitesse": "Correct" if row["V"] <= r["vmax"] else "Excessive"}
            for row in r["rows"]
        ], width='stretch', hide_index=True)


def tab_variation_pr(proj):
    st.markdown("#### Variation de régime — Porte-rampe")
    st.caption("Le débit total (Qpr) et l'écartement (El) sont récupérés depuis POSTES. Chaque unité "
               "conserve ses propres paramètres, **pour 2 scénarios** (comme TABLEAUX dans le classeur Excel).")
    c0a, c0b = st.columns([2, 3])
    code = c0a.number_input("Code unité (POSTES)", value=int(proj["varpr"].get("unite") or 11), step=1, key="pr_unite")
    proj["varpr"]["unite"] = code
    scenario_label = c0b.radio("Scénario", ["Scénario 1", "Scénario 2"], horizontal=True, key=f"pr_scenario_{code}")
    scenario = 0 if scenario_label == "Scénario 1" else 1
    p = get_varpr_for_unit(proj, code, scenario)

    c2, c3 = st.columns(2)
    p["lpr"] = c2.number_input("Lpr — longueur porte-rampe (m)", value=float(p["lpr"]), step=0.1, key=f"pr_lpr_{code}_{scenario}")
    p["hentree"] = c3.number_input("H entrée (m)", value=float(p["hentree"]), step=0.1, key=f"pr_h_{code}_{scenario}")
    c4, c5 = st.columns(2)
    p["dz"] = c4.number_input("Δz — dénivelé total (m)", value=float(p["dz"]), step=0.01, key=f"pr_dz_{code}_{scenario}")
    c5.markdown("<div class='kh-computed'>Vitesse max. admise<br><b>1,5 m/s</b><br>"
                "<span style='font-size:10px;'>valeur fixe (norme Excel)</span></div>", unsafe_allow_html=True)
    p["doubleface"] = st.checkbox(
        "Porte-rampe à deux faces (rampes branchées des deux côtés à chaque nœud — double le débit prélevé par nœud)",
        value=p["doubleface"], key=f"pr_df_{code}_{scenario}")

    st.markdown("##### Allocation des diamètres le long du porte-rampe")
    st.caption("Longueur (m) à construire dans chaque diamètre, en partant de l'amont. Laisse à 0 pour tout garder au plus petit diamètre.")
    cols = st.columns(6)
    for i, col in enumerate(cols):
        p["alloc"][i] = col.number_input(f"Ø {PR_DIAM_LABELS[i]} mm\n({PR_DIAM_RANGES[i]} m³/h)",
                                          min_value=0.0, value=float(p["alloc"][i]), step=1.0, key=f"pralloc_{code}_{scenario}_{i}")

    pr = compute_var_pr_for_unit(proj, code, scenario)
    if pr["lookup"]:
        lu = pr["lookup"]
        st.markdown(
            f"<div class='kh-lookup'>Culture : <b>{lu['culture']['name']}</b> &nbsp;·&nbsp; "
            f"El : <b>{pr['El']:.2f} m</b> &nbsp;·&nbsp; Qpr : <b>{lu['debit_m3h']:.3f} m³/h</b> &nbsp;·&nbsp; "
            f"Q/rampe : <b>{pr['Qrampe']:.1f} l/h</b> &nbsp;·&nbsp; "
            f"Nb. rampes : <b>{pr['nbTroncons']:.2f}</b></div>", unsafe_allow_html=True)
    else:
        st.warning("Aucune unité correspondante dans POSTES pour ce code.")

    if pr["Vmax"] > pr["vmax"]:
        st.markdown(f"<div class='kh-flag-warn'>⚠ Vitesse maximale dépassée ({pr['Vmax']:.2f} m/s &gt; "
                    f"{pr['vmax']} m/s)</div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("ΔH total (m)", f"{pr['dHTotal']:.3f}")
    c2.metric("Δz total (m)", f"{pr['dzSum']:.3f}")
    c3.metric("Vitesse max. (m/s)", f"{pr['Vmax']:.3f}")
    c4, c5, c6 = st.columns(3)
    c4.metric("P min (mCE)", f"{pr['Pmin']:.3f}")
    c5.metric("P max (mCE)", f"{pr['Pmax']:.3f}")
    c6.metric("Nb. tronçons", f"{pr['nbTroncons']:.2f}")

    with st.expander("Tableau des tronçons"):
        st.dataframe([
            {"N°": row["i"], "Lcum (m)": f"{row['Lcum']:.1f}", "Φ (mm)": f"{row['D']:.1f}" if row["i"] else "-",
             "Q (l/h)": f"{row['Q']:.1f}", "ΔH (m)": f"{row['dH']:.4f}" if row["i"] else "-",
             "Δz (m)": f"{row['dz']:.4f}" if row["i"] else "-", "H (mCE)": f"{row['H']:.3f}",
             "V (m/s)": f"{row['V']:.3f}", "Vitesse": "Correct" if row["V"] <= pr["vmax"] else "Excessive"}
            for row in pr["rows"]
        ], width='stretch', hide_index=True)


def tab_tableaux(proj):
    st.markdown("#### TABLEAUX — Synthèse RAMPES / PORTES RAMPES", unsafe_allow_html=True)
    st.caption("2 lignes par unité (un scénario chacune — ex. pente positive / pente négative), "
               "comme la feuille TABLEAUX du classeur Excel. Configure chaque unité et ses 2 scénarios "
               "dans les onglets variation.R / variation PR.")

    rows = compute_tableaux_full(proj)
    if not rows:
        st.info("Aucune unité définie pour le moment — ajoute des postes/unités dans l'onglet POSTES.")
        return

    diam_cols = ["118,8/125", "104,1/110", "84,9/90", "69,9/75", "58,6/63", "46,4/50"]

    def speed_badge(ok):
        color, bg = ("#1e7d32", "#e4efe1") if ok else ("#b3261e", "#fbeceb")
        label = "Correct" if ok else "Incorrect"
        return f"<span style='background:{bg};color:{color};padding:2px 10px;border-radius:10px;font-weight:600;'>{label}</span>"

    r_head = ["Unité", "Lr (m)", "Qr (l/h)", "I (%)", "Dr (mm)", "Lpn (m)", "Lpx (m)", "DP (mCE)", "Speed"]
    r_html = ["<div style='overflow-x:auto;'><table style='border-collapse:collapse;width:100%;font-size:12.5px;'>"]
    r_html.append("<tr>" + "".join(f"<th style='background:#1e7d32;color:white;padding:6px 8px;border:1px solid #cfe3d1;'>{h}</th>" for h in r_head) + "</tr>")
    for r in rows:
        cells = [r["code"], f"{r['r_lr']:.0f}", f"{r['r_qr']:.0f}", f"{r['r_i']:.1f}%", f"{r['r_dr']:.0f}",
                 f"{r['r_lpn']:.0f}", f"{r['r_lpx']:.0f}", f"{r['r_dp']:.1f}", speed_badge(r["r_ok"])]
        r_html.append("<tr>" + "".join(f"<td style='padding:5px 8px;border:1px solid #e3ede4;text-align:center;'>{c}</td>" for c in cells) + "</tr>")
    r_html.append("</table></div>")
    st.markdown("###### RAMPES")
    st.markdown("".join(r_html), unsafe_allow_html=True)

    pr_head = ["Unité", "Lpr (m)", "Qpr (m³/h)", "I (%)"] + [f"{d} mm" for d in diam_cols] + ["Lpn (m)", "Lpx (m)", "ΔP (mCE)", "Speed", "El (m)"]
    pr_html = ["<div style='overflow-x:auto;'><table style='border-collapse:collapse;width:100%;font-size:12.5px;'>"]
    pr_html.append("<tr>" + "".join(f"<th style='background:#1e7d32;color:white;padding:6px 8px;border:1px solid #cfe3d1;white-space:nowrap;'>{h}</th>" for h in pr_head) + "</tr>")
    for r in rows:
        cells = [r["code"], f"{r['pr_lpr']:.0f}", f"{r['pr_qpr']:.1f}", f"{r['pr_i']:.1f}%"]
        cells += [f"{r['pr_alloc'][i]:.0f}" if r["pr_alloc"][i] else "" for i in range(6)]
        cells += [f"{r['pr_lpn']:.0f}", f"{r['pr_lpx']:.0f}", f"{r['pr_dp']:.1f}", speed_badge(r["pr_ok"]), f"{r['pr_el']:.2f}"]
        pr_html.append("<tr>" + "".join(f"<td style='padding:5px 8px;border:1px solid #e3ede4;text-align:center;'>{c}</td>" for c in cells) + "</tr>")
    pr_html.append("</table></div>")
    st.markdown("###### PORTES RAMPES")
    st.markdown("".join(pr_html), unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### Vérification des pressions au goutteur")
    c1, c2 = st.columns(2)
    proj["tableaux"]["pn"] = c1.number_input("Pression nominale du goutteur — Pn (mCE)",
                                              value=float(proj["tableaux"]["pn"]), step=0.1)
    proj["tableaux"]["tol"] = c2.number_input("Tolérance ΔP admise (%)",
                                               value=float(proj["tableaux"]["tol"]), step=1.0)
    pn = proj["tableaux"]["pn"]
    tol = proj["tableaux"]["tol"] / 100.0
    verif_rows = []
    for r in rows:
        dp_env = max(r["r_dp"], r["pr_dp"])
        ok = dp_env <= pn * tol
        verif_rows.append({
            "Unité": r["code"], "ΔP rampe (m)": f"{r['r_dp']:.3f}", "ΔP porte-rampe (m)": f"{r['pr_dp']:.3f}",
            "ΔP enveloppe (m)": f"{dp_env:.3f}", "Vérification": "Dans la tolérance" if ok else "Hors tolérance",
        })
    st.dataframe(verif_rows, width='stretch', hide_index=True)


def tab_principale(proj):
    st.markdown("#### PRINCIPALE — Conduite principale")
    st.caption("Dimensionnement des tronçons de la conduite principale.")
    st.table({"Débit (m³/h)": ["0–10", "10–15", "15–20", "20–30", "30–45", "45–60"],
              "Ø normalisé (mm)": [48.2, 60.8, 72.5, 87, 107, 121.6]})

    for i, t in enumerate(proj["principale"]):
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            t["name"] = c1.text_input("Tronçon", t["name"], key=f"ppname_{i}")
            t["q"] = c2.number_input("Q (m³/h)", value=float(t["q"]), step=0.1, key=f"ppq_{i}")
            t["mode"] = c3.selectbox("Mode", options=["normal", "up"],
                                      format_func=lambda m: "Surdimensionné (UP)" if m == "up" else "Normal",
                                      index=0 if t["mode"] == "normal" else 1, key=f"ppmode_{i}")
            res = compute_principale_row(t)
            with c4:
                st.write("")
                if st.button("×", key=f"ppdel_{i}"):
                    proj["principale"].pop(i)
                    st.rerun()
            if res["D"]:
                flag = "kh-flag-ok" if res["ok"] else "kh-flag-warn"
                st.caption(f"Φ retenu : **{res['D']:.1f} mm** · V = **{res['V']:.3f} m/s** · "
                           f"<span class='{flag}'>{'Correct' if res['ok'] else 'À vérifier'}</span>",
                           unsafe_allow_html=True)
            else:
                st.caption("<span class='kh-flag-warn'>Débit hors plage</span>", unsafe_allow_html=True)

    if st.button("+ Ajouter un tronçon"):
        proj["principale"].append({"name": "Nouveau tronçon", "q": 0.0, "mode": "normal"})
        st.rerun()


def tab_asecondaires(proj):
    st.markdown("#### A.secondaires — Antennes secondaires")
    st.caption("Une ligne par poste : le débit (Q) est récupéré automatiquement depuis POSTES.")
    st.table({"Débit (m³/h)": ["0–10", "10–15", "15–20", "20–30", "30–45", "45–60"],
              "Ø normalisé (mm)": [48.2, 60.8, 72.5, 87, 107, 121.6]})

    if not proj["postes"]:
        st.caption("Aucun poste défini pour l'instant (voir l'onglet POSTES).")
        return

    rows = []
    for pi in range(len(proj["postes"])):
        posteNum = pi + 1
        row = get_asec_row(proj, posteNum)
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"**Poste {posteNum}**")
            row["ls"] = c2.number_input("Ls (m)", value=float(row["ls"]), step=1.0, key=f"asls_{pi}")
            row["dz"] = c3.number_input("Δz (m)", value=float(row["dz"]), step=0.1, key=f"asdz_{pi}")
            row["mode"] = c4.selectbox("Mode", options=["normal", "up"],
                                        format_func=lambda m: "Surdimensionné (UP)" if m == "up" else "Normal",
                                        index=0 if row["mode"] == "normal" else 1, key=f"asmode_{pi}")
            a = compute_asec_row(proj, pi)
            if a["D"]:
                flag = "kh-flag-ok" if a["ok"] else "kh-flag-warn"
                st.caption(f"Q = **{a['debit']:.3f} m³/h** · Φ = **{a['D']:.1f} mm** · ΔH = **{a['dH']:.4f} m** · "
                           f"ΔP = **{a['dP']:.4f} m** · V = **{a['V']:.3f} m/s** · "
                           f"<span class='{flag}'>{'Correct' if a['ok'] else 'À vérifier'}</span>",
                           unsafe_allow_html=True)
            else:
                st.caption("Débit nul ou hors plage.")


# ---------------------------------------------------------------------------
# Router principal
# ---------------------------------------------------------------------------
def main():
    if not st.session_state.chef:
        render_login()
        return

    if not st.session_state.agriculteur:
        render_dashboard()
        return

    render_topbar()
    proj = st.session_state.proj

    tabs = st.tabs(["1 · POSTES", "2 · variation.R", "3 · variation PR", "4 · TABLEAUX",
                    "5 · PRINCIPALE", "6 · A.secondaires"])
    with tabs[0]:
        tab_profile_and_forage(proj)
        st.divider()
        tab_cultures(proj)
        st.divider()
        tab_postes(proj)
    with tabs[1]:
        tab_variation_r(proj)
    with tabs[2]:
        tab_variation_pr(proj)
    with tabs[3]:
        tab_tableaux(proj)
    with tabs[4]:
        tab_principale(proj)
    with tabs[5]:
        tab_asecondaires(proj)


if __name__ == "__main__":
    main()
