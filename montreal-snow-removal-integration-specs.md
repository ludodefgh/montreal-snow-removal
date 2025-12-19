# Intégration Home Assistant - Déneigement Montréal (Planif-Neige)

## Vue d'ensemble du projet

Créer une **Custom Integration Home Assistant** (via HACS) qui permet de suivre en temps réel l'état du chargement de neige dans les rues de Montréal.

---

## 1. Architecture de l'intégration

### Type d'intégration
**Custom Integration (HACS)** - PAS un Addon

**Pourquoi Custom Integration ?**
- ✅ S'intègre directement dans Home Assistant
- ✅ Crée des entités (sensors) utilisables dans les automatisations
- ✅ Compatible avec toutes les installations HA (Core, Container, OS)
- ✅ Plus léger et facile à maintenir
- ✅ Distribution via HACS

**Pourquoi PAS un Addon ?**
- ❌ Addons = applications séparées dans containers Docker
- ❌ Seulement pour HA OS et HA Supervised
- ❌ Overkill pour une simple intégration API

### Structure des fichiers

```
custom_components/
└── montreal_snow_removal/
    ├── __init__.py              # Point d'entrée de l'intégration
    ├── manifest.json            # Métadonnées de l'intégration
    ├── config_flow.py           # Configuration UI (Config Flow)
    ├── coordinator.py           # DataUpdateCoordinator (gestion polling)
    ├── const.py                 # Constantes (URLs, intervalles, etc.)
    ├── sensor.py                # Définition des capteurs HA
    ├── binary_sensor.py         # Capteurs binaires (optionnel)
    ├── api/
    │   ├── __init__.py
    │   ├── planif_neige.py      # Client SOAP pour l'API Planif-Neige
    │   └── geobase.py           # Gestion du mapping COTE_RUE_ID -> noms
    ├── data/
    │   └── geobase_map.json     # Cache local du mapping (généré au setup)
    ├── strings.json             # Traductions FR/EN
    └── translations/
        ├── en.json
        └── fr.json
```

---

## 2. API Planif-Neige - Spécifications

### Endpoints

#### Production
```
URL: https://servicesenligne2.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService
```

#### Test/Acceptation
```
URL: https://servicesenlignedev.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService
```

### Authentification
- **Type**: SOAP/XML avec token
- **Token**: Obtenu par email à `donneesouvertes@montreal.ca`
- **Format du token**: `aaaaa-bbbbb-ccccc-ddddd` (UUID style)

### Rate Limiting
⚠️ **IMPORTANT**: Maximum **1 requête par 5 minutes**

### Méthode API

**GetPlanificationsForDate**

**Paramètres**:
- `fromDate` (ISO 8601): Date depuis laquelle récupérer les modifications (AAAA-MM-JJTHH:MI:SS)
- `tokenString`: Jeton d'authentification

**Exemple de requête SOAP**:

```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
xmlns:ser="https://servicesenlignedev.ville.montreal.qc.ca">
  <soapenv:Header/>
  <soapenv:Body>
    <ser:GetPlanificationsForDate>
      <getPlanificationsForDate>
        <fromDate>2024-12-18T08:00:00</fromDate>
        <tokenString>aaaaa-bbbbb-ccccc-ddddd</tokenString>
      </getPlanificationsForDate>
    </ser:GetPlanificationsForDate>
  </soapenv:Body>
</soapenv:Envelope>
```

### Structure de la réponse

**Champs retournés pour chaque côté de rue**:

| Champ | Type | Description | Exemple |
|-------|------|-------------|---------|
| `MUNID` | String | ID Ville de Montréal (toujours "66023") | "66023" |
| `COTE_RUE_ID` | Integer | Identifiant unique du côté de rue | 10100011 |
| `ETAT_DENEIG` | Integer | État actuel du déneigement | 2 (Planifié) |
| `DATE_DEB_PLANIF` | ISO 8601 | Début période planifiée | "2024-03-02T07:00:00" |
| `DATE_FIN_PLANIF` | ISO 8601 | Fin période planifiée | "2024-03-02T19:00:00" |
| `DATE_DEB_REPLANIF` | ISO 8601 | Début replanification (si applicable) | "2024-03-03T07:00:00" ou NULL |
| `DATE_FIN_REPLANIF` | ISO 8601 | Fin replanification (si applicable) | "2024-03-03T19:00:00" ou NULL |
| `DATE_MAJ` | ISO 8601 | Date de dernière mise à jour | "2024-03-01T15:00:00" |

