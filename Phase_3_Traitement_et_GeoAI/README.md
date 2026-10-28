# Phase 3 — Traitement spatial et modélisation Geo-AI (Séance 5 — À venir)

## Objectifs prévus pour la Séance 5

Cette phase s'appuiera directement sur la géodatabase PostGIS `sante` validée en **Phase 2** (`25 255` mailles H3, `228 022` nœuds connectés, `318 229` tronçons orientés et pondérés en secondes, `1 583` établissements rattachés au graphe) :

1. **Calcul des temps d'accès routiers réels (Dijkstra multi-sources)** :
   - Calcul de `temps_acces_hopital_min`, `temps_acces_soins_base_min` et `temps_acces_pharmacie_min` pour chacune des `25 255` mailles H3 à partir du graphe `sante.troncon` (`cout_secondes`).
2. **Indicateurs d'accessibilité spatiale (E2SFCA / gravitaire)** :
   - Combinaison de l'offre pondérée (`type_etablissement.poids_offre`), de la demande WorldPop (`pop_worldpop`) et de la décroissance temporelle.
3. **Modélisation Geo-AI / Machine Learning** :
   - Typologie non supervisée (clustering spatial / HDBSCAN ou K-Means contraint) et/ou modélisation prédictive (Random Forest / XGBoost avec validation croisée spatiale par blocs provinciaux) pour qualifier et expliquer les **déserts médicaux** (`classe_acces`).
