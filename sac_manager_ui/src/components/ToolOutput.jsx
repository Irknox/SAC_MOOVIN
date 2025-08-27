"use client";

import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css"; // ok en cliente
import ChangeDeliveryOutputView from "./ChangeDeliveryOutputView";

const ToolOutput = ({ tool, output, visible = false,call }) => {
  console.log("Llamada recibida", call);

  // --- Refs y coords ---
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);

  const lat =
    output?.location_data?.latitude !== undefined
      ? Number(output.location_data.latitude)
      : null;
  const lng =
    output?.location_data?.longitude !== undefined
      ? Number(output.location_data.longitude)
      : null;

  useEffect(() => {
    if (
      tool !== "send_current_delivery_address" &&
      tool !== "send_delivery_address_requested"
    )
      return;

    if (!mapContainerRef.current) return;
    if (lat == null || lng == null || Number.isNaN(lat) || Number.isNaN(lng))
      return;

    let mounted = true;
    (async () => {
      const L = (await import("leaflet")).default;

      await import("leaflet-defaulticon-compatibility");
      await import(
        "leaflet-defaulticon-compatibility/dist/leaflet-defaulticon-compatibility.css"
      );

      if (!mounted) return;

      if (!mapRef.current) {
        mapRef.current = L.map(mapContainerRef.current).setView([lat, lng], 15);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
        }).addTo(mapRef.current);
        markerRef.current = L.marker([lat, lng]).addTo(mapRef.current);
      }
    })();

    return () => {
      mounted = false;
    };
  }, [tool, lat, lng]);

  useEffect(() => {
    if (tool !== "send_current_delivery_address") return;
    if (visible && mapRef.current) {
      requestAnimationFrame(() => {
        try {
          mapRef.current.invalidateSize();
        } catch {}
      });
    }
  }, [visible, tool]);

  if (tool === "get_package_timeline") {
    return (
      <div
        className="flex-col z-[1000] w-full rounded bg-gray-900 text-gray-200 border border-gray-700"
        style={{ overflow: "hidden", width: "100%" }}
      >
        <div>
          <p>Nombre en paquete: {output["Dueño del Paquete"]}</p>
          <p>Telefono en paquete: {output["Numero de Telefono"]}</p>
          <p>
            Tienda donde se compro:{" "}
            {output["Tienda donde se compro el paquete"] ||
              "Tienda Desconocida"}{" "}
          </p>
        </div>

        <table
          style={{ fontSize: "smaller" }}
          className="w-full text-sm text-left"
        >
          <thead>
            <tr className="border-b border-gray-600">
              <th className="px-1 py-1">FECHA</th>
              <th className="px-1 py-1">ESTADO</th>
            </tr>
          </thead>
          <tbody>
            {output.timeline.map((item, idx) => (
              <tr
                key={idx}
                className="border-b border-gray-800 hover:bg-gray-800"
              >
                <td className="px-2 py-1 whitespace-nowrap">{item.dateUser}</td>
                <td className="px-2 py-1 whitespace-nowrap">{item.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  } else if (tool === "send_current_delivery_address") {
    return (
      <div className="max-h-100 z-[1000] max-w-auto bg-gray-900 p-2 text-gray-200 border border-gray-700 text-xs">
        <pre>{output.delivery_address}</pre>

        {output.error && visible ? (
          <div className=" text-red-300">
            Error: {""}
            <code>{output.error}</code>.
          </div>
        ) : (
          <div
            id="map_container"
            ref={mapContainerRef}
            style={{
              width: "100%",
              height: "320px",
              borderRadius: "8px",
              overflow: "hidden",
              marginTop: "8px",
            }}
          />
        )}
      </div>
    );
  } else if (tool === "send_delivery_address_requested") {
    return (
      <div className="max-h-100 max-w-auto bg-gray-900 p-2 text-gray-200 border border-gray-700 text-xs">
        <pre>{output["address pre info"]}</pre>
        <div
          id="map_container"
          ref={mapContainerRef}
          style={{
            width: "100%",
            height: "320px",
            borderRadius: "8px",
            overflow: "hidden",
            marginTop: "8px",
          }}
        />
        {(lat == null || lng == null) && (
          <div className="mt-2 text-red-300">
            Coordenadas no disponibles en <code>output.location_data</code>.
          </div>
        )}
      </div>
    );
  } else if (tool === "change_delivery_address") {
    return (
      <div className="max-h-100 max-w-auto bg-gray-900 p-2 text-gray-200 border border-gray-700 text-xs">
        <pre>{output.delivery_address}</pre>
        <ChangeDeliveryOutputView output={output} />
      </div>
    );
  } else {
    return (
      <div className="max-h-100 max-w-auto bg-gray-900 p-2 text-gray-200 border border-gray-700 text-xs">
        <pre>Vista de Herramienta no disponible aun</pre>
      </div>
    );
  }
};

export default ToolOutput;
