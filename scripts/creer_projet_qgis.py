"""
creer_projet_qgis.py — Projet QGIS de vérification des couches collectées

Construit preuves/verification_couches_26191.qgz : toutes les couches produites
par collecte.py, stylées et superposées en EPSG:26191, vue cadrée sur la région.
Écrit aussi preuves/apercu_couches_26191.png, le rendu de la carte par QGIS.

À lancer avec le Python de QGIS (PyQGIS), pas avec celui de l'environnement conda :
    "C:\\Program Files\\QGIS 4.2.3\\bin\\python-qgis.bat" scripts\\creer_projet_qgis.py
"""
from pathlib import Path

from qgis.core import (Qgis, QgsApplication, QgsCategorizedSymbolRenderer, QgsColorRampShader,
                       QgsCoordinateReferenceSystem, QgsFillSymbol, QgsLineSymbol, QgsMapRendererParallelJob,
                       QgsMapSettings, QgsMarkerSymbol, QgsProject, QgsRasterLayer, QgsRasterShader,
                       QgsReferencedRectangle, QgsRendererCategory, QgsSingleBandPseudoColorRenderer,
                       QgsVectorLayer)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor

RACINE = Path(__file__).resolve().parent.parent
DB = RACINE / "donnees_brutes"
SORTIE = RACINE / "preuves" / "verification_couches_26191.qgz"
APERCU = RACINE / "preuves" / "apercu_couches_26191.png"

app = QgsApplication([], False)
app.initQgis()
projet = QgsProject.instance()
crs = QgsCoordinateReferenceSystem("EPSG:26191")
projet.setCrs(crs)
projet.setTitle("Accès aux soins Casablanca-Settat — vérification des couches (EPSG:26191)")


def vecteur(fichier, couche, nom):
    lyr = QgsVectorLayer(f"{fichier}|layername={couche}", nom, "ogr")
    if not lyr.isValid():
        raise SystemExit(f"Couche invalide : {fichier} ({couche}). Lancez d'abord collecte.py.")
    return lyr


# 1. Population WorldPop (en bas) : un pixel = 1 ha, donc valeur = habitants par hectare
pop = QgsRasterLayer(str(DB / "worldpop" / "worldpop_2020_casablanca_settat_26191.tif"),
                     "Population WorldPop 2020 (hab./pixel 100 m)")
if not pop.isValid():
    raise SystemExit("Raster WorldPop absent. Lancez d'abord collecte.py.")
paliers = [(1, "#fff5eb", "< 1"), (5, "#fdd0a2", "1 – 5"), (20, "#fdae6b", "5 – 20"),
           (50, "#fd8d3c", "20 – 50"), (100, "#e6550d", "50 – 100"), (250, "#a63603", "100 – 250"),
           (1e9, "#7f2704", "> 250")]
rampe = QgsColorRampShader()
rampe.setColorRampType(Qgis.ShaderInterpolationMethod.Discrete)
rampe.setColorRampItemList([QgsColorRampShader.ColorRampItem(v, QColor(c), e) for v, c, e in paliers])
shader = QgsRasterShader()
shader.setRasterShaderFunction(rampe)
pop.setRenderer(QgsSingleBandPseudoColorRenderer(pop.dataProvider(), 1, shader))
pop.renderer().setOpacity(0.85)

# 2. Routes
routes = vecteur(DB / "osm_routes" / "routes_casablanca_settat.gpkg", "troncons", "Réseau routier (tronçons)")
routes.renderer().setSymbol(QgsLineSymbol.createSimple({"color": "110,110,110,170", "width": "0.12"}))

# 3. Communes : contour seul, pour laisser voir population et routes
communes = vecteur(DB / "limites" / "limites_casablanca_settat.gpkg", "communes", "Communes (code HCP)")
communes.renderer().setSymbol(QgsFillSymbol.createSimple(
    {"style": "no", "outline_color": "43,123,185", "outline_width": "0.25"}))

# 4. Contour régional
region = vecteur(DB / "limites" / "limites_casablanca_settat.gpkg", "region", "Contour régional")
region.renderer().setSymbol(QgsFillSymbol.createSimple(
    {"style": "no", "outline_color": "20,35,46", "outline_width": "0.8"}))

# 5. Établissements de santé (en haut) : couleur et taille selon le type
sante = vecteur(DB / "osm_sante" / "etablissements_sante.gpkg", "etablissements_sante", "Établissements de santé")
types = [("hospital", "Hôpital", "#d62728", 3.2), ("clinic", "Clinique", "#9467bd", 2.6),
         ("doctors", "Médecin", "#1f77b4", 2.0), ("dentist", "Dentiste", "#17becf", 2.0),
         ("pharmacy", "Pharmacie", "#2ca02c", 1.4)]


def point(couleur, taille):
    return QgsMarkerSymbol.createSimple({"name": "circle", "color": couleur, "size": str(taille),
                                         "outline_color": "255,255,255", "outline_width": "0.2"})


categories = [QgsRendererCategory(v, point(c, t), e) for v, e, c, t in types]
categories.append(QgsRendererCategory(None, point("#7f7f7f", 1.4), "Autre (laboratoire, kiné…)"))
sante.setRenderer(QgsCategorizedSymbolRenderer("amenity", categories))

for lyr in (pop, routes, communes, region, sante):   # chaque ajout passe au-dessus du précédent
    projet.addMapLayer(lyr)

etendue = region.extent().buffered(4000)
projet.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(etendue, crs))
if not projet.write(str(SORTIE)):
    raise SystemExit(f"Échec de l'enregistrement de {SORTIE}")
print(f"Projet QGIS : {SORTIE}")

# Rendu de la carte par QGIS, pour vérifier le style sans ouvrir l'interface
reglages = QgsMapSettings()
reglages.setLayers([sante, region, communes, routes, pop])
reglages.setDestinationCrs(crs)
reglages.setExtent(etendue)
reglages.setOutputSize(QSize(1400, 1100))
reglages.setBackgroundColor(QColor("white"))
rendu = QgsMapRendererParallelJob(reglages)
rendu.start()
rendu.waitForFinished()
rendu.renderedImage().save(str(APERCU))
print(f"Aperçu : {APERCU}")
app.exitQgis()
