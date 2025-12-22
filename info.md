# Montréal Snow Removal (Planif-Neige)

Track snow removal operations in Montreal using real-time data from the city's Planif-Neige system.

## Features

- **Automatic address search** - Just enter your Montreal address
- **Real-time tracking** - Know when snow removal is scheduled for your street
- **Parking ban alerts** - Get notified when parking is banned
- **Multiple addresses** - Track home, work, or any location in Montreal
- **Bilingual** - Full support for French and English

## Quick Setup

1. Install via HACS
2. Add the integration in Home Assistant
3. Enter your Montreal address
4. Done! No API token required

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
