# Projet d'Équipement en Matériel d'Irrigation Localisée (Streamlit)

Application de dimensionnement d'irrigation localisée, reconstituée à partir du
classeur Excel du bureau d'études : POSTES, variation.R, variation PR,
TABLEAUX, PRINCIPALE et A.secondaires.

## Installation

```bash
pip install -r requirements.txt
```

## Lancement

```bash
streamlit run app.py
```

L'application s'ouvre dans le navigateur (par défaut sur `http://localhost:8501`).

## Fonctionnement

- **Chef de service** : chaque membre du bureau d'études crée son propre compte
  (nom d'utilisateur + mot de passe) pour accéder à l'application.
- **Dossiers agriculteurs** : une fois connecté, le chef de service retrouve un
  répertoire **partagé** de tous les dossiers agriculteurs déjà créés,
  et peut en ouvrir un existant ou en créer un nouveau (nom, CIN, téléphone,
  localité).
- **Projet** : à l'intérieur d'un dossier agriculteur, les 6 onglets reproduisent le
  classeur Excel avec recalcul automatique (cultures, postes, rampes,
  porte-rampes, conduite principale, antennes secondaires) et un export PDF
  complet du dossier.

## Stockage des données

Les données sont enregistrées localement dans le dossier `data/` (créé
automatiquement au premier lancement) :

```
data/chefs.json              comptes des chefs de service
data/agriculteurs.json            répertoire partagé des dossiers agriculteurs
data/agriculteur_data/<cin>.json  projet complet de chaque agriculteur
```

Ce dossier `data/` doit être conservé (et sauvegardé) pour ne pas perdre les
dossiers. Pour un usage en réseau (plusieurs postes du bureau accédant aux
mêmes dossiers), lancez l'application sur un poste/serveur commun et faites-y
pointer les navigateurs du bureau, ou déployez-la sur un serveur interne —
`data/` doit alors résider sur ce serveur.

## Notes techniques

- Toutes les formules hydrauliques (`calc.py`) ont été vérifiées cellule par
  cellule contre les résultats du classeur Excel de référence.
- Le PDF est généré avec `reportlab` (pas de dépendance réseau).
- Le mot de passe des chefs de service est haché (SHA-256 + sel) avant
  stockage — ce n'est pas un niveau de sécurité bancaire, mais un contrôle
  d'accès raisonnable pour un usage interne au bureau d'études.
