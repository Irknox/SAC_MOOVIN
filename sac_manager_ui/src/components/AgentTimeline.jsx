import React, { useState } from "react";
import ToolOutput from "./ToolOutput";




const AgentTimeline = ({ actions, getToolOutput }) => {
  const [hoveredItem, setHoveredItem] = useState(null);

  const renderTimelineItem = (action, index) => {
    let label = null;
    let extra = null;

    if (action.type === "function_call") {
      const isHandoff = action.name?.startsWith("transfer_to_");
      if (isHandoff) {
        label = `Handoff: ${action.name.replace("transfer_to_", "")}`;
      } else {
        label = `Tool: ${action.name}`;
          
        const result = getToolOutput(action.call_id);   
        console.log("Herramienta usada:", action.name, "salida de la herramienta", result);     
        extra = result && (
          <div className="relative">
            <div
              className="text-sm text-gray-400 mt-1 cursor-pointer hover:text-blue-400"
              onMouseEnter={() => setHoveredItem(index)}
              onMouseLeave={() => setHoveredItem(null)}
            >
              Ver resultado
            </div>
            {hoveredItem === index && (
              <div className="fixed z-1000 max-h-auto mt-1 bg-white dark:bg-gray-800 rounded shadow text-xs text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700 ">
                <ToolOutput tool={action.name} output={result} />
              </div>
            )}
          </div>
        );
      }
    } else if (action.type === "message") {        
      label = "Respuesta del Agente";
      extra = (
        <div className="relative">
          <div
            className="text-sm text-gray-400 mt-1 cursor-pointer hover:text-blue-400"
            onMouseEnter={() => setHoveredItem(index)}
            onMouseLeave={() => setHoveredItem(null)}
          >
            Ver respuesta
          </div>
          {hoveredItem === index && (
            <div className="absolute z-10 mt-1 p-3 w-72 bg-white dark:bg-gray-800 rounded shadow text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              {action.content?.[0]?.text}
            </div>
          )}
        </div>
      );
    }

    if (!label) return null;
    return (
      <li key={index} className="relative mb-6 sm:mb-0">
        <div className="flex items-center">
          <div className="z-10 flex items-center justify-center w-6 h-6 bg-blue-100 rounded-full ring-0 ring-white dark:bg-blue-900 sm:ring-8 dark:ring-gray-900 shrink-0">
            <svg
              className="w-2.5 h-2.5 text-blue-800 dark:text-blue-300"
              xmlns="http://www.w3.org/2000/svg"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path d="M20 4a2 2 0 0 0-2-2h-2V1a1 1 0 0 0-2 0v1h-3V1a1 1 0 0 0-2 0v1H6V1a1 1 0 0 0-2 0v1H2a2 2 0 0 0-2 2v2h20V4Z" />
            </svg>
          </div>
          <div className="hidden sm:flex w-full bg-gray-200 h-0.5 dark:bg-gray-700"></div>
        </div>
        <div className="mt-3 sm:pe-8">
          <h4 className="text-base font-semibold text-gray-900 dark:text-white">
            {label}
          </h4>
          {extra}
        </div>
      </li>
    );
  };

  return (
    <div className="flex justify-center h-full pt-2">
      <ol className="sm:flex">
        {actions.length ? (
          actions.map(renderTimelineItem)
        ) : (
          <li>No hay acciones del agente</li>
        )}
      </ol>
    </div>
  );
};

export default AgentTimeline;
