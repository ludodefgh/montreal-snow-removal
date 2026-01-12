# Custom Map Card - Installation Guide

Cette carte personnalisée affiche les **segments de rue complets** (pas juste des points) avec des couleurs selon le statut de déneigement.

## Résultat attendu

Au lieu de voir des marqueurs ponctuels, tu verras les **rues tracées en couleur** sur la carte :
- 🔴 **Rouge** - Lignes rouges pour les rues avec déneigement planifié
- 🟡 **Jaune** - Lignes jaunes pour le déneigement en cours
- 🟢 **Vert** - Lignes vertes pour les rues déneigées
- 🟠 **Orange** - Lignes oranges pour les rues replanifiées
- ⚪ **Gris** - Lignes grises pour les conditions dégagées
- 🔵 **Bleu** - Lignes bleues pour les rues enneigées

## Installation

### Étape 1 : Copier le fichier JavaScript

Il y a **deux options** :

#### Option A : Via le dossier `www` de Home Assistant (Recommandé)

1. Localise ton dossier `config/www/` de Home Assistant
2. Copie le fichier :
   ```bash
   cp www/montreal-snow-removal-map-card.js /path/to/homeassistant/config/www/
   ```

#### Option B : Via HACS (si tu publies la carte séparément)

1. Dans HACS, clique sur "Frontend"
2. Clique sur le menu (3 points) → "Custom repositories"
3. Ajoute l'URL de ton repo
4. Installe "Montreal Snow Removal Map Card"

### Étape 2 : Ajouter la ressource dans Lovelace

1. Va dans **Settings** → **Dashboards**
2. Clique sur le menu (3 points en haut à droite) → **Resources**
3. Clique sur **+ Add Resource**
4. Configure :
   - **URL** : `/local/montreal-snow-removal-map-card.js`
   - **Resource type** : JavaScript Module
5. Clique sur **Create**

### Étape 3 : Redémarrer Home Assistant

Redémarre Home Assistant pour charger la nouvelle ressource.

### Étape 4 : Ajouter la carte au Dashboard

**D'abord, trouve le nom exact de tes entités :**

1. Va dans **Developer Tools** → **States**
2. Cherche `device_tracker`
3. Note les noms exacts de tes entités de type "Map"
   - Exemple : `device_tracker.snow_removal_avenue_northcliffe_impair_map_avenue_northcliffe_impair`

#### Via l'interface graphique :

1. Va sur ton Dashboard
2. Clique sur **Edit Dashboard**
3. Clique sur **+ Add Card**
4. Sélectionne **Manual** (carte manuelle)
5. Colle cette configuration en remplaçant les noms d'entités par les tiens :

```yaml
type: custom:montreal-snow-removal-map-card
title: Déneigement Montréal
entities:
  - device_tracker.REMPLACER_PAR_TON_ENTITE_1
  - device_tracker.REMPLACER_PAR_TON_ENTITE_2
zoom: 15
dark_mode: true
```

#### Via YAML (exemple) :

```yaml
type: custom:montreal-snow-removal-map-card
title: Déneigement Montréal
entities:
  - device_tracker.snow_removal_avenue_northcliffe_impair_map_avenue_northcliffe_impair
  - device_tracker.snow_removal_avenue_northcliffe_pair_map_avenue_northcliffe_pair
zoom: 15
dark_mode: true
```

## Configuration

### Options disponibles

| Option | Type | Défaut | Description |
|--------|------|--------|-------------|
| `entities` | list | **requis** | Liste des entités `device_tracker.map_*` |
| `title` | string | "Montreal Snow Removal" | Titre de la carte |
| `zoom` | number | 15 | Niveau de zoom initial |
| `center` | [lat, lon] | auto | Centre de la carte (auto = centre sur les rues) |
| `dark_mode` | boolean | true | Mode sombre de la carte |

### Exemples de configuration

#### Configuration basique :

