# Montréal Snow Removal (Planif-Neige) - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/ludodefgh/montreal-snow-removal.svg)](https://github.com/ludodefgh/montreal-snow-removal/releases)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ludodefgh&repository=montreal-snow-removal&category=integration)

A custom Home Assistant integration that tracks snow removal operations in Montreal streets using the official Planif-Neige API from Ville de Montréal.

## Features

- **Real-time tracking** of snow removal status for your streets
- **Visual map display** 🗺️ - See your streets on a map with color-coded markers
- **Parking ban alerts** - know when you can't park on your street
- **Multiple addresses** - track home, work, or any location in Montreal
- **Vehicle tracking** 🚗 - Track your car's location and get parking ban status based on GPS
- **Bilingual support** - Full French and English translations
- **Rich attributes** - Street names, dates, hours until snow removal starts
- **GPS coordinates** - Automatic location mapping for each tracked street

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ludodefgh&repository=montreal-snow-removal&category=integration)

1. Click the button above, or open HACS in Home Assistant
2. Search for "**Montréal Snow Removal**"
3. Click "**Download**"
4. Restart Home Assistant

### Manual Installation

1. Download the latest release from GitHub
2. Copy the `custom_components/montreal_snow_removal` folder to your `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

### Prerequisites

**No API token required!** 🎉

This integration now uses a [public API](https://github.com/ludodefgh/planif-neige-public-api) that provides free access to Montreal's snow removal data without requiring you to request a token from the city.

### Setup via UI

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "**Montréal Snow Removal**"
4. Enter your full Montreal address (e.g., "1234 rue Example")
   - The integration will **automatically search** for your street
   - If multiple matches are found, select the correct street side
   - Alternatively, use **Manual entry (advanced)** to enter COTE_RUE_ID directly
5. Give your address a friendly name (e.g., "Home", "Work")
6. Add more addresses or click **Finish**

That's it! No API token or manual street lookup needed. ✨

### Advanced: Manual COTE_RUE_ID Entry

If automatic search doesn't find your address, you can enter the `COTE_RUE_ID` manually:

1. During setup, check the **Manual entry (advanced)** option
2. Find your COTE_RUE_ID:
   - Visit the [Geobase Double dataset](https://donnees.montreal.ca/dataset/geobase-double)
   - Download the GeoJSON or CSV file
   - Search for your street name and address range
   - Note the `COTE_RUE_ID` value

**Example:**
```
Street: Avenue Adhémar-Mailhiot
Address range: 12323-12335
Side: Right (Droite)
COTE_RUE_ID: 10100011
```

## Entities

For each configured address, the integration creates:

### Sensor: `sensor.snow_removal_[name]`

Tracks the current snow removal state.

**States:**
- `enneige` / `snowed` - Not yet cleared, no planning
- `planifie` / `planned` - Clearing scheduled
- `en_cours` / `in_progress` - Clearing in progress
- `deneige` / `cleared` - Clearing completed
- `replanifie` / `rescheduled` - Rescheduled to new date
- `sera_replanifie` / `will_be_rescheduled` - Will be rescheduled (no date yet)
- `degage` / `clear` - Clear (between operations)

**Attributes:**
- `cote_rue_id` - Street side ID
- `nom_voie` - Street name
- `type_voie` - Street type (rue, avenue, boulevard)
- `adresse_debut` - Starting civic number
- `adresse_fin` - Ending civic number
- `cote` - Side (Gauche/Droite)
- `date_debut_planif` - Planned start date/time
- `date_fin_planif` - Planned end date/time
- `date_debut_replanif` - Rescheduled start (if applicable)
- `date_fin_replanif` - Rescheduled end (if applicable)
- `derniere_mise_a_jour` - Last update timestamp
- `heures_avant_debut` - Hours until clearing starts

### Binary Sensor: `binary_sensor.parking_ban_[name]`

Indicates if parking is currently banned.

**States:**
- `on` - Parking BANNED (move your car!)
- `off` - Parking allowed

**Attributes:**
- `debut_interdiction` - Ban start date/time
- `fin_interdiction` - Ban end date/time

### Device Tracker: `device_tracker.map_[name]` 🗺️

**NEW!** Visual map marker for each tracked street.

Displays your tracked streets on the Home Assistant map with color-coded markers based on snow removal status.

**Marker Colors:**
- 🔴 **Red** - Planned (déneigement planifié)
- 🟡 **Yellow** - In Progress (en cours)
- 🟢 **Green** - Completed (déneigé)
- ⚪ **Gray** - Clear conditions (dégagé)
- 🟠 **Orange** - Rescheduled (replanifié)
- 🔵 **Blue** - Snowy/Not planned (enneigé)

**Note:** Device tracker entities are automatically created when GeoJSON geometry data is successfully loaded. If coordinates are not available for a street, no tracker will be created.

## Vehicle Tracking 🚗

**NEW!** Track your vehicle's location and automatically get snow removal status for wherever it's parked.

### How It Works

The integration can track vehicles using any Home Assistant entity that provides GPS coordinates (device_tracker, sensor with latitude/longitude attributes, or entities with address attributes). When your vehicle moves to a new street, the integration automatically resolves the GPS coordinates to the correct Montreal street segment.

### Setup

1. Go to **Settings** → **Devices & Services**
2. Find "**Montréal Snow Removal**" and click **Configure**
3. Select "**Manage tracked vehicles**"
4. Click "**Add new tracked vehicle**"
5. Enter a name for your vehicle (e.g., "My Car")
6. Select the source entity (device_tracker or sensor with location data)

### Vehicle Entities

For each tracked vehicle, the integration creates:

#### Sensor: `sensor.snow_removal_[vehicle_name]`

Shows the snow removal status at the vehicle's current location.

**States:**
- Same states as address-based sensors (enneige, planifie, en_cours, etc.)
- `outside_coverage` - Vehicle is outside Montreal
- `source_unavailable` - Location source entity is unavailable

**Attributes:**
- `current_street` - Current street name
- `street_side` - Street side (Impair/Pair)
- `source_entity` - The entity providing location data
- `last_resolution` - When the location was last resolved
- `resolution_method` - How the street was determined (gps, address)

#### Binary Sensor: `binary_sensor.parking_[vehicle_name]`

Indicates if parking is banned at the vehicle's current location.

**States:**
- `Banned` / `Interdit` - Parking is prohibited (move your car!)
- `Allowed` / `Permis` - Parking is allowed

#### Sensor: `sensor.next_operation_[vehicle_name]`

Shows time until the next snow removal operation at the vehicle's location.

### Technical Details

- Uses point-to-segment distance calculation for accurate street matching
- Minimum 5m movement threshold to trigger re-resolution
- Maximum 100m distance to match a street segment
- Automatically tracks street changes and updates coordinator

## Visual Map Display 🗺️

The integration can display your tracked streets on a map in **two ways**:

### Option 1: Native Map (Simple Markers)

Display streets as point markers on Home Assistant's native map.

**Setup:**
1. Go to your **Dashboard**
2. Click **Edit Dashboard**
3. Click **+ Add Card**
4. Select **Map** card
5. Add your `device_tracker.map_*` entities

**YAML configuration:**
```yaml
type: map
entities:
  - entity: device_tracker.map_home
  - entity: device_tracker.map_work
