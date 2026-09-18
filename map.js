/* ================= MAP + LOCATION ================= */

let riskMap;
let currentLocationMarker;

// name -> { circle, level, lat, lng }
const riskZones = {};

const ZONE_COLORS = {
    green: "#2e9e46",
    orange: "#e2a300",
    red: "#d63031"
};

const ZONE_LABELS = {
    green: "🟢 Normal Zone",
    orange: "🟡 Moderate Risk Zone",
    red: "🔴 High Risk Zone"
};

const ZONE_DEFAULT_MESSAGES = {
    green: "Water-quality signals are currently normal.",
    orange: "Some signals require monitoring.",
    red: "Potential contamination risk detected."
};


/* ================= FIX: default marker icons =================
   Leaflet's default marker images can silently fail to load when the
   library is pulled in from a CDN, because it tries to guess the image
   path from the currently running script tag. Pointing it explicitly at
   the CDN's own image folder avoids the classic "marker is a broken
   image / invisible icon" bug.
================================================================= */
if (window.L) {
    L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png"
    });
}


/* ================= CREATE MAP ================= */

document.addEventListener("DOMContentLoaded", function () {

    const mapEl = document.getElementById("riskMap");
    if (!mapEl) {
        return; // this page has no map on it — nothing to do
    }

    riskMap = L.map("riskMap").setView([16.5062, 80.6480], 12);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
        maxZoom: 19
    }).addTo(riskMap);

    // These names line up with the "Area A–D" cards in the dashboard, so
    // clicking a card can find and highlight the matching zone here.
    addRiskZone("Area A", 16.4900, 80.6300, "green");
    addRiskZone("Area B", 16.5000, 80.6600, "orange");
    addRiskZone("Area C", 16.5200, 80.6750, "red");
    addRiskZone("Area D", 16.4780, 80.6550, "green");

});


/* ================= ADD / UPDATE RISK ZONES ================= */

function buildZonePopup(name, level, message) {
    return (
        "<strong>" + name + " — " + (ZONE_LABELS[level] || "") + "</strong><br><br>" +
        (message || ZONE_DEFAULT_MESSAGES[level] || "")
    );
}

function addRiskZone(name, latitude, longitude, level) {

    const color = ZONE_COLORS[level] || ZONE_COLORS.green;

    const circle = L.circle([latitude, longitude], {
        color: color,
        fillColor: color,
        fillOpacity: 0.35,
        radius: 1200
    }).addTo(riskMap);

    circle.bindPopup(buildZonePopup(name, level));

    riskZones[name] = {
        circle: circle,
        level: level,
        lat: latitude,
        lng: longitude
    };

}

// Called from dashboard.html whenever a citizen report or the fake-data
// engine changes an area's risk level, so the map stays in sync.
function setZoneRisk(name, level, message) {

    const zone = riskZones[name];
    if (!zone) return;

    const color = ZONE_COLORS[level] || ZONE_COLORS.green;

    zone.circle.setStyle({ color: color, fillColor: color });
    zone.circle.setPopupContent(buildZonePopup(name, level, message));
    zone.level = level;

}

// Pans/zooms to a zone and opens its popup — used when an Area card is
// clicked on the dashboard, so the map visibly highlights that zone.
function focusZone(name) {

    const zone = riskZones[name];
    if (!zone || !riskMap) return;

    riskMap.setView([zone.lat, zone.lng], 15);
    zone.circle.openPopup();

}


/* ================= CURRENT LOCATION ================= */

function detectLocation() {

    const locationText = document.getElementById("locationText");

    if (!navigator.geolocation) {
        locationText.innerText = "Geolocation is not supported by your browser.";
        return;
    }

    locationText.innerText = "📍 Detecting your location...";

    navigator.geolocation.getCurrentPosition(

        /* SUCCESS */

        function (position) {

            const latitude = position.coords.latitude;
            const longitude = position.coords.longitude;

            locationText.innerHTML =
                "Latitude: " + latitude.toFixed(5) + "<br>" +
                "Longitude: " + longitude.toFixed(5);

            if (currentLocationMarker && riskMap) {
                riskMap.removeLayer(currentLocationMarker);
            }

            if (riskMap) {

                currentLocationMarker = L.marker([latitude, longitude])
                    .addTo(riskMap)
                    .bindPopup("<strong>📍 Your Current Location</strong>")
                    .openPopup();

                riskMap.setView([latitude, longitude], 15);

            }

        },

        /* ERROR */

        function (error) {

            if (error.code === 1) {
                locationText.innerText = "❌ Location permission denied.";
            } else if (error.code === 2) {
                locationText.innerText = "❌ Location unavailable.";
            } else if (error.code === 3) {
                locationText.innerText = "❌ Location request timed out.";
            } else {
                locationText.innerText = "❌ Unable to detect location.";
            }

        },

        /* OPTIONS */

        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        }

    );

}