# Montréal Snow Removal (Planif-Neige)

Track snow removal operations in Montreal using real-time data from the city's Planif-Neige system.

## Features

- **Automatic address search** - Just enter your Montreal address
- **Real-time tracking** - Know when snow removal is scheduled for your street
- **Parking ban alerts** - Get notified when parking is banned
- **Visual map display** - See your streets on a map with color-coded status
- **Custom map card included** - Display complete street segments as colored lines (auto-installed!)
- **Vehicle tracking** 🚗 - Track your car's GPS location and see parking status on the map
- **Multiple addresses** - Track home, work, or any location in Montreal
- **Bilingual** - Full support for French and English

## Quick Setup

1. Install via HACS
2. Add the integration in Home Assistant
3. Enter your Montreal address
4. Done! No API token required

Add the custom map card resource in **Settings** → **Dashboards** → **Resources**:
- URL: `/api/montreal_snow_removal/map-card.js`
- Type: JavaScript Module

Then add the card to your dashboard:

```yaml
type: custom:montreal-snow-removal-map-card
entities:
  - device_tracker.map_home
vehicles:
  - sensor.snow_removal_my_car
```

The map card supports both static addresses and tracked vehicles with GPS markers 🚗.

Data updates every ~20 minutes from the city's public API.

**Important:** Street signage always takes precedence over the integration data.

## Automation Example

Get notified 24 hours before snow removal starts:

```yaml
automation:
  - alias: "Snow Removal Alert"
    trigger:
      - platform: template
        value_template: >
          {{ state_attr('sensor.snow_removal_home', 'heures_avant_debut') | float(0) < 24 }}
    action:
      - service: notify.mobile_app
        data:
          message: "Move your car! Snow removal starts soon."
```