default_zoom: 15
hours_to_show: 0
```

### Option 2: Custom Card (Full Street Segments) ⭐ **Recommended**

Display complete street segments as colored lines on the map based on snow removal status!

**Preview:**
- 🔴 Red lines = Planned snow removal
- 🟡 Yellow lines = In progress
- 🟢 Green lines = Completed
- 🟠 Orange lines = Rescheduled
- ⚪ Gray lines = Clear conditions
- 🔵 Blue lines = Snowy/Not planned

**Installation:**

The custom card is **included** with the integration. Add it as a Lovelace resource:

1. Go to **Settings** → **Dashboards** → click menu (3 dots) → **Resources**
2. Click **+ Add Resource**
3. URL: `/api/montreal_snow_removal/map-card.js`
4. Type: **JavaScript Module**
5. Click **Create** and refresh your browser

**Add the card to your dashboard:**

```yaml
type: custom:montreal-snow-removal-map-card
title: Déneigement Montréal
entities:
  - device_tracker.map_home
  - device_tracker.map_work
vehicles:
  - sensor.snow_removal_my_car
zoom: 15
dark_mode: true
show_vehicle_markers: true
show_vehicle_streets: true
```

**Vehicle tracking on the map:**
- 🚗 **Car icon** - Shows your vehicle's current GPS position
- **Street highlighting** - Vehicle's current street displayed as a favorite (thick line)
- Configurable via `show_vehicle_markers` and `show_vehicle_streets` options

### How It Works

On first setup, the integration downloads Montreal's GeoJSON street geometry data (~75 MB) from the [City's Open Data portal](https://donnees.montreal.ca/dataset/geobase-double). This data contains:
- Precise GPS coordinates for every street in Montreal
- Complete street segment geometries (LineString data)

The data is cached locally at `config/montreal_snow_removal/geobase_geometry.json`, so it only needs to be downloaded once.

### Troubleshooting Map Display

**Map markers/segments not appearing:**
- Check Home Assistant logs for GeoJSON download errors
- Verify the integration successfully loaded: Look for "GeoJSON loaded with X geometries" in logs
- If download failed, delete the cache file at `config/montreal_snow_removal/geobase_geometry.json` and restart

**For custom card issues:**
- See detailed troubleshooting in [CUSTOM_CARD_INSTALLATION.md](CUSTOM_CARD_INSTALLATION.md)

## Automation Examples

### Alert 24 hours before snow removal

```yaml
automation:
  - alias: "Snow Removal Alert - 24h"
    trigger:
      - platform: template
        value_template: >
          {{ state_attr('sensor.snow_removal_home', 'heures_avant_debut') | float(0) < 24
             and state_attr('sensor.snow_removal_home', 'heures_avant_debut') | float(0) > 0 }}
    condition:
      - condition: state
        entity_id: sensor.snow_removal_home
        state: "planifie"
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ Snow Removal Planned"
          message: >
            Move your car before {{ state_attr('sensor.snow_removal_home', 'date_debut_planif') }}
