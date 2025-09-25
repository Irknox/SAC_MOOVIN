"use client";

import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css"; // ok en cliente

const ToolOutput = ({ tool, output, visible = false, call }) => {
  // --- Refs y coords ---
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);

  console.log(
    "tool recibida",
    tool,
    "Output recibido en el tooloutput",
    output,
    "Call recibida:",
    call || "Ninguna fue recibida"
  );

  const mountErrorPanel = (output = {}, call = {}) => {
    console.log("Output recibido", output);

    const prettyKey = (k) =>
      k
        .replace(/_/g, " ")
        .replace(/([a-z])([A-Z])/g, "$1 $2")
        .replace(/\b\w/g, (c) => c.toUpperCase());

    const prettyVal = (v) => {
      if (v === null || v === undefined || v === "") return "N/A";
      if (
        typeof v === "string" ||
        typeof v === "number" ||
        typeof v === "boolean"
      )
        return String(v);
      try {
        return JSON.stringify(v, null, 2);
      } catch {
        return String(v);
      }
    };

    const entries = Object.entries(call || {})
      .filter(([, v]) => typeof v !== "function")
      .sort(([a], [b]) => a.localeCompare(b));

    return (
      <div
        className="flex flex-col z-[1000] w-full h-full rounded bg-gray-900 border border-gray-700 p-3"
        style={{ overflow: "hidden", width: "100%", padding: "10px" }}
      >
        {/* Encabezado de error */}
        <span className="flex flex-row items-center gap-2">
          <svg
            className="w-8 h-8 text-gray-800 dark:text-white"
            aria-hidden="true"
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            fill="#f94747ff"
            viewBox="0 0 24 24"
          >
            <path
              fillRule="evenodd"
              d="M2 12C2 6.477 6.477 2 12 2s10 4.477 10 10-4.477 10-10 10S2 17.523 2 12Zm11-4a1 1 0 1 0-2 0v5a1 1 0 1 0 2 0V8Zm-1 7a1 1 0 1 0 0 2h.01a1 1 0 1 0 0-2H12Z"
              clipRule="evenodd"
            />
          </svg>
          <p className="text-red-400">
            {output?.message || "Error al usar la herramienta"}
          </p>
        </span>

        {/* Datos usados en la llamada */}
        <div className="mt-4 space-y-1 flex justify-around">
          {entries.length === 0 ? (
            <p className="text-gray-300">
              No se recibieron parámetros en <code>call</code>.
            </p>
          ) : (
            entries.map(([k, v]) => (
              <p
                key={k}
                className="text-gray-200 break-words whitespace-pre-wrap"
              >
                <span className="text-gray-400">{prettyKey(k)}:</span>{" "}
                {typeof v === "object" && v !== null ? (
                  <pre className="inline whitespace-pre-wrap break-words align-middle">
                    {prettyVal(v)}
                  </pre>
                ) : (
                  <span>{prettyVal(v)}</span>
                )}
              </p>
            ))
          )}
        </div>
      </div>
    );
  };

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
    return output.status === "error" ? (
      mountErrorPanel(output, call)
    ) : (
      <div
        className="flex-col z-[1000] w-full rounded bg-gray-900 text-white border border-gray-700"
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
            {Array.isArray(output?.timeline) &&
              output.timeline.map((item, idx) => (
                <tr
                  key={idx}
                  className="border-b border-gray-800 hover:bg-gray-800"
                >
                  <td className="px-2 py-1 whitespace-nowrap">
                    {item.dateUser}
                  </td>
                  <td className="px-2 py-1 whitespace-nowrap">{item.status}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    );
  } else if (tool === "send_current_delivery_address") {
    return output.status === "error" ? (
      mountErrorPanel(output, call)
    ) : (
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
    return output.status === "error" ? (
      mountErrorPanel(output, call)
    ) : (
      <div className="max-h-100 z-[1000] max-w-auto bg-gray-900 p-2 text-gray-200 border border-gray-700 text-xs">
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
    return output.status === "error" ? (
      mountErrorPanel(output, call)
    ) : (
      <div className="max-h-100 max-w-auto bg-gray-900 p-2 text-gray-200 border border-gray-700 text-xs">
        <pre>{output.delivery_address}</pre>
        El paquete ha sido cambiado en la API de Desarrollo de Moovin.
      </div>
    );
  } else if (tool === "remember_more") {
    const raw = output ?? {};

    const sessions = Object.entries(raw)
      .filter(([k, v]) => k.startsWith("sesion_") && v)
      .map(([id, v]) => ({ id, ...v }));

    sessions.sort(
      (a, b) =>
        new Date(b.fecha.replace(" ", "T")) -
        new Date(a.fecha.replace(" ", "T"))
    );

    const session_count = sessions.length;

    return output.status === "error" ? (
      mountErrorPanel(output, call)
    ) : (
      <div className="max-h-100 max-w-auto bg-gray-900 p-2 text-gray-200 border border-gray-700 text-xs">
        {session_count === 0 ? (
          <p>No hay sesiones para mostrar.</p>
        ) : (
          sessions.map(({ id, cuando, fecha, resumen }) => (
            <div key={id} className="mb-3">
              <h1 className="font-semibold">{cuando}</h1>
              <h2 className="text-gray-400">Fecha: {fecha}</h2>
              <p className="mt-1">{resumen}</p>
            </div>
          ))
        )}
      </div>
    );
  } else if (tool === "get_likely_package_timelines") {
    return output.status === "error" ? (
      mountErrorPanel(output, call)
    ) : (
      <div className="max-h-100 max-w-auto bg-gray-900 p-2 text-gray-200 border border-gray-700 text-xs">
        <h1>
          Paquetes parecidos a {output.package || "Paquete no disponible"}
        </h1>

        {Array.isArray(output?.similares) && output.similares.length > 0 ? (
          output.similares.map((p, i) => (
            <div
              key={`${p.package_id}-${i}`}
              className="mt-3 border-t border-gray-700 pt-2 flex flex-row justify-around"
            >
              <h2 className="font-semibold">Paquete {p.package_id}</h2>
              <p className="text-gray-400">
                Último estado: {p.last_status || "Desconocido"}
              </p>
            </div>
          ))
        ) : (
          <p className="text-gray-400 mt-2">No hay paquetes similares.</p>
        )}
      </div>
    );
  } else if (
    tool === "pickup_ticket" ||
    tool === "request_electronic_receipt_ticket" ||
    tool === "package_damaged_ticket" ||
    tool === "escalate_to_human"
  ) {
    const devUrl =
      typeof output?.DevURL === "string" && output.DevURL.trim().length > 0
        ? output.DevURL.trim()
        : null;

    return output.status === "error" ? (
      mountErrorPanel(output, call)
    ) : (
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          justifyItems: "center",
          alignContent: "center",
        }}
        className="max-h-100 max-w-auto bg-gray-900 p-2 text-gray-300 border border-gray-700 text-xs"
      >
        <p style={{ alignSelf: "center" }}>
          Ticket creado: {output.TicketNumber || "No disponible"}
        </p>

        {devUrl ? (
          <a
            href={devUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="px-5 py-1 text-sm font-medium w-25 text-center inline-flex items-center text-white bg-blue-700 rounded-lg hover:bg-blue-800 focus:ring-2 focus:outline-none focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
          >
            <svg
              className="w-3 h-3 me-2"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              fill="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                fillRule="evenodd"
                d="M11.403 5H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-6.403a3.01 3.01 0 0 1-1.743-1.612l-3.025 3.025A3 3 0 1 1 9.99 9.768l3.025-3.025A3.01 3.01 0 0 1 11.403 5Z"
                clipRule="evenodd"
              />
              <path
                fillRule="evenodd"
                d="M13.232 4a1 1 0 0 1 1-1H20a1 1 0 0 1 1 1v5.768a1 1 0 1 1-2 0V6.414l-6.182 6.182a1 1 0 0 1-1.414-1.414L17.586 5h-3.354a1 1 0 0 1-1-1Z"
                clipRule="evenodd"
              />
            </svg>
            Zoho
          </a>
        ) : (
          <button
            type="button"
            disabled
            title="Sin enlace disponible"
            className="px-5 py-1 text-sm font-medium w-25 text-center inline-flex items-center text-white bg-gray-500 cursor-not-allowed rounded-lg"
          >
            <svg
              className="w-3 h-3 me-2"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              fill="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                fillRule="evenodd"
                d="M11.403 5H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-6.403a3.01 3.01 0 0 1-1.743-1.612l-3.025 3.025A3 3 0 1 1 9.99 9.768l3.025-3.025A3.01 3.01 0 0 1 11.403 5Z"
                clipRule="evenodd"
              />
              <path
                fillRule="evenodd"
                d="M13.232 4a1 1 0 0 1 1-1H20a1 1 0 0 1 1 1v5.768a1 1 0 1 1-2 0V6.414l-6.182 6.182a1 1 0 0 1-1.414-1.414L17.586 5h-3.354a1 1 0 0 1-1-1Z"
                clipRule="evenodd"
              />
            </svg>
            Zoho
          </button>
        )}
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
