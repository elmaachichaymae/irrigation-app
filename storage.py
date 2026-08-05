"""
Couche de stockage — fichiers JSON locaux (aucune base de données externe requise).

Structure sur disque (dossier `data/` créé automatiquement à côté de app.py) :
  data/chefs.json          -> {"username": {"pwhash": "...", "salt": "..."}}
  data/agriculteurs.json        -> [{"cin":..., "nom":..., "tel":..., "localite":..., "updated_at":...}]
  data/agriculteur_data/<cin>.json -> état complet du projet pour ce agriculteur
"""
import json
import os
import hashlib
import secrets

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
AGRICULTEUR_DATA_DIR = os.path.join(DATA_DIR, "agriculteur_data")
CHEFS_FILE = os.path.join(DATA_DIR, "chefs.json")
AGRICULTEURS_FILE = os.path.join(DATA_DIR, "agriculteurs.json")


def _ensure_dirs():
    os.makedirs(AGRICULTEUR_DATA_DIR, exist_ok=True)


def _read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path, obj):
    _ensure_dirs()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Chefs de service (comptes du personnel du bureau d'études)
# ---------------------------------------------------------------------------

def _hash_password(password, salt):
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def load_chefs():
    return _read_json(CHEFS_FILE, {})


def save_chefs(chefs):
    _write_json(CHEFS_FILE, chefs)


def create_chef(username, password):
    chefs = load_chefs()
    key = username.strip().lower()
    if key in chefs:
        return False, "Ce nom d'utilisateur existe déjà."
    salt = secrets.token_hex(16)
    chefs[key] = {"username": username.strip(), "salt": salt, "pwhash": _hash_password(password, salt)}
    save_chefs(chefs)
    return True, None


def verify_chef(username, password):
    chefs = load_chefs()
    key = username.strip().lower()
    rec = chefs.get(key)
    if not rec:
        return False, "Aucun compte avec ce nom. Crée un compte d'abord."
    if _hash_password(password, rec["salt"]) != rec["pwhash"]:
        return False, "Mot de passe incorrect."
    return True, rec["username"]


# ---------------------------------------------------------------------------
# Répertoire des agriculteurs (partagé entre tous les chefs de service)
# ---------------------------------------------------------------------------

def load_agriculteur_index():
    return _read_json(AGRICULTEURS_FILE, [])


def save_agriculteur_index(index):
    _write_json(AGRICULTEURS_FILE, index)


def upsert_agriculteur(rec):
    """rec: {"cin":..., "nom":..., "tel":..., "localite":..., "updated_at":...}"""
    index = load_agriculteur_index()
    cin = rec["cin"].strip().upper()
    rec = {**rec, "cin": cin}
    for i, f in enumerate(index):
        if f["cin"] == cin:
            index[i] = rec
            save_agriculteur_index(index)
            return
    index.append(rec)
    save_agriculteur_index(index)


def agriculteur_data_path(cin):
    return os.path.join(AGRICULTEUR_DATA_DIR, cin.strip().lower() + ".json")


def load_agriculteur_project(cin):
    return _read_json(agriculteur_data_path(cin), None)


def save_agriculteur_project(cin, state):
    _write_json(agriculteur_data_path(cin), state)


def delete_agriculteur(cin):
    """Removes an agriculteur from the shared directory and deletes their project file."""
    cin_u = cin.strip().upper()
    index = load_agriculteur_index()
    index = [f for f in index if f["cin"] != cin_u]
    save_agriculteur_index(index)
    path = agriculteur_data_path(cin_u)
    if os.path.exists(path):
        os.remove(path)
