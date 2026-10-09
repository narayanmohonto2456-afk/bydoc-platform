"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { Map as LeafletMap } from "leaflet";
import { apiRequest } from "@/lib/api";

type Clinic = {
  id: string; name: string; address: string; locality: string; district: string;
  state: string; latitude: number; longitude: number; distance_km: number;
};
type Point = { latitude: number; longitude: number };

const tileUrl = process.env.NEXT_PUBLIC_MAP_TILE_URL || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const attribution = process.env.NEXT_PUBLIC_MAP_ATTRIBUTION || "&copy; OpenStreetMap contributors";

export default function NearbyClinicsPage() {
  const [point, setPoint] = useState<Point | null>(null);
  const [clinics, setClinics] = useState<Clinic[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const mapElement = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<LeafletMap | null>(null);

  function findNearby() {
    if (!navigator.geolocation) {
      setError("Location is unavailable in this browser. Search by district on the appointments page.");
      return;
    }
    setBusy(true);
    setError("");
    navigator.geolocation.getCurrentPosition(
      async position => {
        const location = { latitude: position.coords.latitude, longitude: position.coords.longitude };
        try {
          const params = new URLSearchParams({
            latitude: String(location.latitude), longitude: String(location.longitude), radius_km: "15",
          });
          const found = await apiRequest<Clinic[]>(`/appointments/nearby-clinics/?${params}`);
          setPoint(location);
          setClinics(found);
          setSelected(null);
        } catch (cause) {
          setError(cause instanceof Error ? cause.message : "Could not find nearby clinics.");
        } finally {
          setBusy(false);
        }
      },
      () => {
        setError("Location was not shared. You can search by district on the appointments page.");
        setBusy(false);
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 },
    );
  }

  useEffect(() => {
    if (!point || !mapElement.current) return;
    let cancelled = false;
    import("leaflet").then(L => {
      if (cancelled || !mapElement.current) return;
      mapInstance.current?.remove();
      const map = L.map(mapElement.current, { scrollWheelZoom: false }).setView([point.latitude, point.longitude], 12);
      mapInstance.current = map;
      L.tileLayer(tileUrl, { attribution, maxZoom: 18 }).addTo(map);
      L.circleMarker([point.latitude, point.longitude], {
        radius: 8, color: "#215cb0", fillColor: "#5594ec", fillOpacity: 1,
      }).addTo(map).bindTooltip("Your approximate location");
      const bounds: [number, number][] = [[point.latitude, point.longitude]];
      for (const clinic of clinics) {
        const position: [number, number] = [clinic.latitude, clinic.longitude];
        L.circleMarker(position, {
          radius: 10, color: "#145b45", fillColor: "#22a36c", fillOpacity: 0.9,
        }).addTo(map).bindTooltip(clinic.name).on("click", () => setSelected(clinic.id));
        bounds.push(position);
      }
      if (bounds.length > 1) map.fitBounds(bounds, { padding: [36, 36], maxZoom: 14 });
    }).catch(() => { if (!cancelled) setError("The map could not load. The clinic list is still available below."); });
    return () => { cancelled = true; mapInstance.current?.remove(); mapInstance.current = null; };
  }, [point, clinics]);

  function focusClinic(clinic: Clinic) {
    setSelected(clinic.id);
    mapInstance.current?.flyTo([clinic.latitude, clinic.longitude], 14);
  }

  return <div className="shell nearby-page">
    <div className="booking-heading"><span className="eyebrow">Find care close to you</span><h1>Nearby clinics</h1>
      <p>Share your location to see active clinics with verified doctors accepting online bookings within 15 km. Your coordinates are used for this search and are not saved to your account.</p>
    </div>
    <div className="nearby-controls">
      <button className="button" type="button" onClick={findNearby} disabled={busy}>{busy ? "Finding clinics…" : point ? "Update my location" : "Use my location"}</button>
      <Link href="/appointments">Search by doctor or district instead</Link>
    </div>
    {error && <p className="message message-error" role="alert">{error}</p>}
    {point && <>
      <div className="nearby-map" ref={mapElement} role="img" aria-label="Map of nearby clinics" />
      <p className="dashboard-note">The map loads tiles from {tileUrl.includes("openstreetmap.org") ? "OpenStreetMap" : "the configured map provider"}; that provider can see the map area your browser requests. The clinic list below works independently of map tiles.</p>
      <h2>{clinics.length ? `${clinics.length} nearby clinic${clinics.length === 1 ? "" : "s"}` : "No matching clinics nearby"}</h2>
      {!clinics.length && <p>Try searching another district or check again later. Clinics without verified bookable doctors or map coordinates are not shown.</p>}
      <ul className="nearby-list">{clinics.map(clinic => <li key={clinic.id} className={selected === clinic.id ? "is-selected" : ""}>
        <button type="button" onClick={() => focusClinic(clinic)}><strong>{clinic.name}</strong><span>{clinic.distance_km.toFixed(1)} km away</span></button>
        <p>{clinic.address}, {clinic.locality}, {clinic.district}, {clinic.state}</p>
        <Link href={`/appointments?q=${encodeURIComponent(clinic.name)}`}>See doctors and appointments →</Link>
      </li>)}</ul>
    </>}
  </div>;
}
