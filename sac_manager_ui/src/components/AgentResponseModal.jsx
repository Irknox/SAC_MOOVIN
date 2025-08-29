import { useState, useEffect } from "react";
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
    console.log("Valor de agent Run",agentRun);
    
    const outputObj = agentRun.find(
      (item) => item.type === "function_call_output" && item.call_id === call_id
    );
    console.log("Output Obj en el getToolOutput",outputObj);
    
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
      <div className="bg-white dark:bg-gray-800 max-w-[90vw] w-[80vw] rounded-lg max-h-[90vh] h-[90vh] p-6 shadow-xl relative  flex flex-col justify-center items-center">
        <h2 className="text-xl font-semibold mb-4">Detalles del Proceso</h2>
        <button
          className="absolute top-4 right-6 text-gray-500 hover:text-red-600"
          onClick={onClose}
        >
          ✕
        </button>

        <div className="grid grid-cols-[25%_50%_24%] grid-rows-[30%_40%_30%] h-full w-full">
          <div className="col-start-1 col-end-2 row-start-1 row-end-2 flex-col text-center">
            <h2 className="font-semibold text-lg">Mensaje del Usuario</h2>
            <p className="text-sm">{entry.user_message.content}</p>
          </div>
          <div className="col-start-2 col-end-3 row-start-1 row-end-2 flex-col text-center">
            <h2 className="font-semibold text-lg">Agente que respondió</h2>
            <p className="text-sm">{entry.agent_message.agent}</p>
          </div>

          <div className="col-start-1 col-end-4 row-start-2 row-end-3 flex-col">
            <h2 className="font-semibold text-center text-lg">
              Acciones del Agente
            </h2>
            <AgentTimeline actions={agentRun} getToolOutput={getToolOutput} />
          </div>

          <div
            style={{ overflow: "hidden" }}
            className="col-start-3 col-end-4 row-start-1 row-end-1 flex-col"
          >
            <h3 className="font-semibold text-center p-3">
              Contexto del Usuario
            </h3>
            <div
              style={{ overflow: "hidden", textAlign: "center" }}
              className="bg-gray-100 h-full dark:bg-gray-700 text-xs p-3 rounded whitespace-pre-wrap"
            >
              <div
                style={{
                  overflow: "hidden",
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                }}
              >
                {" "}
                <svg
                  className="text-gray-800 dark:text-white"
                  aria-hidden="true"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                  style={{ width: "1.2rem", padding: "3px" }}
                >
                  <path
                    fillRule="evenodd"
                    d="M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm-2 9a4 4 0 0 0-4 4v1a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-1a4 4 0 0 0-4-4h-4Z"
                    clipRule="evenodd"
                  />
                </svg>
                <p>{userEnv.username}</p>
              </div>
              <div
                style={{
                  overflow: "hidden",
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                }}
              >
                <svg
                  className="text-gray-800 dark:text-white"
                  aria-hidden="true"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                  style={{ width: "1.2rem", padding: "3px" }}
                >
                  <path d="M7.978 4a2.553 2.553 0 0 0-1.926.877C4.233 6.7 3.699 8.751 4.153 10.814c.44 1.995 1.778 3.893 3.456 5.572 1.68 1.679 3.577 3.018 5.57 3.459 2.062.456 4.115-.073 5.94-1.885a2.556 2.556 0 0 0 .001-3.861l-1.21-1.21a2.689 2.689 0 0 0-3.802 0l-.617.618a.806.806 0 0 1-1.14 0l-1.854-1.855a.807.807 0 0 1 0-1.14l.618-.62a2.692 2.692 0 0 0 0-3.803l-1.21-1.211A2.555 2.555 0 0 0 7.978 4Z" />
                </svg>
                <p>{userEnv.phone}</p>
              </div>

              <div
                style={{
                  overflow: "hidden",
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                }}
              >
                <svg
                  className="text-gray-800 dark:text-white"
                  aria-hidden="true"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                  style={{ width: "1.2rem", padding: "3px" }}
                >
                  <path
                    fillRule="evenodd"
                    d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2ZM7.99 9a1 1 0 0 1 1-1H9a1 1 0 0 1 0 2h-.01a1 1 0 0 1-1-1ZM14 9a1 1 0 0 1 1-1h.01a1 1 0 1 1 0 2H15a1 1 0 0 1-1-1Zm-5.506 7.216A5.5 5.5 0 0 1 6.6 13h10.81a5.5 5.5 0 0 1-8.916 3.216Z"
                    clipRule="evenodd"
                  />
                </svg>

                <p>{userEnv.emotional_state}</p>
              </div>
              <div>Paquetes: {JSON.stringify(userEnv.paquetes, null, 2)}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentResponseModal;
