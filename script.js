// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function () {

    // 1. Initialize the Leaflet Map
    //---------------------------------
    const map = L.map('map').setView([20, 0], 2); // Initial view: latitude, longitude, zoom level

    // Add a tile layer (background map) - OpenStreetMap is free
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    const infoPanel = document.getElementById('info-panel');

    // 2. Load your JSON Data
    //-------------------------
    fetch('windborne_data_with_weather.json')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Data loaded:", data); // Check console to see if data is loaded
            if (data && data.length > 0) {
                // Make sure your JSON is an array of point objects
                plotBalloonData(data);
            } else {
                infoPanel.innerHTML = "<p>No balloon data loaded or data is empty. Make sure 'windborne_data_with_weather.json' is present and correct.</p>";
            }
        })
        .catch(error => {
            console.error("Error loading balloon data:", error);
            infoPanel.innerHTML = `<p>Error loading balloon data: ${error.message}. Check the console and ensure 'windborne_data_with_weather.json' exists in the same folder as index.html.</p>`;
        });

    // 3. Function to Plot Balloon Data
    //---------------------------------
    function plotBalloonData(balloonPoints) {
        if (!balloonPoints || balloonPoints.length === 0) {
            console.log("No points to plot.");
            return;
        }

        infoPanel.innerHTML = '<h2>Balloon & Weather Details</h2><p>Click on a balloon data point on the map to see details here.</p>'; // Reset info panel

        // --- Group points by source_file to draw separate polylines for each hour's data ---
        // This is a simple way to represent "paths". You might refine this.
        const pathsByFile = {};
        balloonPoints.forEach(point => {
            if (!pathsByFile[point.source_file]) {
                pathsByFile[point.source_file] = [];
            }
            // Ensure lat/lon are valid numbers
            if (typeof point.latitude === 'number' && typeof point.longitude === 'number') {
                 pathsByFile[point.source_file].push([point.latitude, point.longitude]);
            }
        });

        const pathColors = ['blue', 'red', 'green', 'purple', 'orange', 'brown', 'teal', 'magenta'];
        let colorIndex = 0;

        for (const fileName in pathsByFile) {
            const pathCoords = pathsByFile[fileName];
            if (pathCoords.length > 1) { // Need at least 2 points for a line
                L.polyline(pathCoords, { color: pathColors[colorIndex % pathColors.length], weight: 3 })
                    .addTo(map)
                    .bindTooltip(`Path from ${fileName}`);
                colorIndex++;
            }
        }
        
        // --- Add individual markers for each point with popups/info display ---
        balloonPoints.forEach(point => {
            // Ensure lat/lon are valid numbers
            if (typeof point.latitude !== 'number' || typeof point.longitude !== 'number') {
                // console.warn("Skipping point with invalid lat/lon:", point);
                return; 
            }

            const marker = L.circleMarker([point.latitude, point.longitude], {
                radius: 5,
                fillColor: "#ff7800",
                color: "#000",
                weight: 1,
                opacity: 1,
                fillOpacity: 0.8
            }).addTo(map);

            marker.on('click', function() {
                displayPointInfo(point);
                map.setView([point.latitude, point.longitude], Math.max(map.getZoom(), 7)); // Zoom to point
            });
        });

        // Fit map to the bounds of all plotted points if there are any valid points
        const validCoords = balloonPoints.filter(p => typeof p.latitude === 'number' && typeof p.longitude === 'number')
                                     .map(p => [p.latitude, p.longitude]);
        if (validCoords.length > 0) {
            map.fitBounds(L.latLngBounds(validCoords));
        }
         infoPanel.innerHTML += '<p>Data plotted. Click markers for details.</p>';
    }

    // 4. Function to Display Point Information
    //-----------------------------------------
    function displayPointInfo(point) {
        let htmlContent = `
            <h2>Balloon & Weather Details</h2>
            <div class="info-item"><strong>Timestamp (UTC):</strong> ${point.timestamp_utc}</div>
            <div class="info-item"><strong>Source File:</strong> ${point.source_file}</div>
            <div class="info-item"><strong>Latitude:</strong> ${point.latitude.toFixed(4)}</div>
            <div class="info-item"><strong>Longitude:</strong> ${point.longitude.toFixed(4)}</div>
            <div class="info-item"><strong>Altitude (km):</strong> ${point.altitude.toFixed(2)}</div>
            <div class="info-item"><strong>Ground Speed (km/h):</strong> ${point.ground_speed_kmh !== null ? point.ground_speed_kmh : 'N/A'}</div>
            <div class="info-item"><strong>Bearing (°):</strong> ${point.bearing_deg !== null ? point.bearing_deg : 'N/A'}</div>
            <hr>
            <h3>Weather Data (if available):</h3>
        `;

        if (point.weather) {
            const weather = point.weather;
            htmlContent += `
                <div class="info-item"><strong>Weather Timestamp (UTC):</strong> ${weather.data_timestamp_utc}</div>
                <div class="info-item"><strong>Description:</strong> ${weather.weather_description || 'N/A'}</div>
                <div class="info-item"><strong>Temperature:</strong> ${weather.temperature_celsius !== null ? weather.temperature_celsius + ' °C' : 'N/A'}</div>
                <div class="info-item"><strong>Pressure:</strong> ${weather.pressure_hpa !== null ? weather.pressure_hpa + ' hPa' : 'N/A'}</div>
                <div class="info-item"><strong>Wind Speed:</strong> ${weather.wind_speed_mps !== null ? weather.wind_speed_mps + ' m/s' : 'N/A'}</div>
                <div class="info-item"><strong>Wind Direction:</strong> ${weather.wind_direction_deg !== null ? weather.wind_direction_deg + ' °' : 'N/A'}</div>
                <div class="info-item"><strong>Wind Gust:</strong> ${weather.wind_gust_mps !== null ? weather.wind_gust_mps + ' m/s' : 'N/A'}</div>
                <div class="info-item"><small>Time diff. to balloon point: ${weather.time_diff_to_actual_seconds}s</small></div>
            `;
            // To show correlation: You could try to visually represent the wind vector here,
            // e.g., an arrow icon rotated by weather.wind_direction_deg.
            // Or, if the balloon has a bearing_deg, you can compare it textually.
             if (point.bearing_deg !== null && weather.wind_direction_deg !== null) {
                const diff = Math.abs(point.bearing_deg - weather.wind_direction_deg);
                const angleDiff = Math.min(diff, 360 - diff); // Difference in degrees (0-180)
                htmlContent += `<div class="info-item"><strong>Balloon Bearing vs Wind Dir.:</strong> Differs by ~${angleDiff.toFixed(0)}°</div>`;
            }

        } else {
            htmlContent += "<p>No weather data fetched for this point (or API key issue).</p>";
        }
        infoPanel.innerHTML = htmlContent;
    }
});