### États de déneigement (`ETAT_DENEIG`)

| Code | État | Description |
|------|------|-------------|
| 0 | Enneigé | Pas encore déneigé, pas de planification |
| 1 | Déneigé | Chargement complété |
| 2 | Planifié | Chargement planifié avec dates |
| 3 | Replanifié | Reporté à une nouvelle date |
| 4 | Sera replanifié ultérieurement | Reporté sans date précise |
| 5 | Chargement en cours | Opération en cours (GPS souffleuses) |
| 10 | Dégagé | Entre deux chargements de neige |

### Codes d'erreur API

| Code | Message | Action |
|------|---------|--------|
| 0 | OK | Succès |
| 1 | Accès invalide | Vérifier paramètres |
| 2 | Accès refusé | Vérifier token |
| 8 | Aucune données pour la plage demandée | Normal (aucune modification) |
| 9 | Date invalide | Vérifier format ISO 8601 |
| 14 | Délais minimum entre accès non respecté | Attendre 5 minutes |

---

## 3. Géobase - Mapping COTE_RUE_ID vers noms de rues

### Source des données

**Géobase Double - Côtés de rue du réseau routier**

URL: https://donnees.montreal.ca/dataset/geobase-double

### Formats disponibles

- **GeoJSON** (recommandé pour parsing facile)
- **CSV** (plus léger)
- **Shapefile** (pour analyse géospatiale)

### Structure des données Géobase

```json
{
  "type": "Feature",
  "geometry": {
    "type": "LineString",
    "coordinates": [[-73.74188, 45.51968], ...]
  },
  "properties": {
    "COTE_RUE_ID": 10100011,
    "ID_TRC": 1010001,
    "ID_VOIE": 300191,
    "NOM_VOIE": "Adhémar-Mailhiot",
    "NOM_VILLE": "MTL",
    "DEBUT_ADRESSE": 12323,
    "FIN_ADRESSE": 12335,
    "COTE": "Droite",
    "TYPE_F": "avenue",
    "SENS_CIR": 0
  }
}
```

### Champs importants

| Champ | Description | Exemple |
|-------|-------------|---------|
| `COTE_RUE_ID` | **CLÉ PRIMAIRE** - ID unique du côté de rue | 10100011 |
| `NOM_VOIE` | Nom de la rue (sans type) | "Adhémar-Mailhiot" |
| `TYPE_F` | Type de voie | "avenue", "rue", "boulevard" |
| `DEBUT_ADRESSE` | Numéro civique début | 12323 |
| `FIN_ADRESSE` | Numéro civique fin | 12335 |
| `COTE` | Côté de la rue | "Gauche" ou "Droite" |
| `NOM_VILLE` | Arrondissement/Ville | "MTL", "AHU", "VER", etc. |

### API CKAN (alternative au téléchargement)

```python
# Endpoint API CKAN
https://data.montreal.ca/api/3/action/datastore_search?resource_id=2f1717e9-0141-48ef-8943-ea348373667f&limit=5000

# Permet de récupérer les données par paginated API calls au lieu de télécharger tout le fichier
```

### Stratégie de mise en cache

1. **Setup initial**: Télécharger la géobase complète et créer un mapping JSON local
2. **Mise à jour**: Vérifier hebdomadairement les modifications (géobase mise à jour chaque semaine)
3. **Fallback**: Si COTE_RUE_ID inconnu, afficher l'ID en attendant la prochaine mise à jour

---

## 4. Configuration de l'intégration

### Config Flow (UI)

L'utilisateur doit pouvoir configurer:

1. **Token API** (requis)
   - Champ texte pour le token UUID
   - Validation lors de la configuration

