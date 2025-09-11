import React, { useState, useEffect } from "react";
import AgentTimeline from "./AgentTimeline";

const AgentResponseModal = ({ ctx, entry, onClose, msg_selected }) => {
  const [agentRun, setAgentRun] = useState([]);
  const [hoveredItem, setHoveredItem] = useState(null);

  if (!entry) return null;

  useEffect(() => {
    try {
      const base = Array.isArray(entry?.steps_taken) ? entry.steps_taken : [];
      const merged = [...base];

      if (entry?.agent_message) {
        const alreadyHasAgentMessage = merged.some(
          (it) => it?.agent && it?.content === entry.agent_message.content
        );

        if (!alreadyHasAgentMessage) merged.push(entry.agent_message);
      }

      if (entry?.user_message) {
        const alreadyHasUserMessage = merged.some((it) => it?.role === "user");
        if (!alreadyHasUserMessage) merged.unshift(entry.user_message);
      }
      setAgentRun(merged);
    } catch (e) {
      console.error("❌ Error al armar timeline:", e);
    }
  }, [entry]);

  const agent = entry.responded_by || "General Agent";
  const userEnv = ctx.user_env || {};

  const getToolOutput = (call_id) => {
    const outputObj = agentRun.find(
      (item) => item.type === "function_call_output" && item.call_id === call_id
    );
    if (!outputObj) return null;
    try {
      return JSON.stringify(
        typeof outputObj.output === "string"
          ? JSON.parse(outputObj.output.replace(/'/g, '"'))
          : outputObj.output,
        null,
        2
      );
    } catch (e) {
      return outputObj.output;
    }
  };

  return (
    <div className="fixed inset-0 bg-gray/10 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 max-w-[80vw] w-[80vw] rounded-lg max-h-[80vh] h-[75vh] p-6 shadow-xl relative  flex flex-col justify-center items-center">
        <h2 className="text-xl font-semibold mb-4">Detalles del Proceso</h2>
        <button
          className="absolute top-4 right-6 text-gray-500 hover:text-red-600 cursor-pointer"
          onClick={onClose}
        >
          <svg
            className="w-6 h-6 text-gray-800 dark:text-white"
            aria-hidden="true"
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              fillRule="evenodd"
              d="M2 12C2 6.477 6.477 2 12 2s10 4.477 10 10-4.477 10-10 10S2 17.523 2 12Zm7.707-3.707a1 1 0 0 0-1.414 1.414L10.586 12l-2.293 2.293a1 1 0 1 0 1.414 1.414L12 13.414l2.293 2.293a1 1 0 0 0 1.414-1.414L13.414 12l2.293-2.293a1 1 0 0 0-1.414-1.414L12 10.586 9.707 8.293Z"
              clipRule="evenodd"
            />
          </svg>
        </button>

        <div className="grid grid-cols-[30%_40%_30%] grid-rows-[45%_1fr] h-full w-full">
          <div className="col-start-1 col-end-2 row-start-1 row-end-2 flex-col text-center">
            <h2 className="font-semibold text-lg">Mensaje del Usuario</h2>
            <p className="text-sm">{entry.user_message.content}</p>
          </div>

          <div className="col-start-3 col-end-4 row-start-1 row-end-2 flex-col text-center">
            <h2 className="font-semibold text-lg">Agente que respondió</h2>
            <p className="text-sm">{entry.agent_message.agent}</p>
          </div>

          <div
            className="col-start-1 col-end-4 row-start-2 row-end-3 flex-col"
            style={{
              display: "flex",
              alignItems: "center",
              width: "100%",
            }}
          >
            <h2 className="font-semibold text-center text-lg">
              Acciones del Agente
            </h2>
            <AgentTimeline actions={agentRun} getToolOutput={getToolOutput} />
          </div>

          <div
            style={{
              overflow: "hidden",
              display: "grid",
              gridTemplate: "10% 10% 10% 1fr / 1fr 1fr",
              padding:"5px"
            }}
            className="col-start-2 col-end-3 row-start-1 row-end-1 flex-col bg-gray-900 rounded-md m-3"
          >
            <h1
              className="text-gray-400 text-bold text-center text-[clamp(0.7rem,0.05vw+0.65rem,0.9rem)]"
              style={{ gridRow: "1", gridColumn: "1/3" }}
            >
              Datos pre-cargados
            </h1>
            <div
              style={{
                overflow: "hidden",
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                gridRow: "2",
                gridColumn: "1 / 3",
              }}
            >
              <svg
                className="w-4 h-4 text-gray-800 dark:text-white"
                aria-hidden="true"
                xmlns="http://www.w3.org/2000/svg"
                fill="#2b5cd8ff"
                viewBox="0 0 24 24"
              >
                <path
                  fillRule="evenodd"
                  d="M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm-2 9a4 4 0 0 0-4 4v1a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-1a4 4 0 0 0-4-4h-4Z"
                  clipRule="evenodd"
                />
              </svg>
              <p className=" text-[clamp(0.7rem,0.05vw+0.65rem,0.9rem)]">
                {userEnv.username}
              </p>
            </div>

            <div
              style={{
                overflow: "hidden",
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                gridRow: "3",
                gridColumn: "1",
              }}
            >
              <svg
                className="w-4 h-4 text-gray-800 dark:text-white"
                aria-hidden="true"
                xmlns="http://www.w3.org/2000/svg"
                fill="#2bd85cff"
                viewBox="0 0 24 24"
              >
                <path d="M7.978 4a2.553 2.553 0 0 0-1.926.877C4.233 6.7 3.699 8.751 4.153 10.814c.44 1.995 1.778 3.893 3.456 5.572 1.68 1.679 3.577 3.018 5.57 3.459 2.062.456 4.115-.073 5.94-1.885a2.556 2.556 0 0 0 .001-3.861l-1.21-1.21a2.689 2.689 0 0 0-3.802 0l-.617.618a.806.806 0 0 1-1.14 0l-1.854-1.855a.807.807 0 0 1 0-1.14l.618-.62a2.692 2.692 0 0 0 0-3.803l-1.21-1.211A2.555 2.555 0 0 0 7.978 4Z" />
              </svg>
              <p className=" text-[clamp(0.7rem,0.05vw+0.65rem,0.9rem)]">
                {userEnv.phone}
              </p>
            </div>

            <div
              style={{
                overflow: "hidden",
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                gridRow: "3",
                gridColumn: "2",
              }}
            >
              <svg
                className="w-5 h-4 text-gray-800 dark:text-white"
                aria-hidden="true"
                xmlns="http://www.w3.org/2000/svg"
                fill="#cad82bff"
                viewBox="0 0 24 24"
              >
                <path
                  fillRule="evenodd"
                  d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2ZM7.99 9a1 1 0 0 1 1-1H9a1 1 0 0 1 0 2h-.01a1 1 0 0 1-1-1ZM14 9a1 1 0 0 1 1-1h.01a1 1 0 1 1 0 2H15a1 1 0 0 1-1-1Zm-5.506 7.216A5.5 5.5 0 0 1 6.6 13h10.81a5.5 5.5 0 0 1-8.916 3.216Z"
                  clipRule="evenodd"
                />
              </svg>

              <p className=" text-[clamp(0.7rem,0.05vw+0.65rem,0.9rem)]">
                {userEnv.emotional_state}
              </p>
            </div>
            <div
              style={{
                gridRow: "4",
                gridColumn: "1/3",
                fontSize: "x-small",
                alignContent: "center",
              }}
            >
              {Array.isArray(userEnv.paquetes) ? (
                userEnv.paquetes.map((paquete, index) => (
                  <React.Fragment
                    key={
                      paquete?.tracking ?? `${index}-${paquete?.fecha ?? "s/n"}`
                    }
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                        paddingBottom: "5px",
                        justifySelf: "center",
                      }}
                    >
                      <span style={{ fontWeight: 600 }}>{index + 1}</span>
                      <svg
                        className="w-4 h-4 text-gray-800 dark:text-white"
                        aria-hidden="true"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path d="M12.013 6.175 7.006 9.369l5.007 3.194-5.007 3.193L2 12.545l5.006-3.193L2 6.175l5.006-3.194 5.007 3.194ZM6.981 17.806l5.006-3.193 5.006 3.193L11.987 21l-5.006-3.194Z" />
                        <path d="m12.013 12.545 5.006-3.194-5.006-3.176 4.98-3.194L22 6.175l-5.007 3.194L22 12.562l-5.007 3.194-4.98-3.211Z" />
                      </svg>
                      <p className="text-center">{paquete.tracking}</p>
                    </div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                        paddingBottom: "5px",
                        justifySelf: "center",
                      }}
                    >
                      <svg
                        className="w-4 h-4 text-gray-800 dark:text-white"
                        aria-hidden="true"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          fillRule="evenodd"
                          d="M2 12C2 6.477 6.477 2 12 2s10 4.477 10 10-4.477 10-10 10S2 17.523 2 12Zm9.408-5.5a1 1 0 1 0 0 2h.01a1 1 0 1 0 0-2h-.01ZM10 10a1 1 0 1 0 0 2h1v3h-1a1 1 0 1 0 0 2h4a1 1 0 1 0 0-2h-1v-4a1 1 0 0 0-1-1h-2Z"
                          clipRule="evenodd"
                        />
                      </svg>

                      <p className="text-gray-400 text-[clamp(0.3rem,0.02vw+0.55rem,0.9rem)]">
                        {paquete.estado}
                      </p>
                      <svg
                        className="w-4 h-4 text-gray-800 dark:text-white"
                        aria-hidden="true"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          fillRule="evenodd"
                          d="M5 5a1 1 0 0 0 1-1 1 1 0 1 1 2 0 1 1 0 0 0 1 1h1a1 1 0 0 0 1-1 1 1 0 1 1 2 0 1 1 0 0 0 1 1h1a1 1 0 0 0 1-1 1 1 0 1 1 2 0 1 1 0 0 0 1 1 2 2 0 0 1 2 2v1a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a2 2 0 0 1 2-2ZM3 19v-7a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Zm6.01-6a1 1 0 1 0-2 0 1 1 0 0 0 2 0Zm2 0a1 1 0 1 1 2 0 1 1 0 0 1-2 0Zm6 0a1 1 0 1 0-2 0 1 1 0 0 0 2 0Zm-10 4a1 1 0 1 1 2 0 1 1 0 0 1-2 0Zm6 0a1 1 0 1 0-2 0 1 1 0 0 0 2 0Zm2 0a1 1 0 1 1 2 0 1 1 0 0 1-2 0Z"
                          clipRule="evenodd"
                        />
                      </svg>
                      <p
                        className="text-gray-400 text-[clamp(0.3rem,0.02vw+0.55rem,0.9rem)]"
                        style={{ textAlign: "center" }}
                      >
                        {paquete.fecha}
                      </p>
                    </div>
                  </React.Fragment>
                ))
              ) : (
                <p className="text-center text-sm p-2">
                  El usuario no tiene paquetes
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentResponseModal;
