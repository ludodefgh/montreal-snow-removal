# Custom Map Card - Installation Guide

This custom card displays **complete street segments** (not just points) with colors based on snow removal status.

## Expected Result

Instead of seeing point markers, you'll see **colored street lines** on the map:
- 🔴 **Red** - Red lines for streets with planned snow removal
- 🟡 **Yellow** - Yellow lines for snow removal in progress
- 🟢 **Green** - Green lines for cleared streets
- 🟠 **Orange** - Orange lines for rescheduled streets
- ⚪ **Gray** - Gray lines for clear conditions
- 🔵 **Blue** - Blue lines for snowy streets

## Installation

### Step 1: Add the Resource

The card is **included** with the Montreal Snow Removal integration but you need to register it as a Lovelace resource:

1. Go to **Settings** → **Dashboards**
2. Click the menu (3 dots in the top right) → **Resources**
3. Click **+ Add Resource**
4. Configure:
   - **URL**: `/api/montreal_snow_removal/map-card.js`
   - **Resource type**: JavaScript Module
5. Click **Create**
6. **Refresh your browser** (Ctrl+Shift+R or Cmd+Shift+R)

### Step 2: Add the Card to Dashboard

**First, find the exact name of your entities:**

1. Go to **Developer Tools** → **States**
2. Search for `device_tracker`
3. Note the exact names of your "Map" type entities
   - Example: `device_tracker.snow_removal_avenue_northcliffe_impair_map_avenue_northcliffe_impair`

#### Via the graphical interface:

1. Go to your Dashboard
2. Click **Edit Dashboard**
3. Click **+ Add Card**
4. Select **Manual** (manual card)
5. Paste this configuration, replacing the entity names with yours:

```yaml
type: custom:montreal-snow-removal-map-card
title: Montreal Snow Removal
entities:
  - device_tracker.REPLACE_WITH_YOUR_ENTITY_1
  - device_tracker.REPLACE_WITH_YOUR_ENTITY_2
zoom: 15
dark_mode: true
```

#### Via YAML (example):

```yaml
type: custom:montreal-snow-removal-map-card
title: Montreal Snow Removal
entities:
  - device_tracker.snow_removal_avenue_northcliffe_impair_map_avenue_northcliffe_impair
  - device_tracker.snow_removal_avenue_northcliffe_pair_map_avenue_northcliffe_pair
zoom: 15
dark_mode: true
```

## Configuration

### Available Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `entities` | list | **required** | List of `device_tracker.map_*` entities |
| `title` | string | "Montreal Snow Removal" | Card title |
| `zoom` | number | 15 | Initial zoom level |
| `center` | [lat, lon] | auto | Map center (auto = center on streets) |
| `dark_mode` | boolean | true | Dark mode for the map |

### Configuration Examples

#### Basic configuration:

```yaml
type: custom:montreal-snow-removal-map-card
entities:
  - device_tracker.map_home
```

#### Complete configuration:

```yaml
type: custom:montreal-snow-removal-map-card
title: My Tracked Streets
entities:
  - device_tracker.map_home
  - device_tracker.map_work
  - device_tracker.map_parents
zoom: 14
center: [45.4942, -73.5709]  # NDG, Montreal
dark_mode: false
```

#### Configuration with auto-centering:

```yaml
type: custom:montreal-snow-removal-map-card
title: Real-time Snow Removal
entities:
  - device_tracker.map_home
  - device_tracker.map_work
# center not specified = auto-center on all streets
zoom: 15
dark_mode: true
```

## Features

### 1. **Complete Street Segments**
Streets are displayed as continuous lines, not just points.

### 2. **Dynamic Colors**
Colors change automatically based on snow removal status.

### 3. **Interactive Tooltips**
Click on a street to see:
- Street name
- Side (Left/Right)
- Snow removal status
- Start and end dates

### 4. **Built-in Legend**
A legend is displayed in the bottom right to understand the colors.

### 5. **Auto-centering**
The map automatically centers to display all your streets (if `center` is not specified).

## Troubleshooting

### The card doesn't appear

1. **Check that the resource is loaded:**
   - Developer Tools → ⚠️ (warnings)
   - Look for errors related to `montreal-snow-removal-map-card.js`

2. **Check the browser console:**
   - Press F12
   - Go to the "Console" tab
   - Look for JavaScript errors

3. **Check the resource path:**
   - The resource URL must be `/api/montreal_snow_removal/map-card.js`
   - Check in Settings → Dashboards → Resources

### Segments don't display

1. **Check that coordinates are present:**
   - Developer Tools → States
   - Search for `device_tracker.map_*`
   - Check the `street_coordinates` attribute

2. **Check Home Assistant logs:**
   - Look for "GeoJSON loaded"
   - If absent, the GeoJSON was not downloaded

### The map is empty

1. **Check that you have configured entities:**
   ```yaml
   entities:
     - device_tracker.map_home  # Replace with your actual entities
   ```

2. **Check that the entities exist:**
   - Settings → Devices & Services → Montreal Snow Removal
   - Look for `device_tracker.map_*` entities

### Leaflet library not found

The card uses Leaflet which is normally included in Home Assistant via the Map integration.

**Solution:**
1. Make sure the "Map" integration is enabled in Home Assistant
2. If the problem persists, you can load Leaflet manually:

Add this resource first:
```
URL: https://unpkg.com/leaflet@1.9.4/dist/leaflet.css
Type: Stylesheet
```

Then:
```
URL: https://unpkg.com/leaflet@1.9.4/dist/leaflet.js
Type: JavaScript Module
```

## Performance

- **Initial load:** < 1 second
- **Updates:** Real-time (when entities change)
- **Number of streets:** Optimized for 1-10 streets, works up to 50+

## Advanced Customization

You can modify the `montreal-snow-removal-map-card.js` file to:
- Change colors in `_getColorForState()`
- Modify line thickness (`weight: 5`)
- Customize tooltips in `_createPopupContent()`
- Change the map background in `tileUrl`

---

**Need help?** Open an issue on GitHub!