```yaml
type: custom:montreal-snow-removal-map-card
entities:
  - device_tracker.map_home
```

#### Configuration complète :

```yaml
type: custom:montreal-snow-removal-map-card
title: Mes rues suivies
entities:
  - device_tracker.map_home
  - device_tracker.map_work
  - device_tracker.map_parents
zoom: 14
center: [45.4942, -73.5709]  # NDG, Montreal
dark_mode: false
```

#### Configuration avec auto-centrage :

```yaml
type: custom:montreal-snow-removal-map-card
title: Déneigement en temps réel
entities:
  - device_tracker.map_home
  - device_tracker.map_work
# center non spécifié = auto-centrage sur toutes les rues
zoom: 15
dark_mode: true
```

## Fonctionnalités

### 1. **Segments de rue complets**
Les rues sont affichées comme des lignes continues, pas juste des points.

### 2. **Couleurs dynamiques**
Les couleurs changent automatiquement selon l'état du déneigement.

### 3. **Info-bulles interactives**
Clique sur une rue pour voir :
- Nom de la rue
- Côté (Gauche/Droite)
- État du déneigement
- Dates de début et fin

### 4. **Légende intégrée**
Une légende est affichée en bas à droite pour comprendre les couleurs.

### 5. **Auto-centrage**
La carte se centre automatiquement pour afficher toutes tes rues (si `center` n'est pas spécifié).

## Dépannage

### La carte n'apparaît pas

1. **Vérifier que la ressource est chargée :**
   - Developer Tools → ⚠️ (warnings)
   - Chercher des erreurs liées à `montreal-snow-removal-map-card.js`

2. **Vérifier la console du navigateur :**
   - Appuyer sur F12
   - Aller dans l'onglet "Console"
   - Chercher des erreurs JavaScript

3. **Vérifier le chemin du fichier :**
   - Le fichier doit être dans `config/www/montreal-snow-removal-map-card.js`
   - L'URL de la ressource doit être `/local/montreal-snow-removal-map-card.js`

### Les segments ne s'affichent pas

1. **Vérifier que les coordonnées sont présentes :**
   - Developer Tools → States
   - Chercher `device_tracker.map_*`
   - Vérifier l'attribut `street_coordinates`

2. **Vérifier les logs Home Assistant :**
   - Chercher "GeoJSON loaded"
   - Si absent, le GeoJSON n'a pas été téléchargé

### La carte est vide

1. **Vérifier que tu as des entités configurées :**
   ```yaml
   entities:
     - device_tracker.map_home  # Remplacer par tes vraies entités
   ```

2. **Vérifier que les entités existent :**
   - Settings → Devices & Services → Montreal Snow Removal
   - Chercher les entités `device_tracker.map_*`

### Leaflet library not found

La carte utilise Leaflet qui est normalement inclus dans Home Assistant via l'intégration Map.

**Solution :**
1. Assure-toi que l'intégration "Map" est activée dans Home Assistant
2. Si le problème persiste, tu peux charger Leaflet manuellement :

Ajoute cette ressource en premier :
```
URL: https://unpkg.com/leaflet@1.9.4/dist/leaflet.css
Type: Stylesheet
```

Puis :
```
URL: https://unpkg.com/leaflet@1.9.4/dist/leaflet.js
Type: JavaScript Module
```

## Performances

- **Chargement initial :** < 1 seconde
- **Mise à jour :** Temps réel (quand les entités changent)
- **Nombre de rues :** Optimisé pour 1-10 rues, fonctionne jusqu'à 50+

## Personnalisation avancée

Tu peux modifier le fichier `montreal-snow-removal-map-card.js` pour :
- Changer les couleurs dans `_getColorForState()`
- Modifier l'épaisseur des lignes (`weight: 5`)
- Personnaliser les info-bulles dans `_createPopupContent()`
- Changer le fond de carte dans `tileUrl`

---

**Besoin d'aide ?** Ouvre une issue sur GitHub !