2. **Adresses à surveiller** (requis)
   - Interface pour ajouter plusieurs adresses
   - Format: "123 rue Example, Montréal" ou "456 avenue Test"
   - Géocodage automatique vers COTE_RUE_ID

3. **Options avancées** (optionnel)
   - Intervalle de polling (min 5 minutes, défaut 10 minutes)
   - Activer/désactiver les notifications push
   - Langue (FR/EN)

### Exemple configuration YAML (ancien style, pour référence)

```yaml
montreal_snow_removal:
  api_token: "aaaaa-bbbbb-ccccc-ddddd"
  scan_interval: 600  # 10 minutes
  addresses:
    - address: "123 rue Example"
      name: "Maison"
    - address: "456 avenue Test"
      name: "Travail"
```

---

## 5. Entités Home Assistant

### Sensors principaux

Pour chaque adresse configurée, créer:

#### Sensor: État du déneigement

```yaml
sensor.snow_removal_maison:
  state: "planifie"  # enneige, planifie, en_cours, deneige, replanifie, sera_replanifie, degage
  attributes:
    friendly_name: "Déneigement - 123 rue Example"
    cote_rue_id: 10100011
    nom_voie: "Example"
    type_voie: "rue"
    adresse_debut: 121
    adresse_fin: 145
    cote: "Gauche"
    date_debut_planif: "2024-03-02T07:00:00"
    date_fin_planif: "2024-03-02T19:00:00"
    date_debut_replanif: null
    date_fin_replanif: null
    derniere_mise_a_jour: "2024-03-01T15:00:00"
    heures_avant_debut: 18  # Calculé
    icon: "mdi:snowflake-alert"
    device_class: "enum"
```

#### Binary Sensor: Interdiction de stationnement

```yaml
binary_sensor.parking_ban_maison:
  state: "off"  # off = Parking OK, on = Parking INTERDIT
  attributes:
    friendly_name: "Interdiction stationnement - 123 rue Example"
    debut_interdiction: "2024-03-02T07:00:00"
    fin_interdiction: "2024-03-02T19:00:00"
    icon: "mdi:car-off"
    device_class: "problem"
```

### Device Class et icônes

| État | Icône | Couleur suggérée |
|------|-------|------------------|
| Enneigé | `mdi:snowflake` | Blanc |
| Planifié | `mdi:snowflake-alert` | Orange |
| En cours | `mdi:snowplow` | Jaune |
| Déneigé | `mdi:check-circle` | Vert |
| Replanifié | `mdi:calendar-refresh` | Orange |
| Dégagé | `mdi:snowflake-off` | Gris |

---

## 6. Notifications et Automatisations

### Exemples d'automatisations possibles

#### 1. Alerte 24h avant le chargement

```yaml
automation:
  - alias: "Alerte déneigement 24h"
    trigger:
      - platform: template
        value_template: "{{ state_attr('sensor.snow_removal_maison', 'heures_avant_debut') | int < 24 }}"
    condition:
      - condition: state
        entity_id: sensor.snow_removal_maison
        state: "planifie"
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ Déneigement planifié"
          message: "Déplacer votre voiture avant {{ state_attr('sensor.snow_removal_maison', 'date_debut_planif') }}"
```

#### 2. Notification quand chargement commence

```yaml
automation:
  - alias: "Déneigement en cours"
    trigger:
      - platform: state
        entity_id: sensor.snow_removal_maison
        to: "en_cours"
    action:
      - service: notify.mobile_app
        data:
          title: "🚜 Chargement de neige en cours"
          message: "Le déneigement a commencé sur votre rue"
```

#### 3. Confirmation quand déneigement terminé

```yaml
automation:
  - alias: "Déneigement complété"
    trigger:
      - platform: state
        entity_id: sensor.snow_removal_maison
        to: "deneige"
    action:
      - service: notify.mobile_app
        data:
          title: "✅ Déneigement terminé"
          message: "Vous pouvez maintenant stationner sur votre rue"
```

---

## 7. Implémentation technique

### manifest.json