```

### Notification when clearing starts

```yaml
automation:
  - alias: "Snow Removal In Progress"
    trigger:
      - platform: state
        entity_id: sensor.snow_removal_home
        to: "en_cours"
    action:
      - service: notify.mobile_app
        data:
          title: "🚜 Snow Removal Started"
          message: "Snow clearing has started on your street"
```

### Parking ban reminder

```yaml
automation:
  - alias: "Parking Ban Active"
    trigger:
      - platform: state
        entity_id: binary_sensor.parking_ban_home
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "🚫 Parking Ban Active"
          message: "You cannot park on your street until {{ state_attr('binary_sensor.parking_ban_home', 'fin_interdiction') }}"
```

### Confirmation when completed

```yaml
automation:
  - alias: "Snow Removal Completed"
    trigger:
      - platform: state
        entity_id: sensor.snow_removal_home
        to: "deneige"
    action:
      - service: notify.mobile_app
        data:
          title: "✅ Snow Removal Complete"
          message: "You can now park on your street again"
```

## Managing Addresses

After installation, you can manage your tracked addresses:

1. Go to **Settings** → **Devices & Services**
2. Find "**Montréal Snow Removal**"
3. Click **Configure**
4. Choose an option:
   - **Configure scan interval** - Adjust update frequency (minimum 300 seconds / 5 minutes)
   - **Manage addresses** - Add or delete tracked addresses
     - **Add new address** - Uses automatic address search (same as initial setup)
     - **Delete** - Remove addresses you no longer want to track

## Important Notes

### Legal Disclaimer

⚠️ **The signage in effect on the streets for parking during snow removal always takes precedence over data transmitted by the API.**

This integration provides information from the City of Montreal's API, but physical signs on streets are the legal authority. Always check street signs before parking.

### API Rate Limits

The Planif-Neige API has a strict limit:
- **Maximum 1 request per 5 minutes**

This integration respects this limit. Don't set update intervals below 5 minutes.

## Troubleshooting

### Integration not loading

1. Check Home Assistant logs: **Settings** → **System** → **Logs**
2. Look for errors related to `montreal_snow_removal`

### No data showing

1. Ensure your address was found correctly during setup
2. Check if there's active snow removal in Montreal (usually November-March)
3. Verify the geobase cache was downloaded successfully

## Data Sources

This integration uses:
- **Planif-Neige API**: Real-time snow removal data
  - Production: `https://servicesenligne2.ville.montreal.qc.ca/api/infoneige/`
  - Test: `https://servicesenlignedev.ville.montreal.qc.ca/api/infoneige/`

