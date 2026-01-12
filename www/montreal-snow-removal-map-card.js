/**
 * Montreal Snow Removal Map Card
 *
 * Custom Lovelace card that displays snow removal streets as colored line segments
 * on a map based on their snow removal status.
 *
 * Installation:
 * 1. Copy this file to: config/www/montreal-snow-removal-map-card.js
 * 2. Add to resources in Lovelace:
 *    - URL: /local/montreal-snow-removal-map-card.js
 *    - Type: JavaScript Module
 * 3. Add card to dashboard with type: custom:montreal-snow-removal-map-card
 */

class MontrealSnowRemovalMapCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._hass = null;
    this._map = null;
    this._layers = new Map();
    this._hasAutoFitted = false;
  }

  setConfig(config) {
    if (!config.entities || !Array.isArray(config.entities)) {
      throw new Error('You need to define entities');
    }
    this._config = {
      title: config.title || 'Montreal Snow Removal',
      entities: config.entities,
      zoom: config.zoom || 15,
      center: config.center || null,
      dark_mode: config.dark_mode !== false,
    };
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._map && !this._initializing) {
      this._initializing = true;
      this._initMap().then(() => {
        this._initializing = false;
        this._updateMap();
      });
    } else if (this._map) {
      this._updateMap();
    }
  }

  async _loadLeaflet() {
    return new Promise((resolve, reject) => {
      // Check if already loading
      if (document.querySelector('script[src*="leaflet.js"]')) {
        console.log('Leaflet script already in document, waiting...');
        // Wait a bit and check again
        setTimeout(() => {
          if (typeof L !== 'undefined') {
            resolve();
          } else {
            reject(new Error('Leaflet script present but not loaded'));
          }
        }, 1000);
        return;
      }

      const script = document.createElement('script');
      script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      script.onload = () => {
        console.log('Leaflet loaded successfully');
        resolve();
      };
      script.onerror = (error) => {
        console.error('Failed to load Leaflet', error);
        reject(new Error('Failed to load Leaflet library'));
      };
      document.head.appendChild(script);
    });
  }

  async _initMap() {
    try {
      // Load Leaflet if not available
      if (typeof L === 'undefined') {
        console.log('Loading Leaflet library...');
        await this._loadLeaflet();
      }

      // Check again after loading attempt
      if (typeof L === 'undefined') {
        throw new Error('Leaflet library still not available after load attempt');
      }
    } catch (error) {
      console.error('Failed to initialize map:', error);
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            <p style="color: red;">Error: Failed to load Leaflet library.</p>
            <p style="font-size: 12px;">Check your internet connection or browser console for details.</p>
          </div>
        </ha-card>
      `;
      return;
    }

    // Create card structure with Leaflet CSS embedded
    this.shadowRoot.innerHTML = `
      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
      <style>
        :host {
          display: block;
        }
        ha-card {
          overflow: hidden;
        }
        .card-header {
          padding: 16px;
          font-size: 16px;
          font-weight: 500;
        }
        #map {
          width: 100%;
          height: 400px;
          position: relative;
        }
        .legend {
          position: absolute;
          bottom: 30px;
          right: 10px;
          background: ${this._config.dark_mode ? 'rgba(50, 50, 50, 0.95)' : 'rgba(255, 255, 255, 0.95)'};
          color: ${this._config.dark_mode ? '#ffffff' : '#000000'};
          padding: 10px;
          border-radius: 4px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
          z-index: 1000;
          font-size: 12px;
        }
        .legend-item {
          display: flex;
          align-items: center;
          margin: 4px 0;
        }
        .legend-color {
          width: 20px;
          height: 3px;
          margin-right: 8px;
        }
        /* Fix Leaflet in Shadow DOM */
        .leaflet-pane,
        .leaflet-tile,
        .leaflet-marker-icon,
        .leaflet-marker-shadow,
        .leaflet-tile-container,
        .leaflet-pane > svg,
        .leaflet-pane > canvas,
        .leaflet-zoom-box,
        .leaflet-image-layer,
        .leaflet-layer {
          position: absolute;
          left: 0;
          top: 0;
        }
        .leaflet-container {
          overflow: hidden;
        }
        .leaflet-tile,
        .leaflet-image-layer {
          max-width: none !important;
          max-height: none !important;
        }
      </style>
      <ha-card>
        ${this._config.title ? `<div class="card-header">${this._config.title}</div>` : ''}
        <div id="map"></div>
        <div class="legend">
          <div class="legend-item">
            <div class="legend-color" style="background-color: red;"></div>
            <span>Planifié</span>
          </div>
          <div class="legend-item">
            <div class="legend-color" style="background-color: yellow;"></div>
            <span>En cours</span>
          </div>
          <div class="legend-item">
            <div class="legend-color" style="background-color: green;"></div>
            <span>Terminé</span>
          </div>
          <div class="legend-item">
            <div class="legend-color" style="background-color: orange;"></div>
            <span>Replanifié</span>
          </div>
          <div class="legend-item">
            <div class="legend-color" style="background-color: gray;"></div>
            <span>Dégagé</span>
          </div>
          <div class="legend-item">
            <div class="legend-color" style="background-color: blue;"></div>
            <span>Enneigé</span>
          </div>
        </div>
      </ha-card>
    `;

    // Wait for the map element to be properly sized
    const mapElement = this.shadowRoot.getElementById('map');

    // Use requestAnimationFrame to ensure DOM is ready
    await new Promise(resolve => requestAnimationFrame(resolve));

    // Initialize Leaflet map
    this._map = L.map(mapElement, {
      zoomControl: true,
    });

    // Add OpenStreetMap tiles
    const tileUrl = this._config.dark_mode
      ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
      : 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';

    L.tileLayer(tileUrl, {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(this._map);

    // Set initial view
    if (this._config.center && this._config.center.length === 2) {
      this._map.setView(this._config.center, this._config.zoom);
    } else {
      // Default to Montreal
      this._map.setView([45.5017, -73.5673], this._config.zoom);
    }

    // Fix rendering issues - multiple attempts to ensure proper sizing
    const invalidateMapSize = () => {
      if (this._map) {
        this._map.invalidateSize();
      }
    };

    // Try multiple times with increasing delays
    setTimeout(invalidateMapSize, 100);
    setTimeout(invalidateMapSize, 300);
    setTimeout(invalidateMapSize, 500);

    // Setup a ResizeObserver to handle dynamic resizing
    // Use debouncing to avoid interfering with user interaction
    if (typeof ResizeObserver !== 'undefined') {
      let resizeTimeout;
      const resizeObserver = new ResizeObserver(() => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
          invalidateMapSize();
        }, 200);
      });
      resizeObserver.observe(mapElement);
    }
  }

  _updateMap() {
    if (!this._map || !this._hass) {
      console.log('Map or hass not ready');
      return;
    }

    const entities = this._config.entities;
    const bounds = [];

    console.log(`Updating map with ${entities.length} entities`);

    entities.forEach(entityId => {
      const entity = this._hass.states[entityId];
      if (!entity) {
        console.warn(`Entity not found: ${entityId}`);
        return;
      }

      const attributes = entity.attributes;
      const coordinates = attributes.street_coordinates;

      console.log(`Entity ${entityId}:`, {
        hasCoordinates: !!coordinates,
        coordinateCount: coordinates ? coordinates.length : 0,
        state: attributes.snow_removal_state,
        color: attributes.marker_color
      });

      if (!coordinates || coordinates.length === 0) {
        console.warn(`No coordinates for entity: ${entityId}`);
        return;
      }

      // Get color based on state
      const color = this._getColorForState(attributes.marker_color || attributes.snow_removal_state);

      // Remove existing layer if present
      if (this._layers.has(entityId)) {
        this._map.removeLayer(this._layers.get(entityId));
      }

      // Create polyline for street segment
      const polyline = L.polyline(coordinates, {
        color: color,
        weight: 5,
        opacity: 0.8,
      });

      // Add popup with street info
      const popupContent = this._createPopupContent(attributes);
      polyline.bindPopup(popupContent);

      // Add to map
      polyline.addTo(this._map);
      this._layers.set(entityId, polyline);

      // Add to bounds
      coordinates.forEach(coord => bounds.push(coord));
    });

    // Auto-fit map to show all streets only on first load
    if (bounds.length > 0 && !this._config.center && !this._hasAutoFitted) {
      this._map.fitBounds(bounds, { padding: [50, 50] });
      this._hasAutoFitted = true;
    }
  }

  _getColorForState(state) {
    const colorMap = {
      'red': '#FF0000',
      'yellow': '#FFD700',
      'green': '#00AA00',
      'orange': '#FF8C00',
      'gray': '#808080',
      'blue': '#0066CC',
      'planifie': '#FF0000',
      'en_cours': '#FFD700',
      'deneige': '#00AA00',
      'replanifie': '#FF8C00',
      'degage': '#808080',
      'enneige': '#0066CC',
    };
    return colorMap[state] || '#0066CC';
  }

  _createPopupContent(attributes) {
    const streetName = attributes.street_name || 'Unknown';
    const streetSide = attributes.street_side || '';
    const state = attributes.snow_removal_state || 'unknown';
    const startTime = attributes.start_time || '';
    const endTime = attributes.end_time || '';

    let content = `<strong>${streetName}</strong>`;
    if (streetSide) {
      content += `<br>Côté: ${streetSide}`;
    }
    content += `<br>État: ${this._formatState(state)}`;
    if (startTime) {
      content += `<br>Début: ${this._formatDateTime(startTime)}`;
    }
    if (endTime) {
      content += `<br>Fin: ${this._formatDateTime(endTime)}`;
    }

    return content;
  }

  _formatState(state) {
    const stateMap = {
      'planifie': 'Planifié',
      'en_cours': 'En cours',
      'deneige': 'Déneigé',
      'replanifie': 'Replanifié',
      'degage': 'Dégagé',
      'enneige': 'Enneigé',
    };
    return stateMap[state] || state;
  }

  _formatDateTime(isoString) {
    try {
      const date = new Date(isoString);
      return date.toLocaleString('fr-CA', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch (e) {
      return isoString;
    }
  }

  getCardSize() {
    return 4;
  }
}

customElements.define('montreal-snow-removal-map-card', MontrealSnowRemovalMapCard);

// Register card with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'montreal-snow-removal-map-card',
  name: 'Montreal Snow Removal Map',
  description: 'Display snow removal streets as colored line segments on a map',
});

console.info(
  '%c MONTREAL-SNOW-REMOVAL-MAP-CARD %c v1.0.0 ',
  'color: white; background: #0066CC; font-weight: 700;',
  'color: #0066CC; background: white; font-weight: 700;'
);