```json
{
  "domain": "montreal_snow_removal",
  "name": "Montréal Snow Removal (Planif-Neige)",
  "codeowners": ["@votre-username"],
  "config_flow": true,
  "dependencies": [],
  "documentation": "https://github.com/votre-username/montreal-snow-removal",
  "iot_class": "cloud_polling",
  "issue_tracker": "https://github.com/votre-username/montreal-snow-removal/issues",
  "requirements": ["zeep>=4.2.1"],
  "version": "1.0.0"
}
```

### Dépendances Python

```python
# requirements.txt ou dans manifest.json
zeep>=4.2.1  # Client SOAP/WSDL pour Python
```

### Structure du client API (api/planif_neige.py)

```python
from zeep import Client
from zeep.transports import Transport
from requests import Session
from datetime import datetime
import logging

_LOGGER = logging.getLogger(__name__)

class PlanifNeigeClient:
    """Client pour l'API Planif-Neige de Montréal."""
    
    def __init__(self, api_token: str, production: bool = True):
        """Initialize the API client."""
        self.api_token = api_token
        
        if production:
            self.wsdl_url = "https://servicesenligne2.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService?wsdl"
        else:
            self.wsdl_url = "https://servicesenlignedev.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService?wsdl"
        
        session = Session()
        transport = Transport(session=session)
        self.client = Client(wsdl=self.wsdl_url, transport=transport)
    
    async def get_planifications(self, from_date: datetime) -> dict:
        """
        Récupère les planifications de déneigement depuis une date.
        
        Args:
            from_date: Date depuis laquelle récupérer les modifications
            
        Returns:
            dict: Réponse de l'API avec les planifications
        """
        from_date_str = from_date.strftime("%Y-%m-%dT%H:%M:%S")
        
        try:
            response = self.client.service.GetPlanificationsForDate(
                fromDate=from_date_str,
                tokenString=self.api_token
            )
            return self._parse_response(response)
        except Exception as err:
            _LOGGER.error(f"Erreur lors de l'appel API: {err}")
            raise
    
    def _parse_response(self, response):
        """Parse la réponse XML de l'API."""
        # Implémenter le parsing de la réponse XML
        # Retourner un dict avec code de retour et données
        pass
```

### DataUpdateCoordinator (coordinator.py)

```python
from datetime import timedelta
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.core import HomeAssistant
import logging

_LOGGER = logging.getLogger(__name__)

class SnowRemovalCoordinator(DataUpdateCoordinator):
    """Coordinator pour gérer les mises à jour des données."""
    
    def __init__(self, hass: HomeAssistant, api_client, update_interval: int = 600):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Montreal Snow Removal",
            update_interval=timedelta(seconds=max(update_interval, 300)),  # Min 5 minutes
        )
        self.api_client = api_client
        self.last_update = None
    
    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            # Récupérer les données depuis la dernière mise à jour
            from_date = self.last_update or datetime.now() - timedelta(days=7)
            data = await self.api_client.get_planifications(from_date)
            self.last_update = datetime.now()
            return data
        except Exception as err:
            raise UpdateFailed(f"Erreur lors de la mise à jour: {err}")
```

---

## 8. Tests et Validation

### Tests à implémenter

1. **Test de connexion API**
   - Valider le token
   - Gérer les erreurs d'authentification
   
2. **Test de parsing**
   - Parser correctement les réponses XML
   - Gérer les cas limites (NULL values, dates manquantes)

3. **Test du rate limiting**
   - Respecter le délai de 5 minutes
   - File d'attente si nécessaire

4. **Test du mapping géobase**
   - Vérifier que les COTE_RUE_ID sont trouvés
   - Gérer les IDs inconnus gracefully

### Environnement de test

Utiliser l'environnement d'acceptation:
```
https://servicesenlignedev.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService
```

---

## 9. Distribution et Installation

### Via HACS (Home Assistant Community Store)

1. Créer un repo GitHub: `montreal-snow-removal`
2. Structure:
```
montreal-snow-removal/
├── custom_components/
│   └── montreal_snow_removal/
│       └── [tous les fichiers de l'intégration]
├── README.md
├── hacs.json
└── .github/
    └── workflows/
        └── validate.yml  # CI/CD pour validation
```

