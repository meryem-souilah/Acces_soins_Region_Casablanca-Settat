"""
01_demo_carte.py — Démo séance 2 : superposer les sources testées et
produire un premier aperçu chiffré (pas encore une analyse !).

Entrées  : les fichiers produits par 00_test_acces.py dans preuves/
Sorties  : preuves/carte_demo.png       (capture pour le 1er jet / les slides)
           preuves/apercu_communes.csv  (population WorldPop et nb d'établissements
                                         par commune — indicateur brut)

Usage :
    python scripts/01_demo_carte.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import LogNorm
from rasterio.mask import mask

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

P = C.PREUVES
F_OSM = P / "osm_sante_echantillon.geojson"
F_COM = P / "communes_casablanca_settat.geojson"
F_POP = P / "worldpop_casablanca_settat.tif"

COULEURS = {"hospital": "#d62728", "clinic": "#1f77b4", "doctors": "#2ca02c",
            "pharmacy": "#9467bd", "dentist": "#8c564b"}


def charger():
    manquants = [f.name for f in (F_OSM, F_POP) if not f.exists()]
    if manquants:
        sys.exit(f"Fichiers manquants {manquants} : lancez d'abord 00_test_acces.py")
    etab = gpd.read_file(F_OSM)
    etab["type"] = etab["amenity"].fillna(etab["healthcare"]).fillna("autre")
    communes = gpd.read_file(F_COM) if F_COM.exists() else None
    if communes is not None:
        # on ne garde que les établissements situés dans la région
        region = communes.dissolve()
        etab = etab[etab.within(region.geometry.iloc[0])].copy()
    return etab, communes


def apercu_par_commune(etab, communes) -> pd.DataFrame:
    """Population WorldPop + nombre d'établissements par commune."""
    col_nom = next((c for c in communes.columns
                    if c.upper().startswith("ADM3") and c.upper().endswith(("_FR", "_EN"))),
                   communes.columns[0])
    lignes = []
    with rasterio.open(F_POP) as src:
        com = communes.to_crs(src.crs)
        for _, row in com.iterrows():
            try:
                data, _ = mask(src, [row.geometry], crop=True, nodata=0)
                pop = float(np.nansum(np.where(data > 0, data, 0)))
            except ValueError:   # commune hors du raster
                pop = np.nan
            lignes.append({"commune": row[col_nom], "population_worldpop": round(pop)})
    df = pd.DataFrame(lignes)
    jointure = gpd.sjoin(etab, communes[[col_nom, "geometry"]], predicate="within")
    nb = jointure.groupby(col_nom).size().rename("nb_etablissements")
    nb_hop = (jointure[jointure["type"].isin(["hospital", "clinic"])]
              .groupby(col_nom).size().rename("nb_hopitaux_cliniques"))
    df = df.join(nb, on="commune").join(nb_hop, on="commune").fillna(0)
    df["etab_pour_10k_hab"] = np.where(df["population_worldpop"] > 0,
                                       10_000 * df["nb_etablissements"] / df["population_worldpop"],
                                       np.nan).round(2)
    return df.sort_values("etab_pour_10k_hab")


def carte(etab, communes):
    fig, ax = plt.subplots(figsize=(11, 9), dpi=150)
    with rasterio.open(F_POP) as src:
        data = src.read(1).astype(float)
        data[data <= 0] = np.nan
        b = src.bounds
        im = ax.imshow(data, extent=(b.left, b.right, b.bottom, b.top),
                       cmap="Greys", norm=LogNorm(vmin=1, vmax=np.nanpercentile(data, 99.5)),
                       alpha=0.85, zorder=1)
    fig.colorbar(im, ax=ax, shrink=0.6, label="Habitants / pixel 100 m (WorldPop 2020)")
    if communes is not None:
        communes.to_crs(C.CRS_GEO).boundary.plot(ax=ax, color="#555", linewidth=0.3, zorder=2)
    for t, g in etab.groupby("type"):
        ax.scatter(g.geometry.x, g.geometry.y, s=6 if t == "pharmacy" else 14,
                   c=COULEURS.get(t, "#ff7f0e"), label=f"{t} ({len(g)})",
                   zorder=3 if t == "pharmacy" else 4, edgecolors="none")
    ax.legend(loc="lower left", fontsize=8, title="OSM — établissements")
    ax.set_title("Casablanca-Settat — établissements de santé (OSM) sur population (WorldPop)\n"
                 "Démo de superposition des sources — séance 2", fontsize=11)
    ax.set_xlabel("Longitude (EPSG:4326)")
    ax.set_ylabel("Latitude")
    if communes is not None:
        x0, y0, x1, y1 = communes.to_crs(C.CRS_GEO).total_bounds
        ax.set_xlim(x0 - 0.05, x1 + 0.05)
        ax.set_ylim(y0 - 0.05, y1 + 0.05)
    sortie = P / "carte_demo.png"
    fig.tight_layout()
    fig.savefig(sortie)
    print(f"Carte : {sortie}")


def main():
    etab, communes = charger()
    print(f"{len(etab)} établissements dans l'emprise")
    print(etab["type"].value_counts().head(8).to_string())
    carte(etab, communes)
    if communes is None:
        print("(Limites communales absentes : pas d'aperçu par commune.)")
        return
    df = apercu_par_commune(etab, communes)
    df.to_csv(P / "apercu_communes.csv", index=False, encoding="utf-8")
    print(f"\nPopulation WorldPop dans la région : {df['population_worldpop'].sum():,.0f} hab.")
    print(f"Communes sans aucun établissement OSM : {(df['nb_etablissements'] == 0).sum()} "
          f"/ {len(df)}")
    print("\n10 communes les moins dotées (indicateur BRUT, avant contrôle qualité) :")
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
