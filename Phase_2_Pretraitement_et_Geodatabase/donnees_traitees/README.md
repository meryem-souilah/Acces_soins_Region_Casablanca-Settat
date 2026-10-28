# Données traitées et nettoyées (`EPSG:26191`)

Ce dossier contient les couches vectorielles issues du script [`scripts/nettoyage.py`](../scripts/nettoyage.py) (Phase 2 — Séance 4), toutes projetées en **`EPSG:26191` (Merchich / Nord Maroc)** et validées topologiquement avant import dans PostGIS (`sante.*`).

| Fichier | Taille | Contenu | Versionné sur Git |
|---|---:|---|---|
| [`sante_nettoyee_couches_legeres.gpkg`](sante_nettoyee_couches_legeres.gpkg) | 8,28 Mo | Couches `province` (9), `commune` (153), `etablissement` (1 583), `maille_h3` (25 255) | ✅ Oui |
| `sante_nettoyee.gpkg` | 115,75 Mo | Les 4 couches ci-dessus **+** le graphe routier complet (`noeud` : 228 554, `troncon` : 318 229) | ⚠️ Ignoré (> 100 Mo GitHub), régénéré en 25 s via `python scripts/nettoyage.py` ou restauré depuis [`sql/acces_soins.backup`](../sql/acces_soins.backup) (42,13 Mo, versionné) |
