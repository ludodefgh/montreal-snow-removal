/**
 * Montreal Snow Removal Map Card
 *
 * Custom Lovelace card that displays snow removal streets as colored line segments
 * on a map based on their snow removal status.
 *
 * Features:
 * - Zoom-based display: show all streets at lower zoom, only tracked at high zoom
 * - Special markers for tracked streets (starred)
 * - Real-time color updates based on snow removal state
 * - Viewport-based loading for performance
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
    this._trackedLayers = new Map(); // Layers for tracked streets
    this._neighborhoodLayers = new Map(); // Layers for neighborhood streets
    this._hasAutoFitted = false;
    this._currentZoom = 15;
    this._loadingNeighborhood = false;
    this._neighborhoodCache = new Map(); // Cache viewport queries
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
      // New options
      show_all_streets: config.show_all_streets !== false, // Show neighborhood streets by default
      zoom_threshold: config.zoom_threshold || 14, // Zoom level to show all streets
      max_neighborhood_streets: config.max_neighborhood_streets || 100, // Max streets to load
    };
  }

  set hass(hass) {
    this._hass = hass;

    if (!this._map && !this._initializing) {
      this._initializing = true;
      this._initMap().then(() => {
        this._initializing = false;
        this._updateTrackedStreets();
        this._updateNeighborhoodStreets();
      });
    } else if (this._map) {
      // Update tracked streets when their state changes
      this._updateTrackedStreets();
    }
  }

  async _loadLeaflet() {
    return new Promise((resolve, reject) => {
      // Check if already loading
      if (document.querySelector('script[src*="leaflet.js"]')) {
        console.log('Leaflet script already in document, waiting...');
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
      if (typeof L === 'undefined') {
        console.log('Loading Leaflet library...');
        await this._loadLeaflet();
      }

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
          <div class="legend-item" style="margin-top: 8px; padding-top: 8px; border-top: 1px solid ${this._config.dark_mode ? '#666' : '#ccc'};">
            <span style="font-weight: bold;">★</span>
            <span style="margin-left: 4px;">Rue suivie</span>
          </div>
        </div>
      </ha-card>
    `;

    const mapElement = this.shadowRoot.getElementById('map');
    await new Promise(resolve => requestAnimationFrame(resolve));

    // Initialize Leaflet map
    this._map = L.map(mapElement, {
      zoomControl: true,
    });

    // Track zoom and pan changes
    this._map.on('zoomend', () => {
      this._currentZoom = this._map.getZoom();
      this._updateNeighborhoodStreetsVisibility();
    });

    this._map.on('moveend', () => {
      // Reload neighborhood streets when map moves
      if (this._currentZoom >= this._config.zoom_threshold && this._config.show_all_streets) {
        this._updateNeighborhoodStreets();
      }
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
      this._map.setView([45.5017, -73.5673], this._config.zoom);
    }

    this._currentZoom = this._map.getZoom();

    // Fix rendering issues
    const invalidateMapSize = () => {
      if (this._map) {
        this._map.invalidateSize();
      }
    };

    setTimeout(invalidateMapSize, 100);
    setTimeout(invalidateMapSize, 300);
    setTimeout(invalidateMapSize, 500);

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

  _updateTrackedStreets() {
    if (!this._map || !this._hass) {
      return;
    }

    const entities = this._config.entities;
    const bounds = [];

    entities.forEach(entityId => {
      const entity = this._hass.states[entityId];
      if (!entity) {
        console.warn(`Entity not found: ${entityId}`);
        return;
      }

      const attributes = entity.attributes;
      const coordinates = attributes.street_coordinates;

      if (!coordinates || coordinates.length === 0) {
        return;
      }

      const color = this._getColorForState(attributes.marker_color || attributes.snow_removal_state);

      // Remove existing layer
      if (this._trackedLayers.has(entityId)) {
        this._map.removeLayer(this._trackedLayers.get(entityId));
      }

      // Create thicker polyline for tracked streets
      const polyline = L.polyline(coordinates, {
        color: color,
        weight: 7,
        opacity: 0.9,
      });

      const popupContent = this._createPopupContent(attributes, true);
      polyline.bindPopup(popupContent);

      polyline.addTo(this._map);
      this._trackedLayers.set(entityId, polyline);

      coordinates.forEach(coord => bounds.push(coord));
    });

    // Auto-fit map on first load
    if (bounds.length > 0 && !this._config.center && !this._hasAutoFitted) {
      this._map.fitBounds(bounds, { padding: [50, 50] });
      this._hasAutoFitted = true;
    }
  }

  async _updateNeighborhoodStreets() {
    if (!this._map || !this._hass || !this._config.show_all_streets) {
      return;
    }

    if (this._currentZoom < this._config.zoom_threshold) {
      return;
    }

    if (this._loadingNeighborhood) {
      console.log('Already loading neighborhood streets');
      return;
    }

    this._loadingNeighborhood = true;

    try {
      // Get current viewport bounds
      const bounds = this._map.getBounds();
      const cacheKey = `${bounds.getNorth().toFixed(4)},${bounds.getSouth().toFixed(4)},${bounds.getEast().toFixed(4)},${bounds.getWest().toFixed(4)}`;

      // Check cache
      if (this._neighborhoodCache.has(cacheKey)) {
        console.log('Using cached neighborhood streets');
        this._loadingNeighborhood = false;
        return;
      }

      console.log('Fetching neighborhood streets from service');

      // Call Home Assistant service via WebSocket to get return value
      const result = await this._hass.callWS({
        type: 'call_service',
        domain: 'montreal_snow_removal',
        service: 'get_streets_in_viewport',
        service_data: {
          north: bounds.getNorth(),
          south: bounds.getSouth(),
          east: bounds.getEast(),
          west: bounds.getWest(),
          max_results: this._config.max_neighborhood_streets,
        },
        return_response: true,
      });

      const streets = result?.response?.streets || [];
      console.log(`Loaded ${streets.length} neighborhood streets`);

      // Clear old neighborhood layers
      this._neighborhoodLayers.forEach(layer => this._map.removeLayer(layer));
      this._neighborhoodLayers.clear();

      // Add new street layers
      streets.forEach(street => {
        // Skip if this is a tracked street
        if (this._isTrackedStreet(street.cote_rue_id)) {
          return;
        }

        const color = this._getColorForState(street.state);

        const polyline = L.polyline(street.coordinates, {
          color: color,
          weight: 3,
          opacity: 0.6,
        });

        const popupContent = this._createPopupContentFromStreet(street, false);
        polyline.bindPopup(popupContent);

        polyline.addTo(this._map);
        this._neighborhoodLayers.set(street.cote_rue_id, polyline);
      });

      // Cache this viewport
      this._neighborhoodCache.set(cacheKey, true);

      // Limit cache size to 10 entries
      if (this._neighborhoodCache.size > 10) {
        const firstKey = this._neighborhoodCache.keys().next().value;
        this._neighborhoodCache.delete(firstKey);
      }

    } catch (error) {
      console.error('Failed to load neighborhood streets:', error);
    } finally {
      this._loadingNeighborhood = false;
    }
  }

  _updateNeighborhoodStreetsVisibility() {
    if (!this._config.show_all_streets) {
      return;
    }

    if (this._currentZoom < this._config.zoom_threshold) {
      // Hide neighborhood streets
      this._neighborhoodLayers.forEach(layer => {
        if (this._map.hasLayer(layer)) {
          this._map.removeLayer(layer);
        }
      });
      console.log(`Zoom ${this._currentZoom}: hiding neighborhood streets`);
    } else {
      // Show neighborhood streets
      this._neighborhoodLayers.forEach(layer => {
        if (!this._map.hasLayer(layer)) {
          layer.addTo(this._map);
        }
      });
      console.log(`Zoom ${this._currentZoom}: showing neighborhood streets`);

      // Trigger reload for current viewport
      this._updateNeighborhoodStreets();
    }
  }

  _isTrackedStreet(coteRueId) {
    // Check if this cote_rue_id belongs to any tracked entity
    return this._config.entities.some(entityId => {
      const entity = this._hass.states[entityId];
      return entity && entity.attributes.cote_rue_id === coteRueId;
    });
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

  _createPopupContent(attributes, isTracked) {
    const streetName = attributes.street_name || 'Unknown';
    const streetSide = attributes.street_side || '';
    const state = attributes.snow_removal_state || 'unknown';
    const startTime = attributes.start_time || '';
    const endTime = attributes.end_time || '';

    let content = `<strong>${streetName}</strong>`;

    if (isTracked) {
      content += ` <span style="color: gold; font-size: 16px;">★</span>`;
    }

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

  _createPopupContentFromStreet(street, isTracked) {
    let content = `<strong>${street.street_name}</strong>`;

    if (isTracked) {
      content += ` <span style="color: gold; font-size: 16px;">★</span>`;
    }

    if (street.street_side) {
      content += `<br>Côté: ${street.street_side}`;
    }
    content += `<br>État: ${this._formatState(street.state)}`;
    if (street.start_time) {
      content += `<br>Début: ${this._formatDateTime(street.start_time)}`;
    }
    if (street.end_time) {
      content += `<br>Fin: ${this._formatDateTime(street.end_time)}`;
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

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'montreal-snow-removal-map-card',
  name: 'Montreal Snow Removal Map',
  description: 'Display snow removal streets as colored line segments on a map',
});

console.info(
  '%c MONTREAL-SNOW-REMOVAL-MAP-CARD %c v2.0.0 ',
  'color: white; background: #0066CC; font-weight: 700;',
  'color: #0066CC; background: white; font-weight: 700;'
);
