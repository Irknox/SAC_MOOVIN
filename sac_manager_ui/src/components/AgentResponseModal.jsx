// Refactor del timeline del agente con hover en respuesta y nuevo layout
import { useState, useEffect } from "react";
import AgentTimeline from "./AgentTimeline";

const AgentResponseModal = ({ entry, onClose, msg_selected }) => {
  const [parsedContext, setParsedContext] = useState({});
  const [agentRun, setAgentRun] = useState([]);
  const [hoveredItem, setHoveredItem] = useState(null);
  const [inputItems, setInputItems] = useState([]);

  if (!entry) return null;

  useEffect(() => {
    try {
      const firstParse = JSON.parse(entry.contexto);
      const raw = JSON.parse(firstParse);
      setParsedContext(raw);
      const items = raw.input_items;
      const lastIndex = items.length - 1;
      let startIndex = lastIndex - 1;
      while (startIndex >= 0 && items[startIndex].role !== "user") {
        startIndex--;
      }
      const inputItems =
        startIndex >= 0
          ? items.slice(startIndex, lastIndex + 1)
          : [items[lastIndex]];
      setInputItems(inputItems);

      const filteredItems = inputItems.filter((action) => {
        return action.type === "function_call" || action.type === "message";
      });
      setAgentRun(filteredItems);
    } catch (e) {
      console.error("\u274C Error al parsear el contexto:", e);
    }
  }, [entry]);

  const agent = parsedContext.current_agent || "Desconocido";
  const userEnv = parsedContext.context?.user_env || {};

  const getToolOutput = (call_id) => {
    const outputObj = inputItems.find(
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
      <div
        className="bg-white dark:bg-gray-800 max-w-[90vw] w-[80vw] rounded-lg max-h-[90vh] h-[90vh] p-6 shadow-xl relative overflow-hidden flex flex-col justify-center items-center"
      >
        <h2 className="text-xl font-semibold mb-4">Detalles del Proceso</h2>
        <button
          className="absolute top-4 right-6 text-gray-500 hover:text-red-600"
          onClick={onClose}
        >
          ✕
        </button>

        <div
          className="grid grid-cols-[25%_50%_24%] grid-rows-[20%_40%_20%] h-full w-full"
        >
          <div className="col-start-1 col-end-2 row-start-1 row-end-2 flex-col text-center">
            <h2 className="font-semibold text-lg">Agente que respondió</h2>
            <p className="text-sm">{agent}</p>
          </div>

          <div
            className="col-start-1 col-end-4 row-start-2 row-end-3 flex-col"
          >
            <h2 className="font-semibold text-center text-lg">
              Acciones del Agente
            </h2>
            <AgentTimeline actions={agentRun} getToolOutput={getToolOutput} />
          </div>

          <div
            className="col-start-1 col-end-2 row-start-3 row-end-4 flex-col"
          >
            <h3 className="font-semibold text-center p-3">
              Contexto del Usuario
            </h3>
            <pre className="bg-gray-100 dark:bg-gray-700 text-xs p-3 rounded whitespace-pre-wrap">
              {JSON.stringify(userEnv, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentResponseModal;
