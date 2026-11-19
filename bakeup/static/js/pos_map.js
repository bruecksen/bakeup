// Maps of the points of sale. MapLibre GL JS is not part of base.html, it is
// loaded once, and only on pages that contain a [data-pos-map] element:
//
// - overview: markers from a json_script payload (data-markers holds its id),
//   [data-pos-focus="<pk>"] inside the same [data-pos-overview] focuses a marker
// - pin picker (data-pos-map-edit): click or drag sets the inputs named in
//   data-lat-input / data-lng-input, [data-pos-map-remove] clears them; with
//   data-geocode-url the search (with type-ahead) places the pin and fills the address fields
(function () {
    if (window.bakeupPosMapLoaded) {
        return;
    }
    window.bakeupPosMapLoaded = true;

    // Germany, used until there is a marker to look at.
    var DEFAULT_CENTER = [10.45, 51.16];
    var DEFAULT_ZOOM = 5;
    var MARKER_ZOOM = 14;
    var library = null;

    function loadLibrary(element) {
        if (window.maplibregl) {
            return Promise.resolve();
        }
        if (!library) {
            library = new Promise(function (resolve, reject) {
                var link = document.createElement('link');
                link.rel = 'stylesheet';
                link.href = element.dataset.mapCss;
                document.head.appendChild(link);
                var script = document.createElement('script');
                script.src = element.dataset.mapJs;
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            });
        }
        return library;
    }

    function createMap(element, options) {
        var map = new maplibregl.Map(Object.assign({
            container: element,
            style: element.dataset.styleUrl,
            center: DEFAULT_CENTER,
            zoom: DEFAULT_ZOOM,
            // The style names its sources, they stay visible on small maps too.
            attributionControl: {compact: false}
        }, options));
        map.addControl(new maplibregl.NavigationControl({showCompass: false}));
        return map;
    }

    // A line of the popup with its icon, as on the cards of the overview.
    function popupLine(icon, texts) {
        var line = document.createElement('div');
        line.className = 'pos-popup-line';
        var symbol = document.createElement('i');
        symbol.className = icon + ' fa-fw';
        line.appendChild(symbol);
        var text = document.createElement('div');
        texts.forEach(function (value) {
            var row = document.createElement('div');
            row.textContent = value;
            text.appendChild(row);
        });
        line.appendChild(text);
        return line;
    }

    function popupContent(point) {
        var content = document.createElement('div');
        content.className = 'pos-popup';
        // MapLibre sets its own font on the map, the popup takes the shop's.
        content.style.fontFamily = getComputedStyle(document.body).fontFamily;
        var name = document.createElement('div');
        name.className = 'pos-popup-name';
        name.textContent = point.name;
        content.appendChild(name);
        if (point.address) {
            content.appendChild(popupLine('fa-solid fa-location-dot', [point.address]));
        }
        if (point.pickup_times && point.pickup_times.length) {
            content.appendChild(popupLine('fa-regular fa-clock', point.pickup_times));
        }
        return content;
    }

    // Pins in the colour of the shop's theme.
    function markerColor() {
        return getComputedStyle(document.documentElement)
            .getPropertyValue('--bs-primary').trim() || undefined;
    }

    function initOverview(element) {
        var payload = document.getElementById(element.dataset.markers);
        var points = payload ? JSON.parse(payload.textContent) : [];
        if (!points.length) {
            return;
        }
        var map = createMap(element, {
            center: [points[0].lng, points[0].lat],
            zoom: MARKER_ZOOM
        });
        var markers = {};
        var bounds = new maplibregl.LngLatBounds();
        var overview = element.closest('[data-pos-overview]');

        function setActiveCard(id, active) {
            var card = overview && overview.querySelector('[data-pos-card="' + id + '"]');
            if (card) {
                card.classList.toggle('active', active);
            }
        }

        points.forEach(function (point) {
            var position = [point.lng, point.lat];
            var popup = new maplibregl.Popup({offset: 30, maxWidth: '300px'}).setDOMContent(popupContent(point));
            // The card of the point of sale whose popup is open is highlighted.
            popup.on('open', function () {
                setActiveCard(point.id, true);
            });
            popup.on('close', function () {
                setActiveCard(point.id, false);
            });
            markers[point.id] = new maplibregl.Marker({color: markerColor()})
                .setLngLat(position)
                .setPopup(popup)
                .addTo(map);
            bounds.extend(position);
        });
        if (points.length > 1) {
            map.fitBounds(bounds, {padding: 60, maxZoom: MARKER_ZOOM, animate: false});
        }
        if (!overview) {
            return;
        }
        overview.querySelectorAll('[data-pos-focus]').forEach(function (trigger) {
            trigger.addEventListener('click', function () {
                var marker = markers[trigger.dataset.posFocus];
                if (!marker) {
                    return;
                }
                Object.keys(markers).forEach(function (id) {
                    if (markers[id] !== marker && markers[id].getPopup().isOpen()) {
                        markers[id].togglePopup();
                    }
                });
                map.flyTo({center: marker.getLngLat(), zoom: MARKER_ZOOM});
                if (!marker.getPopup().isOpen()) {
                    marker.togglePopup();
                }
                element.scrollIntoView({behavior: 'smooth', block: 'center'});
            });
        });
    }

    // SmartMaps geocoding: resolves with the first hit or null. A location
    // finds an address, coordinates alone name the place of a pin.
    function geocode(url, location, coordinates) {
        return fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                type: 'Feature',
                properties: {},
                geometry: {type: 'Point', coordinates: coordinates || [0, 0]},
                crs: {type: 'name', properties: {name: 'urn:ogc:def:crs:OGC:1.3:CRS84'}},
                searchparams: {
                    geocodingType: location ? 'GEOCODE' : 'REVERSE_GEOCODE',
                    coordFormatOut: 'GEODECIMAL_POINT'
                },
                authentication: {channel: 'bakeup'},
                location: location || {}
            })
        }).then(function (response) {
            if (!response.ok) {
                throw new Error('geocoding failed');
            }
            return response.json();
        }).then(function (data) {
            return (data.features && data.features[0]) || null;
        });
    }

    function initPinPicker(element) {
        var latInput = document.querySelector(element.dataset.latInput);
        var lngInput = document.querySelector(element.dataset.lngInput);
        var removeButton = document.querySelector('[data-pos-map-remove]');
        var searchInput = document.querySelector('[data-pos-map-search]');
        var searchButton = document.querySelector('[data-pos-map-search-button]');
        var status = document.querySelector('[data-pos-map-status]');
        var geocodeUrl = element.dataset.geocodeUrl;
        var suggestionList = document.querySelector('[data-pos-map-suggestions]');
        var tokenUrl = element.dataset.autocompleteTokenUrl;
        var autocompleteUrl = element.dataset.autocompleteUrl;
        var token = null;
        var suggestions = [];
        var activeSuggestion = -1;
        var suggestTimer = null;
        var suggestRequest = 0;
        // Form field and the property of a geocoding hit that fills it.
        var addressFields = [
            [document.getElementById('id_street'), 'street'],
            [document.getElementById('id_street_number'), 'houseNo'],
            [document.getElementById('id_postal_code'), 'zip'],
            [document.getElementById('id_city'), 'city']
        ].filter(function (field) {
            return field[0];
        });
        if (!latInput || !lngInput) {
            return;
        }
        var lat = parseFloat(latInput.value);
        var lng = parseFloat(lngInput.value);
        var hasPin = !isNaN(lat) && !isNaN(lng);
        var map = createMap(element, hasPin ? {center: [lng, lat], zoom: MARKER_ZOOM} : {});
        var marker = null;

        function showStatus(message) {
            if (status) {
                status.textContent = message || '';
                status.hidden = !message;
            }
        }

        function addressIsEmpty() {
            return addressFields.every(function (field) {
                return !field[0].value.trim();
            });
        }

        function fillAddress(properties) {
            addressFields.forEach(function (field) {
                var value = properties[field[1]] || '';
                var maxLength = field[0].maxLength;
                field[0].value = maxLength > 0 ? value.slice(0, maxLength) : value;
            });
        }

        function store(lngLat) {
            // The model stores six decimal places.
            var position = lngLat.wrap();
            latInput.value = position.lat.toFixed(6);
            lngInput.value = position.lng.toFixed(6);
            if (removeButton) {
                removeButton.hidden = false;
            }
        }

        // A pin placed by hand names its address only while none is entered, so
        // moving the pin to the exact spot never overwrites what was typed.
        function suggestAddress(lngLat) {
            if (!geocodeUrl || !addressIsEmpty()) {
                return;
            }
            var position = lngLat.wrap();
            geocode(geocodeUrl, null, [position.lng, position.lat]).then(function (hit) {
                if (hit && addressIsEmpty()) {
                    fillAddress(hit.properties);
                }
            }).catch(function () {});
        }

        function setPin(lngLat) {
            if (!marker) {
                marker = new maplibregl.Marker({draggable: true, color: markerColor()});
                marker.on('dragend', function () {
                    store(marker.getLngLat());
                    suggestAddress(marker.getLngLat());
                });
            }
            marker.setLngLat(lngLat).addTo(map);
        }

        function showHit(hit, fill) {
            var position = new maplibregl.LngLat(
                hit.geometry.coordinates[0], hit.geometry.coordinates[1]
            );
            setPin(position);
            store(position);
            map.flyTo({center: position, zoom: Math.max(map.getZoom(), MARKER_ZOOM)});
            if (fill) {
                fillAddress(hit.properties);
            }
        }

        // The token of the type-ahead lasts ten minutes, it is renewed after nine.
        function getToken() {
            if (token && Date.now() - token.time < 9 * 60 * 1000) {
                return Promise.resolve(token.value);
            }
            return fetch(tokenUrl).then(function (response) {
                if (!response.ok) {
                    throw new Error('no token');
                }
                return response.json();
            }).then(function (value) {
                token = {value: value, time: Date.now()};
                return value;
            });
        }

        function closeSuggestions() {
            clearTimeout(suggestTimer);
            // Answers that are still on their way are dropped.
            suggestRequest += 1;
            suggestions = [];
            activeSuggestion = -1;
            if (suggestionList) {
                suggestionList.hidden = true;
                suggestionList.textContent = '';
            }
            if (searchInput) {
                searchInput.setAttribute('aria-expanded', 'false');
            }
        }

        function markSuggestion(index) {
            activeSuggestion = index;
            Array.prototype.forEach.call(suggestionList.children, function (item, position) {
                item.classList.toggle('active', position === index);
                item.setAttribute('aria-selected', position === index ? 'true' : 'false');
            });
        }

        function chooseSuggestion(index) {
            var hit = suggestions[index];
            if (!hit) {
                return;
            }
            searchInput.value = hit.properties.displayValue || searchInput.value;
            closeSuggestions();
            showStatus('');
            showHit(hit, true);
        }

        function showSuggestions(hits) {
            suggestions = hits;
            activeSuggestion = -1;
            suggestionList.textContent = '';
            hits.forEach(function (hit, index) {
                var item = document.createElement('button');
                item.type = 'button';
                item.className = 'list-group-item list-group-item-action';
                item.setAttribute('role', 'option');
                item.textContent = hit.properties.displayValue;
                // mousedown comes before the blur that closes the list.
                item.addEventListener('mousedown', function (event) {
                    event.preventDefault();
                    chooseSuggestion(index);
                });
                suggestionList.appendChild(item);
            });
            suggestionList.hidden = !hits.length;
            searchInput.setAttribute('aria-expanded', hits.length ? 'true' : 'false');
        }

        function suggest() {
            var query = searchInput.value.trim();
            if (query.length < 3) {
                closeSuggestions();
                return;
            }
            var request = suggestRequest += 1;
            getToken().then(function (value) {
                return fetch(autocompleteUrl, {
                    method: 'POST',
                    headers: {
                        'Authorization': 'Bearer ' + value,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        query: query,
                        geoJson: true,
                        top: 5,
                        isoCountries: ['DE', 'AT', 'CH']
                    })
                });
            }).then(function (response) {
                if (!response.ok) {
                    throw new Error('no suggestions');
                }
                return response.json();
            }).then(function (data) {
                if (request === suggestRequest) {
                    showSuggestions(data.features || []);
                }
            }).catch(function () {
                // Without suggestions the search button still works.
                if (request === suggestRequest) {
                    closeSuggestions();
                }
            });
        }

        function search() {
            closeSuggestions();
            var query = searchInput ? searchInput.value.trim() : '';
            var location = {singleSlot: query};
            if (!query) {
                if (addressIsEmpty()) {
                    showStatus(element.dataset.messageEmpty);
                    return;
                }
                location = {};
                addressFields.forEach(function (field) {
                    location[field[1]] = field[0].value.trim();
                });
            }
            showStatus('');
            geocode(geocodeUrl, location).then(function (hit) {
                if (!hit) {
                    showStatus(element.dataset.messageNotFound);
                    return;
                }
                // Typed address fields are kept, a search fills them in.
                showHit(hit, Boolean(query));
            }).catch(function () {
                showStatus(element.dataset.messageError);
            });
        }

        if (hasPin) {
            setPin([lng, lat]);
        }
        map.on('click', function (event) {
            setPin(event.lngLat);
            store(event.lngLat);
            suggestAddress(event.lngLat);
        });
        if (removeButton) {
            removeButton.hidden = !hasPin;
            removeButton.addEventListener('click', function () {
                if (marker) {
                    marker.remove();
                }
                latInput.value = '';
                lngInput.value = '';
                removeButton.hidden = true;
            });
        }
        if (geocodeUrl && searchButton) {
            searchButton.addEventListener('click', search);
        }
        if (geocodeUrl && searchInput) {
            searchInput.addEventListener('keydown', function (event) {
                var count = suggestions.length;
                if (event.key === 'Enter') {
                    // Enter never submits the form: it takes the marked
                    // suggestion, or searches for what was typed.
                    event.preventDefault();
                    if (activeSuggestion >= 0) {
                        chooseSuggestion(activeSuggestion);
                    } else {
                        search();
                    }
                } else if (event.key === 'ArrowDown' && count) {
                    event.preventDefault();
                    markSuggestion((activeSuggestion + 1) % count);
                } else if (event.key === 'ArrowUp' && count) {
                    event.preventDefault();
                    markSuggestion((activeSuggestion - 1 + count) % count);
                } else if (event.key === 'Escape') {
                    closeSuggestions();
                }
            });
        }
        if (geocodeUrl && searchInput && suggestionList && tokenUrl && autocompleteUrl) {
            searchInput.addEventListener('input', function () {
                clearTimeout(suggestTimer);
                suggestTimer = setTimeout(suggest, 250);
            });
            searchInput.addEventListener('blur', closeSuggestions);
        }
    }

    function init() {
        document.querySelectorAll('[data-pos-map]').forEach(function (element) {
            loadLibrary(element).then(function () {
                if ('posMapEdit' in element.dataset) {
                    initPinPicker(element);
                } else {
                    initOverview(element);
                }
            }).catch(function () {
                // Without the map the list and the form still work.
                element.hidden = true;
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
