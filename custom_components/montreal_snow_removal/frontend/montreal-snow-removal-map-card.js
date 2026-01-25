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
    this._vehicleLayers = new Map(); // Layers for vehicle streets
    this._vehicleMarkers = new Map(); // Markers for vehicle locations
    this._hasAutoFitted = false;
    this._currentZoom = 15;
    this._loadingNeighborhood = false;
    this._neighborhoodCache = new Map(); // Cache viewport queries
    this._centerMarker = null; // Debug marker for viewport center

    // Translations
    this._translations = {
      fr: {
        legend: 'Légende',
        snowy: 'Enneigé',
        cleared: 'Déneigé',
        parking_banned: 'Stationnement interdit',
        loading_planned: 'Chargement planifié',
        will_be_rescheduled: 'Sera replanifié',
        loading_in_progress: 'Chargement en cours',
        no_operation: 'Aucune opération',
        tracked_street: 'Rue suivie',
        tracked_vehicle: 'Véhicule suivi',
        side: 'Côté',
        status: 'État',
        start: 'Début',
        end: 'Fin',
        vehicle: 'Véhicule',
      },
      en: {
        legend: 'Legend',
        snowy: 'Snowy',
        cleared: 'Cleared',
        parking_banned: 'Parking banned',
        loading_planned: 'Loading planned',
        will_be_rescheduled: 'Will be rescheduled',
        loading_in_progress: 'Loading in progress',
        no_operation: 'No operation',
        tracked_street: 'Tracked street',
        tracked_vehicle: 'Tracked vehicle',
        side: 'Side',
        status: 'Status',
        start: 'Start',
        end: 'End',
        vehicle: 'Vehicle',
      },
    };
  }

  _getLanguage() {
    // Get language from Home Assistant, default to French
    const lang = this._hass?.language || 'fr';
    // Support both 'fr' and 'fr-CA', etc.
    return lang.startsWith('fr') ? 'fr' : 'en';
  }

  _t(key) {
    const lang = this._getLanguage();
    return this._translations[lang]?.[key] || this._translations['en'][key] || key;
  }

  setConfig(config) {
    // Allow either entities or vehicles to be defined (or both)
    const hasEntities = config.entities && Array.isArray(config.entities) && config.entities.length > 0;
    const hasVehicles = config.vehicles && Array.isArray(config.vehicles) && config.vehicles.length > 0;
    if (!hasEntities && !hasVehicles) {
      throw new Error('You need to define entities or vehicles');
    }
    this._config = {
      title: config.title || 'Montreal Snow Removal',
      entities: config.entities || [],
      vehicles: config.vehicles || [], // Vehicle sensor entities
      zoom: config.zoom || 15,
      center: config.center || null,
      dark_mode: config.dark_mode !== false,
      height: config.height || 600, // Map height in pixels
      // New options
      show_all_streets: config.show_all_streets !== false, // Show neighborhood streets by default
      zoom_threshold: config.zoom_threshold || 14, // Zoom level to show all streets
      max_neighborhood_streets: config.max_neighborhood_streets || 100, // Max streets to load
      debug_center: config.debug_center || false, // Show center marker for debugging
      // Vehicle options
      show_vehicle_markers: config.show_vehicle_markers !== false, // Show car icons at GPS location
      show_vehicle_streets: config.show_vehicle_streets !== false, // Show vehicle's current street as favorite
    };
  }

  set hass(hass) {
    this._hass = hass;

    if (!this._map && !this._initializing) {
      this._initializing = true;
      this._initMap().then(() => {
        this._initializing = false;
        this._updateTrackedStreets();
        this._updateVehicles();
        this._updateNeighborhoodStreets();
      });
    } else if (this._map) {
      // Update tracked streets and vehicles when their state changes
      this._updateTrackedStreets();
      this._updateVehicles();
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
          position: relative;
          z-index: 0;
        }
        ha-card {
          overflow: hidden;
          position: relative;
          z-index: 0;
        }
        .card-header {
          padding: 16px;
          font-size: 16px;
          font-weight: 500;
        }
        #map {
          width: 100%;
          height: ${this._config.height}px;
          min-height: 400px;
          position: relative;
          z-index: 0;
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
          z-index: 400;
          font-size: 12px;
        }
        .legend-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          cursor: pointer;
          margin-bottom: 8px;
          padding-bottom: 4px;
          border-bottom: 1px solid ${this._config.dark_mode ? '#666' : '#ccc'};
        }
        .legend-title {
          font-weight: bold;
          font-size: 13px;
        }
        .legend-toggle {
          font-size: 16px;
          line-height: 1;
          user-select: none;
        }
        .legend-content {
          display: block;
        }
        .legend-content.collapsed {
          display: none;
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
          <div class="legend-header" id="legend-header">
            <span class="legend-title">${this._t('legend')}</span>
            <span class="legend-toggle">▼</span>
          </div>
          <div class="legend-content" id="legend-content">
            <div class="legend-item">
              <div class="legend-color" style="background-color: #FF0000;"></div>
              <span>${this._t('parking_banned')}</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background-color: #FF8C00;"></div>
              <span>${this._t('loading_planned')}</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background-color: #FFD700;"></div>
              <span>${this._t('will_be_rescheduled')}</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background-color: #9932CC;"></div>
              <span>${this._t('loading_in_progress')}</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background-color: #00AA00;"></div>
              <span>${this._t('cleared')}</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background-color: #0066CC;"></div>
              <span>${this._t('snowy')}</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background-color: #808080;"></div>
              <span>${this._t('no_operation')}</span>
            </div>
            <div class="legend-item" style="margin-top: 8px; padding-top: 8px; border-top: 1px solid ${this._config.dark_mode ? '#666' : '#ccc'};">
              <span style="font-weight: bold;">★</span>
              <span style="margin-left: 4px;">${this._t('tracked_street')}</span>
            </div>
            <div class="legend-item">
              <span style="font-size: 16px;">🚗</span>
              <span style="margin-left: 4px;">${this._t('tracked_vehicle')}</span>
            </div>
          </div>
        </div>
      </ha-card>
    `;

    const mapElement = this.shadowRoot.getElementById('map');
    await new Promise(resolve => requestAnimationFrame(resolve));

    // Setup legend toggle
    const legendHeader = this.shadowRoot.getElementById('legend-header');
    const legendContent = this.shadowRoot.getElementById('legend-content');
    const legendToggle = this.shadowRoot.querySelector('.legend-toggle');

    legendHeader.addEventListener('click', () => {
      const isCollapsed = legendContent.classList.toggle('collapsed');
      legendToggle.textContent = isCollapsed ? '▶' : '▼';
    });

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

    // Add map tiles - using CartoDB for better styling
    const tileUrl = this._config.dark_mode
      ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
      : 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';

    L.tileLayer(tileUrl, {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 20,
      subdomains: 'abcd',
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

  _updateVehicles() {
    if (!this._map || !this._hass) {
      return;
    }

    const vehicles = this._config.vehicles || [];
    const bounds = [];

    vehicles.forEach(entityId => {
      const entity = this._hass.states[entityId];
      if (!entity) {
        console.warn(`Vehicle entity not found: ${entityId}`);
        return;
      }

      const attributes = entity.attributes;

      // Get vehicle GPS location from source entity
      if (this._config.show_vehicle_markers) {
        const sourceEntityId = attributes.source_entity;
        if (sourceEntityId) {
          const sourceEntity = this._hass.states[sourceEntityId];
          if (sourceEntity) {
            const lat = sourceEntity.attributes.latitude;
            const lng = sourceEntity.attributes.longitude;
            if (lat && lng) {
              this._updateVehicleMarker(entityId, lat, lng, attributes);
            }
          }
        }
      }

      // Draw vehicle's current street as favorite
      if (this._config.show_vehicle_streets) {
        const coordinates = attributes.street_coordinates;
        if (coordinates && coordinates.length > 0) {
          const color = this._getColorForState(attributes.marker_color || attributes.snow_removal_state);

          // Remove existing layer
          if (this._vehicleLayers.has(entityId)) {
            this._map.removeLayer(this._vehicleLayers.get(entityId));
          }

          // Create thicker polyline for vehicle streets (same as tracked)
          const polyline = L.polyline(coordinates, {
            color: color,
            weight: 7,
            opacity: 0.9,
          });

          const popupContent = this._createVehiclePopupContent(attributes);
          polyline.bindPopup(popupContent);

          polyline.addTo(this._map);
          this._vehicleLayers.set(entityId, polyline);

          coordinates.forEach(coord => bounds.push(coord));
        }
      }
    });

    // Include vehicle bounds in auto-fit (only on first load)
    if (bounds.length > 0 && !this._config.center && !this._hasAutoFitted) {
      // Combine with tracked street bounds
      const allBounds = [...bounds];
      this._trackedLayers.forEach(layer => {
        layer.getLatLngs().forEach(coord => allBounds.push([coord.lat, coord.lng]));
      });
      if (allBounds.length > 0) {
        this._map.fitBounds(allBounds, { padding: [50, 50] });
        this._hasAutoFitted = true;
      }
    }
  }

  _updateVehicleMarker(entityId, lat, lng, attributes) {
    // Remove existing marker
    if (this._vehicleMarkers.has(entityId)) {
      this._map.removeLayer(this._vehicleMarkers.get(entityId));
    }

    // Determine marker color based on parking ban status
    const state = attributes.snow_removal_state;
    const markerColor = this._getColorForState(attributes.marker_color || state);

    // Create car icon
    const carIcon = L.divIcon({
      className: 'vehicle-marker',
      html: `<div style="
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        filter: drop-shadow(2px 2px 2px rgba(0,0,0,0.5));
      ">🚗</div>`,
      iconSize: [32, 32],
      iconAnchor: [16, 16],
    });

    // Create marker
    const marker = L.marker([lat, lng], {
      icon: carIcon,
      zIndexOffset: 1000, // Above street lines
    });

    // Create popup content
    const vehicleName = attributes.current_street || this._t('vehicle');
    let popupContent = `<strong>🚗 ${vehicleName}</strong>`;
    if (attributes.street_side) {
      popupContent += `<br>${this._t('side')}: ${attributes.street_side}`;
    }
    if (state) {
      popupContent += `<br>${this._t('status')}: ${this._formatState(state)}`;
    }

    marker.bindPopup(popupContent);
    marker.addTo(this._map);
    this._vehicleMarkers.set(entityId, marker);
  }

  _createVehiclePopupContent(attributes) {
    const streetName = attributes.street_name || attributes.current_street || 'Unknown';
    const streetSide = attributes.street_side || '';
    const state = attributes.snow_removal_state || 'unknown';
    const startTime = attributes.start_time || '';
    const endTime = attributes.end_time || '';

    let content = `<strong>${streetName}</strong>`;
    content += ` <span style="font-size: 16px;">🚗</span>`;

    if (streetSide) {
      content += `<br>${this._t('side')}: ${streetSide}`;
    }
    content += `<br>${this._t('status')}: ${this._formatState(state)}`;
    if (startTime) {
      content += `<br>${this._t('start')}: ${this._formatDateTime(startTime)}`;
    }
    if (endTime) {
      content += `<br>${this._t('end')}: ${this._formatDateTime(endTime)}`;
    }

    return content;
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

      // Get viewport center
      const center = this._map.getCenter();
      const centerLat = center.lat;
      const centerLng = center.lng;

      // Call Home Assistant service via WebSocket to get return value
      // Now includes center coordinates for backend sorting
      const result = await this._hass.callWS({
        type: 'call_service',
        domain: 'montreal_snow_removal',
        service: 'get_streets_in_viewport',
        service_data: {
          north: bounds.getNorth(),
          south: bounds.getSouth(),
          east: bounds.getEast(),
          west: bounds.getWest(),
          center_lat: centerLat,
          center_lng: centerLng,
          max_results: this._config.max_neighborhood_streets,
        },
        return_response: true,
      });

      const streets = result?.response?.streets || [];
      console.log(`Loaded ${streets.length} neighborhood streets (sorted by backend)`);

      // Update debug center marker if enabled
      this._updateCenterMarker(centerLat, centerLng);

      // Streets are already sorted by backend, no need to sort again
      const streetsToDisplay = streets;

      console.log(`Displaying ${streetsToDisplay.length} streets`);

      // Clear old neighborhood layers
      this._neighborhoodLayers.forEach(layer => this._map.removeLayer(layer));
      this._neighborhoodLayers.clear();

      // Add new street layers
      streetsToDisplay.forEach(street => {
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
    // Check if this cote_rue_id belongs to any tracked entity (static address)
    const isStaticTracked = this._config.entities.some(entityId => {
      const entity = this._hass.states[entityId];
      return entity && entity.attributes.cote_rue_id === coteRueId;
    });
    if (isStaticTracked) return true;

    // Check if this cote_rue_id belongs to any tracked vehicle
    const vehicles = this._config.vehicles || [];
    return vehicles.some(entityId => {
      const entity = this._hass.states[entityId];
      return entity && entity.attributes.cote_rue_id === coteRueId;
    });
  }

  _getColorForState(state) {
    const colorMap = {
      // Color names (from marker_color attribute)
      'blue': '#0066CC',
      'green': '#00AA00',
      'red': '#FF0000',
      'orange': '#FF8C00',
      'yellow': '#FFD700',
      'purple': '#9932CC',
      'gray': '#808080',
      // State names
      'enneige': '#0066CC',           // Blue - Snowy
      'deneige': '#00AA00',           // Green - Cleared
      'stationnement_interdit': '#FF0000',  // Red - Parking banned (within interval)
      'planifie': '#FF8C00',          // Orange - Planned (not yet in interval)
      'replanifie': '#FF8C00',        // Orange - Rescheduled with date (not yet in interval)
      'sera_replanifie': '#FFD700',   // Yellow - Will be rescheduled (no date yet)
      'en_cours': '#9932CC',          // Purple - Loading in progress
      'degage': '#808080',            // Gray - Clear
    };
    return colorMap[state] || '#808080';
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
      content += `<br>${this._t('side')}: ${streetSide}`;
    }
    content += `<br>${this._t('status')}: ${this._formatState(state)}`;
    if (startTime) {
      content += `<br>${this._t('start')}: ${this._formatDateTime(startTime)}`;
    }
    if (endTime) {
      content += `<br>${this._t('end')}: ${this._formatDateTime(endTime)}`;
    }

    return content;
  }

  _createPopupContentFromStreet(street, isTracked) {
    let content = `<strong>${street.street_name}</strong>`;

    if (isTracked) {
      content += ` <span style="color: gold; font-size: 16px;">★</span>`;
    }

    if (street.street_side) {
      content += `<br>${this._t('side')}: ${street.street_side}`;
    }
    content += `<br>${this._t('status')}: ${this._formatState(street.state)}`;
    if (street.start_time) {
      content += `<br>${this._t('start')}: ${this._formatDateTime(street.start_time)}`;
    }
    if (street.end_time) {
      content += `<br>${this._t('end')}: ${this._formatDateTime(street.end_time)}`;
    }

    return content;
  }

  _formatState(state) {
    const stateMapFr = {
      'enneige': 'Enneigé',
      'deneige': 'Déneigé',
      'stationnement_interdit': 'Stationnement interdit',
      'planifie': 'Chargement planifié',
      'replanifie': 'Chargement replanifié',
      'sera_replanifie': 'Sera replanifié',
      'en_cours': 'Chargement en cours',
      'degage': 'Aucune opération',
    };
    const stateMapEn = {
      'enneige': 'Snowy',
      'deneige': 'Cleared',
      'stationnement_interdit': 'Parking banned',
      'planifie': 'Loading planned',
      'replanifie': 'Loading rescheduled',
      'sera_replanifie': 'Will be rescheduled',
      'en_cours': 'Loading in progress',
      'degage': 'No operation',
    };
    const stateMap = this._getLanguage() === 'fr' ? stateMapFr : stateMapEn;
    return stateMap[state] || state;
  }

  _formatDateTime(isoString) {
    try {
      const date = new Date(isoString);
      const locale = this._getLanguage() === 'fr' ? 'fr-CA' : 'en-CA';
      return date.toLocaleString(locale, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch (e) {
      return isoString;
    }
  }

  _getMinDistanceToCenter(coordinates, centerLat, centerLng) {
    // Calculate minimum distance from any point of the street to the viewport center
    if (!coordinates || coordinates.length === 0) {
      return Infinity;
    }

    let minDistance = Infinity;

    // Check every point in the street's coordinates
    for (const coord of coordinates) {
      const distance = this._calculateDistance(centerLat, centerLng, coord[0], coord[1]);
      if (distance < minDistance) {
        minDistance = distance;
      }
    }

    return minDistance;
  }

  _getStreetCenter(coordinates) {
    // Calculate the center point of a street from its coordinates
    if (!coordinates || coordinates.length === 0) {
      return { lat: 0, lng: 0 };
    }

    // Find middle coordinate (geometrically simpler than calculating actual midpoint of polyline)
    const middleIndex = Math.floor(coordinates.length / 2);
    return {
      lat: coordinates[middleIndex][0],
      lng: coordinates[middleIndex][1]
    };
  }

  _calculateDistance(lat1, lng1, lat2, lng2) {
    // Haversine formula to calculate distance between two GPS coordinates
    // Returns distance in kilometers
    const R = 6371; // Earth's radius in km
    const dLat = this._toRadians(lat2 - lat1);
    const dLng = this._toRadians(lng2 - lng1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(this._toRadians(lat1)) * Math.cos(this._toRadians(lat2)) *
      Math.sin(dLng / 2) * Math.sin(dLng / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  _toRadians(degrees) {
    return degrees * (Math.PI / 180);
  }

  _updateCenterMarker(lat, lng) {
    if (!this._config.debug_center) {
      // Remove marker if debug is disabled
      if (this._centerMarker) {
        this._map.removeLayer(this._centerMarker);
        this._centerMarker = null;
      }
      return;
    }

    // Remove existing marker
    if (this._centerMarker) {
      this._map.removeLayer(this._centerMarker);
    }

    // Create custom icon for center marker (red crosshair)
    const crosshairIcon = L.divIcon({
      className: 'center-marker',
      html: `<div style="
        width: 40px;
        height: 40px;
        position: relative;
      ">
        <div style="
          position: absolute;
          width: 2px;
          height: 40px;
          background-color: red;
          left: 19px;
          top: 0;
        "></div>
        <div style="
          position: absolute;
          width: 40px;
          height: 2px;
          background-color: red;
          left: 0;
          top: 19px;
        "></div>
        <div style="
          position: absolute;
          width: 12px;
          height: 12px;
          border: 2px solid red;
          border-radius: 50%;
          left: 14px;
          top: 14px;
          background-color: rgba(255, 0, 0, 0.3);
        "></div>
      </div>`,
      iconSize: [40, 40],
      iconAnchor: [20, 20]
    });

    // Add new marker at center
    this._centerMarker = L.marker([lat, lng], {
      icon: crosshairIcon,
      zIndexOffset: 1000
    });
    this._centerMarker.addTo(this._map);
  }

  getCardSize() {
    return 4;
  }

  static getConfigElement() {
    return document.createElement('montreal-snow-removal-map-card-editor');
  }

  static getStubConfig() {
    return {
      entities: [],
      vehicles: [],
      title: 'Déneigement Montréal',
      zoom: 15,
      height: 600,
      dark_mode: true,
      show_all_streets: true,
      zoom_threshold: 14,
      max_neighborhood_streets: 100,
      debug_center: false,
      show_vehicle_markers: true,
      show_vehicle_streets: true,
    };
  }
}

// Configuration Editor
class MontrealSnowRemovalMapCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._hass = null;
    this._availableEntities = [];
    this._availableVehicleEntities = [];
    this._ignoreNextSetConfig = false;
  }

  setConfig(config) {
    this._config = { ...config };
    // Skip render if this is from our own _fireEvent
    if (this._ignoreNextSetConfig) {
      this._ignoreNextSetConfig = false;
      return;
    }
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._updateAvailableEntities();
  }

  _updateAvailableEntities() {
    if (!this._hass) return;

    // Get all device_tracker entities from Montreal Snow Removal (static addresses)
    this._availableEntities = Object.keys(this._hass.states)
      .filter(entityId => {
        if (!entityId.startsWith('device_tracker.')) return false;
        const state = this._hass.states[entityId];
        // Check if it has street_coordinates attribute (Montreal Snow Removal map entity)
        return state.attributes && state.attributes.street_coordinates;
      })
      .sort();

    // Get all vehicle sensor entities from Montreal Snow Removal
    this._availableVehicleEntities = Object.keys(this._hass.states)
      .filter(entityId => {
        if (!entityId.startsWith('sensor.')) return false;
        const state = this._hass.states[entityId];
        // Check if it has source_entity attribute (Montreal Snow Removal vehicle entity)
        return state.attributes && state.attributes.source_entity && state.attributes.cote_rue_id !== undefined;
      })
      .sort();
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        .card-config {
          padding: 16px;
        }
        .option {
          display: flex;
          align-items: center;
          margin: 12px 0;
        }
        .option label {
          flex: 1;
          font-weight: 500;
        }
        .option input[type="text"],
        .option input[type="number"] {
          flex: 2;
          padding: 8px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
        }
        .option input[type="checkbox"] {
          width: 20px;
          height: 20px;
        }
        .section-title {
          font-weight: bold;
          margin-top: 16px;
          margin-bottom: 8px;
          color: var(--primary-color);
        }
        .entity-list {
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          padding: 8px;
          background: var(--secondary-background-color);
          margin: 8px 0;
        }
        .entity-item {
          display: flex;
          align-items: center;
          margin: 4px 0;
          padding: 4px;
          background: var(--primary-background-color);
          border-radius: 4px;
        }
        .entity-item input {
          flex: 1;
          margin-right: 8px;
          padding: 4px 8px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
        }
        .entity-item button {
          padding: 4px 8px;
          background: var(--primary-color);
          color: var(--text-primary-color);
          border: none;
          border-radius: 4px;
          cursor: pointer;
        }
        .entity-item button:hover {
          opacity: 0.8;
        }
        .add-entity-btn {
          margin-top: 8px;
          padding: 8px 16px;
          background: var(--primary-color);
          color: var(--text-primary-color);
          border: none;
          border-radius: 4px;
          cursor: pointer;
        }
        .add-entity-btn:hover {
          opacity: 0.8;
        }
        .help-text {
          font-size: 12px;
          color: var(--secondary-text-color);
          margin-top: 4px;
        }
        .entity-input-wrapper {
          position: relative;
          flex: 1;
          margin-right: 8px;
        }
        .entity-input-wrapper input {
          width: 100%;
          padding: 4px 8px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          box-sizing: border-box;
        }
        .autocomplete-list {
          position: absolute;
          top: 100%;
          left: 0;
          right: 0;
          max-height: 200px;
          overflow-y: auto;
          background: var(--primary-background-color);
          border: 1px solid var(--divider-color);
          border-top: none;
          border-radius: 0 0 4px 4px;
          z-index: 1000;
          display: none;
        }
        .autocomplete-list.show {
          display: block;
        }
        .autocomplete-item {
          padding: 8px 12px;
          cursor: pointer;
          font-size: 13px;
          border-bottom: 1px solid var(--divider-color);
        }
        .autocomplete-item:last-child {
          border-bottom: none;
        }
        .autocomplete-item:hover,
        .autocomplete-item.selected {
          background: var(--primary-color);
          color: var(--text-primary-color);
        }
        .autocomplete-item .entity-name {
          font-weight: 500;
        }
        .autocomplete-item .entity-friendly {
          font-size: 11px;
          opacity: 0.8;
          margin-top: 2px;
        }
      </style>
      <div class="card-config">
        <div class="section-title">Général</div>

        <div class="option">
          <label for="title">Titre</label>
          <input
            type="text"
            id="title"
            value="${this._config.title || ''}"
            placeholder="Déneigement Montréal"
          />
        </div>

        <div class="option">
          <label for="height">Hauteur (px)</label>
          <input
            type="number"
            id="height"
            value="${this._config.height || 600}"
            min="200"
            max="1200"
          />
        </div>

        <div class="section-title">Adresses statiques</div>
        <div class="entity-list" id="entity-list">
          ${(this._config.entities || []).map((entity, index) => `
            <div class="entity-item" data-index="${index}">
              <div class="entity-input-wrapper">
                <input
                  type="text"
                  class="entity-input"
                  data-index="${index}"
                  value="${entity}"
                  placeholder="device_tracker.snow_removal_..."
                  autocomplete="off"
                />
                <div class="autocomplete-list" data-index="${index}"></div>
              </div>
              <button data-index="${index}">✕</button>
            </div>
          `).join('')}
        </div>
        <button class="add-entity-btn" id="add-entity-btn">+ Ajouter une adresse</button>
        <div class="help-text">Adresses configurées manuellement (device_tracker)</div>

        <div class="section-title">Véhicules 🚗</div>
        <div class="entity-list" id="vehicle-list">
          ${(this._config.vehicles || []).map((vehicle, index) => `
            <div class="entity-item vehicle-item" data-index="${index}">
              <div class="entity-input-wrapper">
                <input
                  type="text"
                  class="vehicle-input"
                  data-index="${index}"
                  value="${vehicle}"
                  placeholder="sensor.snow_removal_vehicle_..."
                  autocomplete="off"
                />
                <div class="autocomplete-list vehicle-autocomplete" data-index="${index}"></div>
              </div>
              <button class="remove-vehicle-btn" data-index="${index}">✕</button>
            </div>
          `).join('')}
        </div>
        <button class="add-entity-btn" id="add-vehicle-btn">+ Ajouter un véhicule</button>
        <div class="help-text">Véhicules suivis par GPS (capteurs avec source_entity)</div>

        <div class="option">
          <label for="show_vehicle_markers">Afficher icône véhicule sur carte</label>
          <input
            type="checkbox"
            id="show_vehicle_markers"
            ${this._config.show_vehicle_markers !== false ? 'checked' : ''}
          />
        </div>

        <div class="option">
          <label for="show_vehicle_streets">Afficher rue du véhicule en favori</label>
          <input
            type="checkbox"
            id="show_vehicle_streets"
            ${this._config.show_vehicle_streets !== false ? 'checked' : ''}
          />
        </div>

        <div class="section-title">Centre et Zoom</div>

        <div class="option">
          <label for="zoom">Zoom initial</label>
          <input
            type="number"
            id="zoom"
            value="${this._config.zoom || 15}"
            min="10"
            max="19"
          />
        </div>

        <div class="option">
          <label for="center">Centre (lat, lng)</label>
          <input
            type="text"
            id="center"
            value="${this._config.center ? this._config.center.join(', ') : ''}"
            placeholder="45.5017, -73.5673"
          />
        </div>
        <div class="help-text">Laissez vide pour centrer automatiquement sur vos rues suivies</div>

        <div class="section-title">Apparence</div>

        <div class="option">
          <label for="dark_mode">Mode sombre</label>
          <input
            type="checkbox"
            id="dark_mode"
            ${this._config.dark_mode !== false ? 'checked' : ''}
          />
        </div>

        <div class="section-title">Rues du quartier</div>

        <div class="option">
          <label for="show_all_streets">Afficher les rues du quartier</label>
          <input
            type="checkbox"
            id="show_all_streets"
            ${this._config.show_all_streets !== false ? 'checked' : ''}
          />
        </div>

        <div class="option">
          <label for="zoom_threshold">Zoom minimum pour afficher</label>
          <input
            type="number"
            id="zoom_threshold"
            value="${this._config.zoom_threshold || 14}"
            min="10"
            max="19"
          />
        </div>

        <div class="option">
          <label for="max_neighborhood_streets">Nombre max de rues</label>
          <input
            type="number"
            id="max_neighborhood_streets"
            value="${this._config.max_neighborhood_streets || 100}"
            min="10"
            max="500"
          />
        </div>

        <div class="section-title">Débogage</div>

        <div class="option">
          <label for="debug_center">Afficher le marqueur central</label>
          <input
            type="checkbox"
            id="debug_center"
            ${this._config.debug_center ? 'checked' : ''}
          />
        </div>
      </div>
    `;

    // Add event listeners after rendering
    this.shadowRoot.querySelectorAll('input:not(.entity-input):not(.vehicle-input)').forEach(element => {
      if (element.id === 'center') {
        element.addEventListener('blur', this._centerChanged.bind(this));
        element.addEventListener('keydown', (e) => {
          if (e.key === 'Enter') {
            this._centerChanged(e);
          }
        });
      } else if (element.type === 'number') {
        // Pour les champs numériques: déclencher uniquement sur blur ou Enter
        element.addEventListener('blur', this._valueChanged.bind(this));
        element.addEventListener('keydown', (e) => {
          if (e.key === 'Enter') {
            this._valueChanged(e);
          }
        });
      } else {
        // Pour les autres champs (texte, checkbox): déclencher immédiatement
        element.addEventListener('input', this._valueChanged.bind(this));
        element.addEventListener('change', this._valueChanged.bind(this));
      }
    });

    // Entity input listeners with autocomplete
    this.shadowRoot.querySelectorAll('.entity-input').forEach(element => {
      element.addEventListener('input', (e) => this._onEntityInput(e, 'entity'));
      element.addEventListener('focus', (e) => this._onEntityFocus(e, 'entity'));
      element.addEventListener('blur', (e) => {
        // Delay to allow click on autocomplete item
        setTimeout(() => this._hideAutocomplete(e.target, 'entity'), 200);
        this._entityChanged(e);
      });
      element.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          this._hideAutocomplete(e.target, 'entity');
          this._entityChanged(e);
        } else if (e.key === 'Escape') {
          this._hideAutocomplete(e.target, 'entity');
        } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
          e.preventDefault();
          this._navigateAutocomplete(e.target, e.key === 'ArrowDown' ? 1 : -1, 'entity');
        }
      });
    });

    // Vehicle input listeners with autocomplete
    this.shadowRoot.querySelectorAll('.vehicle-input').forEach(element => {
      element.addEventListener('input', (e) => this._onEntityInput(e, 'vehicle'));
      element.addEventListener('focus', (e) => this._onEntityFocus(e, 'vehicle'));
      element.addEventListener('blur', (e) => {
        // Delay to allow click on autocomplete item
        setTimeout(() => this._hideAutocomplete(e.target, 'vehicle'), 200);
        this._vehicleChanged(e);
      });
      element.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          this._hideAutocomplete(e.target, 'vehicle');
          this._vehicleChanged(e);
        } else if (e.key === 'Escape') {
          this._hideAutocomplete(e.target, 'vehicle');
        } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
          e.preventDefault();
          this._navigateAutocomplete(e.target, e.key === 'ArrowDown' ? 1 : -1, 'vehicle');
        }
      });
    });

    // Add entity button
    this.shadowRoot.querySelector('#add-entity-btn')?.addEventListener('click', this._addEntity.bind(this));

    // Add vehicle button
    this.shadowRoot.querySelector('#add-vehicle-btn')?.addEventListener('click', this._addVehicle.bind(this));

    // Remove entity buttons (not vehicle buttons)
    this.shadowRoot.querySelectorAll('.entity-item:not(.vehicle-item) button').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const index = parseInt(e.target.dataset.index);
        this._removeEntity(index);
      });
    });

    // Remove vehicle buttons
    this.shadowRoot.querySelectorAll('.remove-vehicle-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const index = parseInt(e.target.dataset.index);
        this._removeVehicle(index);
      });
    });
  }

  _onEntityInput(ev, type = 'entity') {
    const input = ev.target;
    const value = input.value.toLowerCase();
    this._showAutocomplete(input, value, type);
  }

  _onEntityFocus(ev, type = 'entity') {
    const input = ev.target;
    const value = input.value.toLowerCase();
    this._showAutocomplete(input, value, type);
  }

  _showAutocomplete(input, filter, type = 'entity') {
    const index = input.dataset.index;
    const listSelector = type === 'vehicle'
      ? `.vehicle-autocomplete[data-index="${index}"]`
      : `.autocomplete-list:not(.vehicle-autocomplete)[data-index="${index}"]`;
    const listEl = this.shadowRoot.querySelector(listSelector);
    if (!listEl) return;

    // Get the appropriate lists based on type
    const currentItems = type === 'vehicle'
      ? (this._config.vehicles || [])
      : (this._config.entities || []);
    const availableItems = type === 'vehicle'
      ? this._availableVehicleEntities
      : this._availableEntities;

    // Filter available items
    const filtered = availableItems.filter(entityId => {
      // Don't show already selected items (except current one)
      if (currentItems.includes(entityId) && currentItems[index] !== entityId) {
        return false;
      }
      // Filter by search term
      if (filter && !entityId.toLowerCase().includes(filter)) {
        const state = this._hass.states[entityId];
        const friendlyName = state?.attributes?.friendly_name || '';
        if (!friendlyName.toLowerCase().includes(filter)) {
          return false;
        }
      }
      return true;
    });

    if (filtered.length === 0) {
      listEl.classList.remove('show');
      return;
    }

    // Build autocomplete list
    listEl.innerHTML = filtered.map(entityId => {
      const state = this._hass.states[entityId];
      const friendlyName = state?.attributes?.friendly_name || '';
      return `
        <div class="autocomplete-item" data-entity="${entityId}">
          <div class="entity-name">${entityId}</div>
          ${friendlyName ? `<div class="entity-friendly">${friendlyName}</div>` : ''}
        </div>
      `;
    }).join('');

    // Add click handlers
    const changeHandler = type === 'vehicle' ? this._vehicleChanged : this._entityChanged;
    listEl.querySelectorAll('.autocomplete-item').forEach(item => {
      item.addEventListener('mousedown', (e) => {
        e.preventDefault();
        const entityId = item.dataset.entity;
        input.value = entityId;
        this._hideAutocomplete(input, type);
        changeHandler.call(this, { target: input });
      });
    });

    listEl.classList.add('show');
  }

  _hideAutocomplete(input, type = 'entity') {
    const index = input.dataset.index;
    const listSelector = type === 'vehicle'
      ? `.vehicle-autocomplete[data-index="${index}"]`
      : `.autocomplete-list:not(.vehicle-autocomplete)[data-index="${index}"]`;
    const listEl = this.shadowRoot.querySelector(listSelector);
    if (listEl) {
      listEl.classList.remove('show');
    }
  }

  _navigateAutocomplete(input, direction, type = 'entity') {
    const index = input.dataset.index;
    const listSelector = type === 'vehicle'
      ? `.vehicle-autocomplete[data-index="${index}"]`
      : `.autocomplete-list:not(.vehicle-autocomplete)[data-index="${index}"]`;
    const listEl = this.shadowRoot.querySelector(listSelector);
    if (!listEl || !listEl.classList.contains('show')) return;

    const items = listEl.querySelectorAll('.autocomplete-item');
    if (items.length === 0) return;

    const currentSelected = listEl.querySelector('.autocomplete-item.selected');
    let newIndex = 0;

    if (currentSelected) {
      currentSelected.classList.remove('selected');
      const currentIndex = Array.from(items).indexOf(currentSelected);
      newIndex = currentIndex + direction;
      if (newIndex < 0) newIndex = items.length - 1;
      if (newIndex >= items.length) newIndex = 0;
    } else {
      newIndex = direction === 1 ? 0 : items.length - 1;
    }

    items[newIndex].classList.add('selected');
    items[newIndex].scrollIntoView({ block: 'nearest' });

    // Update input with selected value
    input.value = items[newIndex].dataset.entity;
  }

  _valueChanged(ev) {
    if (!this._config) {
      return;
    }

    const target = ev.target;
    const configValue = target.type === 'checkbox' ? target.checked : target.value;

    let value;
    if (target.type === 'number') {
      if (configValue === '') {
        return;
      }
      value = parseFloat(configValue);
      if (isNaN(value)) {
        return;
      }
    } else {
      value = configValue;
    }

    if (this._config[target.id] === value) {
      return;
    }

    this._config = {
      ...this._config,
      [target.id]: value,
    };

    this._fireEvent();
  }

  _centerChanged(ev) {
    const value = ev.target.value;
    if (value === '') {
      this._config = { ...this._config };
      delete this._config.center;
    } else {
      const parts = value.split(',').map(s => parseFloat(s.trim()));
      if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
        this._config = {
          ...this._config,
          center: parts,
        };
      }
    }
    this._fireEvent();
  }

  _entityChanged(ev) {
    const index = parseInt(ev.target.dataset.index);
    const entities = [...(this._config.entities || [])];
    entities[index] = ev.target.value;
    this._config = {
      ...this._config,
      entities,
    };
    this._fireEvent();
  }

  _addEntity() {
    const entities = [...(this._config.entities || []), ''];
    this._config = {
      ...this._config,
      entities,
    };
    this._fireEvent();
    this._render();
  }

  _removeEntity(index) {
    const entities = [...(this._config.entities || [])];
    entities.splice(index, 1);
    this._config = {
      ...this._config,
      entities,
    };
    this._fireEvent();
    this._render();
  }

  _vehicleChanged(ev) {
    const index = parseInt(ev.target.dataset.index);
    const vehicles = [...(this._config.vehicles || [])];
    vehicles[index] = ev.target.value;
    this._config = {
      ...this._config,
      vehicles,
    };
    this._fireEvent();
  }

  _addVehicle() {
    const vehicles = [...(this._config.vehicles || []), ''];
    this._config = {
      ...this._config,
      vehicles,
    };
    this._fireEvent();
    this._render();
  }

  _removeVehicle(index) {
    const vehicles = [...(this._config.vehicles || [])];
    vehicles.splice(index, 1);
    this._config = {
      ...this._config,
      vehicles,
    };
    this._fireEvent();
    this._render();
  }

  _fireEvent() {
    // Tell setConfig to skip the next render (it's our own update)
    this._ignoreNextSetConfig = true;

    const event = new CustomEvent('config-changed', {
      detail: { config: this._config },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }
}

customElements.define('montreal-snow-removal-map-card', MontrealSnowRemovalMapCard);
customElements.define('montreal-snow-removal-map-card-editor', MontrealSnowRemovalMapCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'montreal-snow-removal-map-card',
  name: 'Montreal Snow Removal Map',
  description: 'Display snow removal streets as colored line segments on a map',
});

console.info(
  '%c MONTREAL-SNOW-REMOVAL-MAP-CARD %c v2.1.0 ',
  'color: white; background: #0066CC; font-weight: 700;',
  'color: #0066CC; background: white; font-weight: 700;'
);