3. **hacs.json**:
```json
{
  "name": "Montréal Snow Removal",
  "content_in_root": false,
  "filename": "montreal_snow_removal",
  "render_readme": true,
  "homeassistant": "2024.1.0"
}
```

### Installation manuelle

```bash
# Copier le dossier dans custom_components
cd /config
mkdir -p custom_components
cd custom_components
git clone https://github.com/votre-username/montreal-snow-removal.git
mv montreal-snow-removal/custom_components/montreal_snow_removal .
rm -rf montreal-snow-removal

# Redémarrer Home Assistant
```

---

## 10. Roadmap et fonctionnalités futures

### Version 1.0 (MVP)
- ✅ Connexion à l'API Planif-Neige
- ✅ Sensors pour état de déneigement
- ✅ Binary sensors pour interdiction stationnement
- ✅ Config Flow UI
- ✅ Support FR/EN

### Version 1.1
- 🔲 Intégration avec Google Maps pour géocodage automatique
- 🔲 Carte visuelle montrant les rues en déneigement
- 🔲 Support pour plusieurs adresses (illimité)

### Version 1.2
- 🔲 Notifications push intégrées
- 🔲 Intégration avec les stationnements gratuits pendant déneigement
- 🔲 Historique des opérations de déneigement

### Version 2.0
- 🔲 Support pour d'autres villes du Québec (si API disponibles)
- 🔲 Machine Learning pour prédire les dates probables
- 🔲 Intégration météo pour anticiper les chargements

---

## 11. Ressources et liens utiles

### Documentation API
- Spécifications API Planif-Neige (PDF fourni)
- https://donnees.montreal.ca/dataset/deneigement

### Données ouvertes Montréal
- Géobase Double: https://donnees.montreal.ca/dataset/geobase-double
- Secteurs déneigement: https://donnees.montreal.ca/dataset/secteur-deneigement
- Stationnements gratuits: https://donnees.montreal.ca/dataset/stationnements-deneigement

### Documentation Home Assistant
- Integration Quality Scale: https://developers.home-assistant.io/docs/integration_quality_scale_index
- Config Flow: https://developers.home-assistant.io/docs/config_entries_config_flow_handler
- DataUpdateCoordinator: https://developers.home-assistant.io/docs/integration_fetching_data

### Outils Python
- Zeep (SOAP client): https://docs.python-zeep.org/
- Home Assistant development: https://developers.home-assistant.io/

### Contact
- Token API: donneesouvertes@montreal.ca
- Support données ouvertes: https://donnees.montreal.ca/nous-joindre

---

## Notes importantes

### ⚠️ Avertissement légal

Comme indiqué dans les spécifications de l'API:

> *La signalisation en vigueur dans les rues pour le stationnement en période de chargement de la neige prévaut toujours sur les données transmises par l'API.*

Ajouter ce disclaimer dans la documentation et l'interface utilisateur.

### 🔒 Sécurité

- Ne JAMAIS committer le token API dans le code
- Stocker le token de manière sécurisée dans la configuration HA
- Utiliser les secrets HA si nécessaire

### 📊 Performance

- Respecter strictement le rate limit de 5 minutes
- Optimiser le mapping géobase (index par COTE_RUE_ID)
- Mettre en cache les données entre les polling

### 🌐 Internationalisation

- Toutes les chaînes doivent être dans strings.json/translations
- Support FR et EN obligatoire
- États des sensors en minuscules avec underscores (pour compatibilité)

---

## Checklist de développement

- [ ] Obtenir le token API auprès de la Ville de Montréal
- [ ] Télécharger la géobase double et créer le mapping
- [ ] Implémenter le client SOAP (zeep)
- [ ] Créer le DataUpdateCoordinator
- [ ] Implémenter le Config Flow
- [ ] Créer les sensors et binary_sensors
- [ ] Ajouter les traductions FR/EN
- [ ] Écrire les tests unitaires
- [ ] Tester en environnement de dev (acceptation)
- [ ] Documentation README.md
- [ ] Publier sur GitHub
- [ ] Soumettre à HACS
- [ ] Tester en production

---

**Bon développement avec Claude Code ! 🚀**

N'hésite pas à me consulter si tu as des questions durant l'implémentation.