- **Geobase Double**: Street name mapping
  - Source: [Données ouvertes Montréal](https://donnees.montreal.ca/dataset/geobase-double)
  - Updated weekly

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

- **Issues**: [GitHub Issues](https://github.com/ludovic/montreal-snow-removal/issues)
- **Discussions**: [GitHub Discussions](https://github.com/ludovic/montreal-snow-removal/discussions)
- **API Questions**: donneesouvertes@montreal.ca

## Changelog

### Version 2.3.4 (Current)

**Bug Fixes:**
- 🐛 Fixed compatibility with recent Home Assistant versions where `LovelaceData` API changed

### Version 2.3.3

**Improvements:**
- ✨ Integration now available in HACS default repository (no manual repo addition needed!)

### Version 2.3.1 🚗🗺️

**Map Card: Vehicle Support**
- ✨ **Vehicle markers on map** - 🚗 icons show vehicle GPS position in real-time
- ✨ **Vehicle street highlighting** - Current street displayed as favorite (thick line with color-coded status)
- ✨ **New config options** - `vehicles`, `show_vehicle_markers`, `show_vehicle_streets`
- ✨ **Visual editor support** - Add vehicles via the card's configuration UI with autocomplete
- ✨ **Legend updated** - Shows tracked vehicle icon in the legend

### Version 2.3.0 🚗

**New Feature: Vehicle Tracking**
- ✨ **Dynamic vehicle tracking** - Track your car using GPS-based device_tracker or sensor entities
- ✨ **Automatic street resolution** - GPS coordinates are resolved to Montreal street segments using point-to-segment distance calculation
- ✨ **Vehicle-specific entities** - Each tracked vehicle gets its own parking ban, status, and next operation sensors
- ✨ **Street side detection** - Detects which side of the street (Impair/Pair) the vehicle is on
- ✨ **Config flow UI** - Easy management of tracked vehicles (add/delete) through the options menu

**Improvements:**
- 🎨 Fixed vehicle parking ban sensor to display "Allowed/Banned" (en) or "Permis/Interdit" (fr) instead of generic "Activated/Deactivated"

### Version 2.2.1 🗺️

**Bug Fixes:**
- 🐛 Fixed translation placeholder quotes for hassfest validation
- 🐛 Added lovelace dependency to manifest.json

### Version 2.2.0

**New Feature: Interactive Map Card**
- ✨ **Neighborhood map visualization** - See your streets on an interactive map
- ✨ **Color-coded street segments** based on snow removal status:
  - 🔴 Red: Snow covered (enneigé)
  - 🟡 Yellow: Planned/Scheduled (planifié)
  - 🟢 Green: Cleared (déneigé)
  - 🔵 Blue: In progress (en cours)
  - ⚫ Gray: Clear/No snow (dégagé)
- ✨ **Collapsible legend** - Maximize map view when needed
- ✨ **Smart street prioritization** - Major streets displayed with thicker lines
- ✨ **HTTP API endpoint** - Card served automatically, no manual file copying

**Usage:**
```yaml
type: custom:montreal-snow-removal-map-card
entity: sensor.your_snow_removal_sensor
```

### Version 2.1.1

**New Features:**
- ✨ **Next Operation sensor** - Shows time until next snow removal operation
  - Displays "En cours" when operation is active (GPS tracking or within scheduled period)
  - Shows countdown in hours/days format (e.g., "2h", "1j 5h")
  - Visible directly in main sensor list for quick status checks
- ✨ **Last Update sensor** - Shows when data was last updated from the city's API
  - Timestamp sensor with proper Montreal timezone
  - Helps you know if the data is current

**Improvements:**
- 🎨 Improved parking ban sensor display
  - Changed from "Problem" device class to custom translated states
  - Renamed from "Parking Ban" to "Parking" for better UX
  - Clearer states: "Interdit"/"Permis" (FR), "Banned"/"Allowed" (EN)

**User Experience:**
- 📊 All critical information now visible in main sensor list
- 🚀 No need to click through multiple screens to check snow removal status
- 🌐 Full bilingual support (EN/FR) for all new features

### Version 2.1.0

**Bug Fixes:**
- 🐛 Fixed address deletion error (TypeError in config flow)
- 🐛 Proper cleanup of entities and devices when deleting addresses
- 🐛 Fixed orphaned entities remaining after address removal

**Improvements:**
- ✨ Added integration icon (snowplow) in HA integrations list
- ✨ Single instance enforcement - prevents duplicate integration entries
- ✨ Updated device manufacturer info to "ludodefgh"
- ✨ Added translations for address deletion confirmation (EN/FR)

### Version 2.0.0

**New Features:**
- ✨ **Automatic address search** - Just enter your address, no need to find COTE_RUE_ID!
- ✨ **Smart street matching** - Handles accents, abbreviations, and multiple results
- ✨ **Address management** - Add/delete addresses through options menu
- ✨ **Manual fallback** - Advanced option to enter COTE_RUE_ID directly

**Major Changes:**
- ✅ **No API token required!** - Now uses public API
- ✅ Simplified configuration - removed token setup step
- ✅ Improved reliability - public API updated every 10 minutes
- ✅ Removed zeep dependency - lighter installation
- ✅ Uses [planif-neige-public-api](https://github.com/ludodefgh/planif-neige-public-api)

**Migration from v1.x:**
- Existing installations will need to be reconfigured (remove and re-add the integration)
- No token needed in v2.0!

### Version 1.0.0
- ✅ SOAP API integration
- ✅ Snow removal status sensors
- ✅ Parking ban binary sensors
- ✅ Config Flow UI
- ✅ French/English support

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **Ville de Montréal** for providing the Planif-Neige API and open data
- **Home Assistant** community for the excellent platform
- All contributors and users

---

**Made with ❄️ in Montréal**
