# Montréal Snow Removal (Planif-Neige) - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/ludovic/montreal-snow-removal.svg)](https://github.com/ludovic/montreal-snow-removal/releases)

A custom Home Assistant integration that tracks snow removal operations in Montreal streets using the official Planif-Neige API from Ville de Montréal.

## Features

- **Real-time tracking** of snow removal status for your streets
- **Parking ban alerts** - know when you can't park on your street
- **Multiple addresses** - track home, work, or any location in Montreal
- **Bilingual support** - Full French and English translations
- **Automatic updates** - Respects API rate limits (5 min minimum)
- **Rich attributes** - Street names, dates, hours until snow removal starts

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/ludovic/montreal-snow-removal`
6. Select category: "Integration"
7. Click "Add"
8. Find "Montréal Snow Removal" in HACS and click "Install"
9. Restart Home Assistant

### Manual Installation

1. Download the latest release from GitHub
2. Copy the `custom_components/montreal_snow_removal` folder to your `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

### Prerequisites

You need an API token from Ville de Montréal:
- Email: donneesouvertes@montreal.ca
- Request access to the Planif-Neige API
- You'll receive a token in the format: `aaaaa-bbbbb-ccccc-ddddd`

### Finding Your COTE_RUE_ID

To track a specific address, you need its `COTE_RUE_ID` (street side identifier):

1. Visit the [Geobase Double dataset](https://donnees.montreal.ca/dataset/geobase-double)
2. Download the GeoJSON or CSV file
3. Search for your street name and address range
4. Note the `COTE_RUE_ID` value

**Example:**
```
Street: Avenue Adhémar-Mailhiot
Address range: 12323-12335
Side: Right (Droite)
COTE_RUE_ID: 10100011
```

### Setup via UI

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "**Montréal Snow Removal**"
4. Enter your **API token**
5. Choose **Production API** (or uncheck for testing)
6. Click **Submit**
7. Add addresses:
   - **Name**: Friendly name (e.g., "Home", "Work")
   - **Address**: Full address (optional, for reference)
   - **COTE_RUE_ID**: Street side identifier (required)
8. Add more addresses or click **Finish**

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

## Options

After installation, you can configure:

1. Go to **Settings** → **Devices & Services**
2. Find "**Montréal Snow Removal**"
3. Click **Configure**
4. Adjust:
   - **Update interval** (minimum 300 seconds / 5 minutes)

## Important Notes

### Legal Disclaimer

⚠️ **The signage in effect on the streets for parking during snow removal always takes precedence over data transmitted by the API.**

This integration provides information from the City of Montreal's API, but physical signs on streets are the legal authority. Always check street signs before parking.

### API Rate Limits

The Planif-Neige API has a strict limit:
- **Maximum 1 request per 5 minutes**

This integration respects this limit. Don't set update intervals below 5 minutes.

### Security

- Never commit your API token to version control
- Store your token securely in Home Assistant's configuration
- Use Home Assistant secrets if needed

## Troubleshooting

### Integration not loading

1. Check Home Assistant logs: **Settings** → **System** → **Logs**
2. Look for errors related to `montreal_snow_removal`
3. Verify your API token is valid

### No data showing

1. Ensure your `COTE_RUE_ID` is correct
2. Check if there's active snow removal in Montreal
3. Verify the geobase cache was downloaded successfully

### Authentication errors

1. Verify your API token with the City of Montreal
2. Try switching between Production and Test APIs
3. Request a new token if needed

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

## Roadmap

### Version 1.0 (Current)
- ✅ SOAP API integration
- ✅ Snow removal status sensors
- ✅ Parking ban binary sensors
- ✅ Config Flow UI
- ✅ French/English support

### Future Versions
- 🔲 Automatic geocoding from addresses
- 🔲 Visual map of streets being cleared
- 🔲 Integration with free parking during snow removal
- 🔲 Snow removal history tracking
- 🔲 Predictive ML for probable dates

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **Ville de Montréal** for providing the Planif-Neige API and open data
- **Home Assistant** community for the excellent platform
- All contributors and users

---

**Made with ❄️ in Montréal**
