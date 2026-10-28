"""
generer_presentation_seance4.py — Génère le support de présentation PDF 16:9 de la Séance 4
dans le même style graphique que `présentation_scéance3_acquisition.pdf`.
"""
from __future__ import annotations

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch, Rectangle
import matplotlib.image as mpimg

_parent = Path(__file__).resolve().parent.parent
RACINE = _parent.parent if _parent.name.startswith("Phase_") else _parent
CARTE_NETTOYAGE = RACINE / "preuves" / "carte_nettoyage.png"
SORTIE_REPO = RACINE / "presentation" / "seance4_pretraitement.pdf"
SORTIE_DOSSIER = RACINE.parent / "présentation_séance4_prétraitement.pdf"

ENCRE = "#14232E"
SARCELLE = "#1E8A80"
AMBRE = "#C8742A"
BLEU = "#2B7BB9"
ROUGE = "#C0392B"
GRIS = "#6B7280"
FOND = "#F1F4F7"
LIGNE = "#D9DEE3"

TOTAL_PAGES = 12


def nouvelle_page(num: int, section: str = "", titre: str = "", sombre: bool = False):
    fig = plt.figure(figsize=(16, 9), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")

    if sombre:
        ax.add_patch(Rectangle((0, 0), 16, 9, facecolor=ENCRE, edgecolor="none"))
        ax.add_patch(Rectangle((0, 0), 0.18, 9, facecolor=SARCELLE, edgecolor="none"))
    else:
        ax.add_patch(Rectangle((0, 0), 16, 9, facecolor="white", edgecolor="none"))
        ax.add_patch(Rectangle((0, 0), 0.18, 9, facecolor=SARCELLE, edgecolor="none"))
        if section:
            ax.text(1.1, 8.15, section.upper(), color=AMBRE, fontsize=11, fontweight="bold")
        if titre:
            ax.text(1.1, 7.62, titre, color=ENCRE, fontsize=22, fontweight="bold")
            ax.plot([1.1, 14.9], [7.32, 7.32], color=LIGNE, linewidth=1.2)
        ax.text(
            1.1, 0.42,
            "Accès aux soins — Casablanca-Settat   ·   Séance 4 — Pré-traitement et géodatabase PostGIS",
            color=GRIS, fontsize=9.5,
        )
        ax.text(14.9, 0.42, f"{num} / {TOTAL_PAGES}", color=GRIS, fontsize=9.5, fontweight="bold", ha="right")
    return fig, ax


def page_section(pdf: PdfPages, num_sec: str, titre: str, sous_titre: str):
    fig, ax = nouvelle_page(0, sombre=True)
    ax.text(1.3, 5.4, num_sec, color=AMBRE, fontsize=68, fontweight="bold")
    ax.text(1.3, 4.1, titre, color="white", fontsize=30, fontweight="bold")
    ax.text(1.3, 3.3, sous_titre, color="#94A3B8", fontsize=15)
    pdf.savefig(fig)
    plt.close(fig)


def carte_kpi(ax, x: float, y: float, w: float, h: float, couleur: str, val: str, lbl: str, sous: str):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.08", facecolor=FOND, edgecolor="none"))
    ax.add_patch(Rectangle((x, y), 0.10, h, facecolor=couleur, edgecolor="none"))
    ax.text(x + 0.25, y + h - 0.55, val, color=couleur, fontsize=21, fontweight="bold")
    ax.text(x + 0.25, y + h - 1.05, lbl, color=ENCRE, fontsize=12, fontweight="bold")
    ax.text(x + 0.25, y + 0.28, sous, color=GRIS, fontsize=9.5)


def construire_pdf(dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(dest) as pdf:
        # Slide 1 : Couverture
        fig = plt.figure(figsize=(16, 9), dpi=150)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 16)
        ax.set_ylim(0, 9)
        ax.axis("off")
        ax.add_patch(Rectangle((0, 0), 16, 9, facecolor="white", edgecolor="none"))
        ax.add_patch(Rectangle((0, 0), 8.2, 9, facecolor=ENCRE, edgecolor="none"))
        ax.add_patch(Rectangle((0, 0), 0.18, 9, facecolor=SARCELLE, edgecolor="none"))
        ax.text(0.9, 7.3, "GÉODATA APPLIQUÉE · SÉANCE 4", color=AMBRE, fontsize=12, fontweight="bold")
        ax.text(0.9, 5.5, "Accès aux soins\ndans la région\nCasablanca-Settat", color="white", fontsize=28, fontweight="bold", linespacing=1.18)
        ax.text(0.9, 3.9, "Pré-traitement, validation topologique\net géodatabase PostGIS (EPSG:26191)", color="#CBD5E1", fontsize=15, linespacing=1.3)
        ax.text(0.9, 2.0, "SOUILAH Meryem · MANYANI Hiba · ZOUHRI Imane\nBELMOKHTARE Fatima Ezzahra · GUEROUANE Imane", color="white", fontsize=10.5, linespacing=1.4)
        ax.text(0.9, 1.25, "Élèves ingénieurs 3e année", color="#94A3B8", fontsize=10.5)
        if CARTE_NETTOYAGE.exists():
            img = mpimg.imread(CARTE_NETTOYAGE)
            ax_img = fig.add_axes([0.52, 0.12, 0.46, 0.76])
            ax_img.imshow(img)
            ax_img.axis("off")
        pdf.savefig(fig)
        plt.close(fig)

        # Slide 2 : Plan
        fig, ax = nouvelle_page(2, "", "Déroulé de la présentation")
        items = [
            ("01", "Rappel du défi et cahier des charges", "Question spatiale et exigences de l'intersession 3"),
            ("02", "Pipeline de nettoyage et topologie", "Mode --dry-run, doublons point/polygone OSM, graphe routier et grille H3"),
            ("03", "Modèle de données (MCD / MLD) et schéma PostGIS", "8 tables normalisées, 10 clés étrangères, contraintes CHECK et index GIST"),
            ("04", "Requêtes spatiales métier et plans d'exécution", "3 requêtes pour la séance 5 évaluées avec EXPLAIN (ANALYZE, BUFFERS)"),
            ("05", "Démonstration live et sauvegarde", "Preuve de rejet FK/SRID, sauvegarde pg_dump et test de restauration"),
        ]
        for idx, (num, t, st) in enumerate(items):
            y = 6.3 - idx * 1.12
            ax.text(1.1, y, num, color=AMBRE, fontsize=20, fontweight="bold")
            ax.text(2.2, y + 0.12, t, color=ENCRE, fontsize=15, fontweight="bold")
            ax.text(2.2, y - 0.22, st, color=GRIS, fontsize=11)
            ax.plot([1.1, 14.9], [y - 0.45, y - 0.45], color=LIGNE, linewidth=0.9)
        pdf.savefig(fig)
        plt.close(fig)

        # Slide 3 : Section 01
        page_section(pdf, "01", "Le défi et les attendus de la séance 4", "De la donnée brute collectée à une géodatabase PostGIS opérationnelle")

        # Slide 4 : Checklist Intersession 3
        fig, ax = nouvelle_page(4, "Le défi et la phase", "Conformité complète au cahier des charges de l'intersession 3")
        lignes = [
            ("1. Détection/correction des géométries invalides, doublons, hors emprise", "scripts/nettoyage.py + ST_MakeValid (100 % valides)", "✓"),
            ("2. Mode « rapport seul » (--dry-run) et rapport avant/après", "python scripts/nettoyage.py --dry-run → preuves/rapport_nettoyage.md", "✓"),
            ("3. Cas réel de désaccord topologique du thème traité", "Doublons point/polygone OSM (< 35 m) + topologisation graphe routier", "✓"),
            ("4. DDL du schéma PostGIS, contraintes FK/CHECK, import ogr2ogr, index GIST", "sql/schema.sql (8 tables, 10 FK, 6 index GIST, 10 index B-tree)", "✓"),
            ("5. Trois requêtes spatiales métier utiles pour la séance 5 + EXPLAIN ANALYZE", "sql/requetes.sql + preuves/resultats_requetes_seance4.md", "✓"),
            ("6. Base peuplée, dump restaurable et test de restauration automatique", "sql/acces_soins.backup (42,1 Mo, pg_restore testé)", "✓"),
        ]
        ax.add_patch(Rectangle((1.1, 6.45), 13.8, 0.55, facecolor=ENCRE, edgecolor="none"))
        ax.text(1.3, 6.65, "Exigence de l'intersession 3", color="white", fontsize=11, fontweight="bold")
        ax.text(8.6, 6.65, "Livrable réalisé dans le dépôt", color="white", fontsize=11, fontweight="bold")
        ax.text(14.5, 6.65, "État", color="white", fontsize=11, fontweight="bold", ha="center")
        for i, (c1, c2, st) in enumerate(lignes):
            y = 5.65 - i * 0.78
            if i % 2 == 1:
                ax.add_patch(Rectangle((1.1, y - 0.22), 13.8, 0.75, facecolor=FOND, edgecolor="none"))
            ax.text(1.3, y + 0.08, c1, color=ENCRE, fontsize=10.5, fontweight="bold")
            ax.text(8.6, y + 0.08, c2, color=BLEU, fontsize=10, family="monospace")
            ax.text(14.5, y + 0.08, st, color=SARCELLE, fontsize=14, fontweight="bold", ha="center")
        pdf.savefig(fig)
        plt.close(fig)

        # Slide 5 : Section 02
        page_section(pdf, "02", "Nettoyage et validation topologique", "Traçabilité avant/après, mode --dry-run et résolution des conflits spatiaux")

        # Slide 6 : Bilan chiffré
        fig, ax = nouvelle_page(6, "Nettoyage et topologie", "Bilan avant / après nettoyage (toutes couches en EPSG:26191)")
        carte_kpi(ax, 1.1, 5.25, 2.55, 1.65, BLEU, "153 / 153", "Communes HCP", "9 provinces, 7,69 M hab.")
        carte_kpi(ax, 3.9, 5.25, 2.55, 1.65, ROUGE, "1 583", "Établissements", "146 hors région, 8 topo")
        carte_kpi(ax, 6.7, 5.25, 2.55, 1.65, AMBRE, "318 229", "Arcs routiers", "228 554 nœuds (99,8 %)")
        carte_kpi(ax, 9.5, 5.25, 2.55, 1.65, SARCELLE, "25 255", "Hexagones H3", "7 113 peuplés (7,39 M)")
        carte_kpi(ax, 12.3, 5.25, 2.60, 1.65, ENCRE, "100 %", "Géom. valides", "ST_IsValid vérifié")

        rows = [
            ("province", "153 communes", "0 → 0", "0", "Fermeture ±5 m", "9 MultiPolygon"),
            ("commune", "153 relations OSM", "0 → 0", "0", "0 hors région", "153 (100 % jointes HCP)"),
            ("etablissement", "1 737 points/bât.", "0 → 0", "8 doublons topo (< 35 m)", "146 hors région", "1 583 Point"),
            ("troncon", "130 783 voies OSM", "0 → 0", "0", "196 boucles (départ=arrivée)", "318 229 LineString"),
            ("noeud", "Non topologisé", "0 → 0", "—", "532 en îlots isolés exclus", "228 554 Point"),
            ("maille_h3", "26 789 cellules", "0 → 0", "0", "1 534 hors région", "25 255 Polygon"),
        ]
        headers = ["Table PostGIS", "Entités brutes", "Invalides", "Doublons traités", "Hors région / boucles", "Entités propres"]
        xs = [1.2, 3.5, 6.0, 7.6, 10.5, 13.3]
        ax.add_patch(Rectangle((1.1, 4.35), 13.8, 0.48, facecolor=ENCRE, edgecolor="none"))
        for x, h in zip(xs, headers):
            ax.text(x, 4.52, h, color="white", fontsize=10, fontweight="bold")
        for i, r in enumerate(rows):
            y = 3.82 - i * 0.48
            if i % 2 == 1:
                ax.add_patch(Rectangle((1.1, y - 0.14), 13.8, 0.46, facecolor=FOND, edgecolor="none"))
            for j, (x, val) in enumerate(zip(xs, r)):
                ax.text(x, y, val, color=ENCRE if j < 5 else SARCELLE, fontsize=9.8, fontweight="bold" if j in (0, 5) else "normal")
        pdf.savefig(fig)
        plt.close(fig)

        # Slide 7 : Désaccords topologiques traités
        import textwrap
        fig, ax = nouvelle_page(7, "Nettoyage et topologie", "Trois cas réels de désaccord topologique et sémantique résolus")
        blocs = [
            (
                "A", "Doublons point / polygone",
                [
                    "Dans OSM, plusieurs établissements sont saisis à la fois comme bâtiment (way/*) et comme point (node/*) à quelques mètres d'écart.",
                    "• Détection par arbre KD (rayon ≤ 35 m) à code_type identique.",
                    "• Fusion des attributs (nom, secteur, nb_lits, urgences) vers l'entité principale.",
                    "• 8 doublons éliminés : Hôpital Sidi Othmane (21,9 m), Clinique Avicenne (16,0 m), Pharmacie Al Fath (2,7 m)...",
                ]
            ),
            (
                "B", "Topologie du graphe routier",
                [
                    "Les 130 783 voies Geofabrik ne sont pas découpées aux carrefours et comportent des boucles et îlots isolés.",
                    "• Détection vectorisée des sommets partagés (≥ 2 voies, précision 0,1 m) et découpage en 318 229 arcs.",
                    "• Élimination de 196 boucles (noeud_depart = noeud_arrivee).",
                    "• Filtrage de 91 micro-îlots isolés (532 nœuds) : 99,8 % du graphe est connexe (accrochage médian = 22,4 m).",
                ]
            ),
            (
                "C", "Conflits tags OSM & CHU",
                [
                    "Certains centres de radiologie, labos ou kinés sont tagués clinic, et des cliniques privées sont taguées hospital.",
                    "• Recroisement sémantique du nom avec les tags OSM (labo/radio/kiné → autre, inclus_analyse = false).",
                    "• Relecture métier tracée (niveau_source = 'relecture') pour les 5 hôpitaux de niveau 3 (CHU Ibn Rochd, 20 Août, Harouchi, Cheikh Khalifa, Mohammed VI).",
                ]
            ),
        ]
        for idx, (lettre, titre_b, paras) in enumerate(blocs):
            x = 1.1 + idx * 4.7
            ax.add_patch(FancyBboxPatch((x, 1.15), 4.4, 5.7, boxstyle="round,pad=0.05,rounding_size=0.1", facecolor=FOND, edgecolor=LIGNE))
            ax.text(x + 0.22, 6.25, lettre, color=AMBRE, fontsize=25, fontweight="bold")
            ax.text(x + 0.78, 6.30, titre_b, color=ENCRE, fontsize=12.0, fontweight="bold")
            wrapped = "\n\n".join(textwrap.fill(p, width=44) for p in paras)
            ax.text(x + 0.22, 5.82, wrapped, color=ENCRE, fontsize=9.6, va="top", linespacing=1.32)
        pdf.savefig(fig)
        plt.close(fig)

        # Slide 8 : Carte de contrôle
        fig, ax = nouvelle_page(8, "Nettoyage et topologie", "Contrôle visuel des couches nettoyées en EPSG:26191")
        if CARTE_NETTOYAGE.exists():
            img = mpimg.imread(CARTE_NETTOYAGE)
            ax_img = fig.add_axes([0.07, 0.09, 0.86, 0.72])
            ax_img.imshow(img)
            ax_img.axis("off")
        pdf.savefig(fig)
        plt.close(fig)

        # Slide 9 : Section 03 — Modèle et schéma PostGIS
        page_section(pdf, "03", "Modèle (MCD / MLD) et schéma PostGIS", "8 tables normalisées, 10 clés étrangères, contraintes CHECK et index GIST")

        # Slide 10 : Architecture PostGIS & Contraintes
        fig, ax = nouvelle_page(10, "Modèle et schéma PostGIS", "Architecture du schéma `sante` et preuves de rejet d'intégrité")
        tables_info = [
            ("sante.province (9)", "PK code_province · MultiPolygon, 26191 · CHECK type_province IN ('province','prefecture') · ST_IsValid"),
            ("sante.commune (153)", "PK code_hcp · FK code_province (RESTRICT) · MultiPolygon, 26191 · CHECK pop_2024 >= 0 · ST_IsValid"),
            ("sante.niveau_soin (3)", "PK code_niveau (1, 2, 3) · seuil_acces_min (15, 30, 60 min) · source_norme · couvre_niveaux_inferieurs"),
            ("sante.type_etablissement (7)", "PK code_type · FK niveau_defaut · inclus_analyse (true: hopital/clinique/centre/medecin ; false: pharma/dentiste/autre)"),
            ("sante.etablissement (1 583)", "PK id_etab · osm_id UNIQUE · FK code_type, code_niveau, code_hcp, id_noeud · CHECK niveau_source, secteur, nb_lits"),
            ("sante.maille_h3 (25 255)", "PK h3_index · FK code_hcp, id_noeud · Polygon, 26191 · CHECK population >= 0, resolution 0..15, ST_IsValid"),
            ("sante.noeud (228 554)", "PK id_noeud · Point, 26191 · Sommets d'intersection du graphe routier régional"),
            ("sante.troncon (318 229)", "PK id_troncon · FK noeud_depart, noeud_arrivee (CASCADE) · CHECK longueur_m > 0, noeud_depart <> noeud_arrivee"),
        ]
        for i, (tname, tdesc) in enumerate(tables_info):
            y = 6.65 - i * 0.56
            ax.add_patch(Rectangle((1.1, y - 0.14), 13.8, 0.48, facecolor=FOND if i % 2 == 0 else "white", edgecolor=LIGNE, linewidth=0.5))
            ax.text(1.25, y + 0.04, tname, color=BLEU, fontsize=10, fontweight="bold", family="monospace")
            ax.text(5.1, y + 0.04, tdesc, color=ENCRE, fontsize=9.5)

        ax.add_patch(FancyBboxPatch((1.1, 0.95), 13.8, 1.35, boxstyle="round,pad=0.04,rounding_size=0.08", facecolor=ENCRE, edgecolor="none"))
        ax.text(1.35, 2.02, "TESTS DE REJET EXÉCUTÉS SUR POSTGRESQL 16 / POSTGIS 3.5 (4 / 4 REJETÉS COMME ATTENDU) :", color=AMBRE, fontsize=10, fontweight="bold")
        ax.text(
            1.35, 1.15,
            "1. FK commune inexistante : ERROR: insert or update on table \"etablissement\" violates foreign key constraint \"etablissement_code_hcp_fkey\"\n"
            "2. SRID 4326 invalide     : ERROR: Geometry SRID (4326) does not match column SRID (26191)\n"
            "3. Boucle routière (u=v)  : ERROR: new row for relation \"troncon\" violates check constraint \"troncon_noeuds_distincts\"",
            color="white", fontsize=9.2, family="monospace", linespacing=1.35,
        )
        pdf.savefig(fig)
        plt.close(fig)

        # Slide 11 : Requêtes spatiales métier et EXPLAIN ANALYZE
        fig, ax = nouvelle_page(11, "Requêtes métier et performances", "Trois requêtes spatiales pour la séance 5 validées par EXPLAIN ANALYZE")
        reqs = [
            (
                "Requête 1 — Diagnostic communal par niveau de soin (6,5 ms)",
                "Opérateur : ST_Within(e.geom, c.geom) + ST_Area(c.geom) · Plan : Index Scan using etablissement_geom_gist",
                "Identifie les communes les plus peuplées dépourvues d'offre active (inclus_analyse = true) :\n"
                "• Bni Yakhlef (Mohammadia) : 117 653 hab. (1 989 hab./km²) — 0 établissement de niveau 1/2 (8 pharmacies/dentistes)\n"
                "• Chellalate (Mohammadia) : 98 015 hab. — 0 établissement actif  |  Deroua (Berrechid) : 96 619 hab. — 0 établissement actif"
            ),
            (
                "Requête 2 — Baseline euclidienne KNN par hexagone H3 peuplé (355,8 ms sur 7 113 mailles)",
                "Opérateur : CROSS JOIN LATERAL + ORDER BY ST_Centroid(m.geom) <-> e.geom LIMIT 1 · Plan : Index Scan GIST KNN",
                "Calcule pour chaque hexagone H3 peuplé la distance à l'établissement actif le plus proche (baseline pour la séance 5) :\n"
                "• Deroua : 62 249 hab. à > 10 km (dist. moy. 11,1 km)  |  Sahel Oulad H'riz : 40 972 hab. à > 10 km  |  El Gara : 39 950 hab. à 23,1 km\n"
                "• Lgharbia (Sidi Bennour) et Ouled Ghanem (El Jadida) : distance jusqu'à 51,4 km de l'offre de soin la plus proche !"
            ),
            (
                "Requête 3 — Connectivité routière autour des hôpitaux de niveau 2 et 3 (1 222 ms sur 318 229 tronçons)",
                "Opérateur : ST_DWithin(e.geom, tr.geom, 2000) + ST_Distance(e.geom, n.geom) · Plan : Index Scan using troncon_geom_gist",
                "Vérifie l'accrochage de chaque hôpital/clinique au graphe routier et mesure le linéaire et le coût moyen dans un rayon de 2 km :\n"
                "• Distance médiane d'accrochage des établissements au nœud routier le plus proche : 22,4 m (max 264,6 m à Sidi Ali Ben Hamdouche).\n"
                "• Le graphe (noeud, troncon) et les coûts élémentaires sont prêts pour le calcul de plus court chemin en séance 5."
            ),
        ]
        for idx, (rtitre, rplan, rres) in enumerate(reqs):
            y = 5.45 - idx * 1.98
            ax.add_patch(FancyBboxPatch((1.1, y), 13.8, 1.72, boxstyle="round,pad=0.04,rounding_size=0.08", facecolor=FOND, edgecolor=LIGNE))
            ax.add_patch(Rectangle((1.1, y), 0.12, 1.72, facecolor=SARCELLE if idx != 1 else AMBRE, edgecolor="none"))
            ax.text(1.38, y + 1.40, rtitre, color=ENCRE, fontsize=12, fontweight="bold")
            ax.text(1.38, y + 1.08, rplan, color=BLEU, fontsize=9.8, family="monospace", fontweight="bold")
            ax.text(1.38, y + 0.18, rres, color=ENCRE, fontsize=9.6, linespacing=1.32)
        pdf.savefig(fig)
        plt.close(fig)

        # Slide 12 : Sauvegarde, reproductibilité et conclusion
        fig, ax = nouvelle_page(12, "Démonstration et suite", "Rejeu en une commande, sauvegarde restaurable et cap sur la séance 5")
        carte_kpi(ax, 1.1, 5.1, 4.3, 1.75, SARCELLE, "--dry-run", "Mode rapport seul", "Diagnostic complet sans écriture")
        carte_kpi(ax, 5.85, 5.1, 4.3, 1.75, BLEU, "42,13 Mo", "Dump PostGIS (.backup)", "Restauration testée via pg_restore")
        carte_kpi(ax, 10.6, 5.1, 4.3, 1.75, AMBRE, "Séance 5", "Prochaine étape : Geo-AI", "Temps d'accès routier & ML spatial")

        ax.add_patch(FancyBboxPatch((1.1, 1.35), 13.8, 3.3, boxstyle="round,pad=0.04,rounding_size=0.08", facecolor=ENCRE, edgecolor="none"))
        ax.text(1.4, 4.25, "COMMANDES DE DÉMONSTRATION LIVE (SÉANCE 4) :", color=AMBRE, fontsize=11, fontweight="bold")
        ax.text(
            1.4, 1.70,
            "# 1. Exécuter le nettoyage en mode « rapport seul » (aucune modification des fichiers)\n"
            "python scripts/nettoyage.py --dry-run\n\n"
            "# 2. Nettoyer les couches, créer le schéma PostGIS, importer via ogr2ogr, tester les FK et sauvegarder\n"
            "python scripts/nettoyage.py && python scripts/import_postgis.py\n\n"
            "# 3. Exécuter en direct les 3 requêtes spatiales métier et leurs plans EXPLAIN (ANALYZE, BUFFERS)\n"
            "psql -h 127.0.0.1 -U postgres -d acces_soins -f sql/requetes.sql",
            color="white", fontsize=10.2, family="monospace", linespacing=1.35,
        )
        pdf.savefig(fig)
        plt.close(fig)


if __name__ == "__main__":
    construire_pdf(SORTIE_REPO)
    construire_pdf(SORTIE_DOSSIER)
    print(f"Présentations générées :\n  - {SORTIE_REPO}\n  - {SORTIE_DOSSIER}")
