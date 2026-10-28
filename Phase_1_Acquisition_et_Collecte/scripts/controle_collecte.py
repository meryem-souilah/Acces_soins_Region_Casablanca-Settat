"""
controle_collecte.py — Vérification du jeu de données brut (CRS, emprise, volume)

À lancer après collecte.py. Pour chaque couche produite, le script vérifie :
  - que le CRS est bien EPSG:26191 (CRS unique du projet) ;
  - que les entités tombent dans la région (part hors emprise) ;
  - le nombre d'entités et de géométries invalides (à corriger en intersession 3) ;
  - pour la population, que la reprojection a conservé les effectifs.

Sorties :
    preuves/controle_collecte.md   rapport lisible (pour la séance 3)
    preuves/carte_controle.png     toutes les couches superposées en EPSG:26191

Usage :
    python scripts/controle_collecte.py
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402  (avant geopandas/rasterio : correctif PROJ)

import geopandas as gpd  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from matplotlib.colors import LogNorm  # noqa: E402

DB = C.DONNEES_BRUTES
CIBLE = C.CRS_METRIQUE
COUCHES = [  # (fichier, couche, libellé)
    (DB / "limites" / "limites_casablanca_settat.gpkg", "region", "Contour régional"),
    (DB / "limites" / "limites_casablanca_settat.gpkg", "communes", "Communes (OSM, codes HCP)"),
    (DB / "osm_sante" / "etablissements_sante.gpkg", "etablissements_sante", "Établissements de santé"),
    (DB / "osm_routes" / "routes_casablanca_settat.gpkg", "troncons", "Réseau routier (tronçons)"),
]
RASTER = DB / "worldpop" / "worldpop_2020_casablanca_settat_26191.tif"
TABLEAU_HCP = DB / "hcp" / "tableaux_bruts_region.csv"


def controle_jointure(communes) -> tuple[bool, list[str]]:
    """Chaque commune de la carte a-t-elle sa ligne dans le tableau de population HCP ?"""
    if communes is None or not TABLEAU_HCP.exists():
        return False, ["Jointure communes ↔ population HCP : ❌ couche communes ou tableau HCP absent."]
    with open(TABLEAU_HCP, encoding="utf-8", newline="") as f:
        lignes = list(csv.DictReader(f))
    hcp = {l["code_geographique"].rstrip(".") for l in lignes if l["collectivite"].startswith("Commune")}
    carte = set(communes["code_hcp"])
    ok = carte == hcp
    md = [f"Jointure communes ↔ population légale HCP 2024 (code géographique) : "
          f"**{len(carte & hcp)} / {len(carte)}** communes de la carte appariées, "
          f"{len(hcp)} communes dans le tableau HCP — {'✅' if ok else '⚠️'}"]
    if carte - hcp:
        md.append(f"Sans population HCP : {', '.join(sorted(carte - hcp))}")
    if hcp - carte:
        md.append(f"Sans polygone : {', '.join(sorted(hcp - carte))}")
    return ok, md


def epsg(crs) -> str:
    if crs is None:
        return "NON DÉFINI"
    code = crs.to_epsg()
    return f"EPSG:{code}" if code else crs.to_string()[:40]


def main():
    C.PREUVES.mkdir(parents=True, exist_ok=True)
    f_lim = COUCHES[0][0]
    if not f_lim.exists():
        sys.exit("Contour régional absent : lancez d'abord scripts/collecte.py")
    region = gpd.read_file(f_lim, layer="region")
    zone = region.buffer(50).union_all()  # 50 m de tolérance sur les bords

    lignes, chargees = [], {}
    for fichier, couche, libelle in COUCHES:
        if not fichier.exists():
            lignes.append((libelle, "absent", "—", "—", "—", "—", "❌ couche absente"))
            continue
        try:
            g = gpd.read_file(fichier, layer=couche)
        except Exception:
            lignes.append((libelle, "absent", "—", "—", "—", "—", "❌ couche absente"))
            continue
        chargees[couche] = g
        crs = epsg(g.crs)
        invalides = int((~g.geometry.is_valid).sum())
        if couche == "region":
            hors = 0
        else:
            hors = int((~g.geometry.representative_point().within(zone)).sum())
        ok = crs == CIBLE and hors == 0
        verdict = "✅" if ok else ("⚠️ CRS différent" if crs != CIBLE else f"⚠️ {hors} hors région")
        lignes.append((libelle, crs, f"{len(g):,}".replace(",", " "), str(invalides),
                       str(hors), g.geom_type.mode().iat[0] if len(g) else "—", verdict))

    pop = None
    if RASTER.exists():
        with rasterio.open(RASTER) as src:
            data = src.read(1, masked=True)
            total = float(data[data > 0].sum())
            crs = epsg(src.crs)
            b = src.bounds
            cx, cy = (b.left + b.right) / 2, (b.bottom + b.top) / 2
            dans = region.geometry.iloc[0].contains(gpd.points_from_xy([cx], [cy])[0])
            pop = (crs, src.res, total, src.width, src.height)
        manifest = json.loads((DB / "manifest.json").read_text(encoding="utf-8"))
        ref = manifest["sources"].get("worldpop", {}).get("population_region_4326")
        ecart = 100 * (total - ref) / ref if ref else None
        verdict = "✅" if crs == CIBLE and dans and (ecart is None or abs(ecart) < 1) else "⚠️"
        lignes.append(("Population WorldPop 100 m (raster)", crs,
                       f"{src.width}×{src.height} px", "—", "—",
                       f"total {total:,.0f} hab.".replace(",", " "),
                       verdict + (f" écart {ecart:+.2f} % vs 4326" if ecart is not None else "")))
    else:
        lignes.append(("Population WorldPop 100 m (raster)", "absent", "—", "—", "—", "—",
                       "❌ raster absent"))

    crs_vus = {l[1] for l in lignes if l[1] not in ("absent",)}
    absentes = [l[0] for l in lignes if l[1] == "absent"]
    uniforme = crs_vus == {CIBLE} and not absentes
    md = ["# Contrôle du jeu de données brut", "",
          f"Exécuté le {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} par "
          "`scripts/controle_collecte.py`.", "",
          f"**CRS uniforme : {'oui' if uniforme else ('oui pour les couches présentes, mais jeu INCOMPLET' if crs_vus == {CIBLE} else 'NON')}** — CRS rencontrés : "
          f"{', '.join(sorted(crs_vus)) or 'aucun'} (attendu : {CIBLE}).", "",
          *([f"Couches manquantes : {', '.join(absentes)}.", ""] if absentes else []),
          f"Surface de la région : {region.area.sum() / 1e6:,.0f} km².".replace(",", " "), "",
          "| Couche | CRS | Entités | Géométries invalides | Hors région | Type | Verdict |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    md += [f"| {' | '.join(l)} |" for l in lignes]
    jointure_ok, md_jointure = controle_jointure(chargees.get("communes"))
    md += ["", *md_jointure]
    md += ["", "Les géométries invalides ne sont pas corrigées à ce stade : la correction "
           "tracée (`ST_MakeValid`, rapport avant/après) relève de l'intersession 3."]
    (C.PREUVES / "controle_collecte.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # ── Carte de contrôle : toutes les couches dans le même CRS ──────────────
    fig, ax = plt.subplots(figsize=(10, 10), dpi=150)
    if RASTER.exists():
        with rasterio.open(RASTER) as src:
            d = src.read(1).astype(float)
            d[d <= 0] = np.nan
            b = src.bounds
            ax.imshow(d, extent=(b.left, b.right, b.bottom, b.top), cmap="Greys",
                      norm=LogNorm(vmin=0.5, vmax=np.nanpercentile(d, 99.5)), zorder=1)
    if "troncons" in chargees:
        chargees["troncons"].plot(ax=ax, color="#c8742a", linewidth=0.15, zorder=2)
    if "communes" in chargees:
        chargees["communes"].boundary.plot(ax=ax, color="#3b6e8f", linewidth=0.3, zorder=3)
    region.boundary.plot(ax=ax, color="#14232e", linewidth=1.2, zorder=4)
    if "etablissements_sante" in chargees:
        e = chargees["etablissements_sante"]
        hop = e["amenity"].isin(["hospital", "clinic"])
        ax.scatter(e[~hop].geometry.x, e[~hop].geometry.y, s=2, c="#1e8a80", zorder=5,
                   label=f"Autres établissements ({(~hop).sum()})")
        ax.scatter(e[hop].geometry.x, e[hop].geometry.y, s=10, c="#d62728", zorder=6,
                   label=f"Hôpitaux et cliniques ({hop.sum()})")
        ax.legend(loc="lower left", fontsize=8)
    ax.set_title(f"Casablanca-Settat — couches collectées superposées ({CIBLE})", fontsize=11)
    ax.set_xlabel("X (m, Merchich / Nord Maroc)")
    ax.set_ylabel("Y (m)")
    fig.tight_layout()
    fig.savefig(C.PREUVES / "carte_controle.png")

    print("\n".join(md))
    print(f"\nCarte : {C.PREUVES / 'carte_controle.png'}")
    sys.exit(0 if uniforme and jointure_ok else 1)


if __name__ == "__main__":
    main()
