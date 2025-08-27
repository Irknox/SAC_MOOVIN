import React, { useEffect, useState } from "react";

const PromptNav = ({ handlePromptSelect }) => {
  const [selectedType, setSelectedType] = useState("Seleccione el tipo");

  const handleTypeChange = (type) => {
    setSelectedType(type);
  };

  return (
    <>
      <div
        style={{
          gridRow: "1",
          gridColumn: "1",
          backgroundColor: "#f2f2f2ff",
          width: "100%",
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          borderBottom: "2px solid #0b39804f",
        }}
      >

        
        <form
          className="max-w-sm w-150 mx-auto"
          style={{
            display: "flex",
            flexDirection: "row",
            alignItems: "center",
          }}
        >
          <label
            htmlFor="types"
            className="block text-sm w-8 font-medium text-[var(--color-primary_blue)] dark:text-[var(--color-primary_blue)]"
          >
            Tipo
          </label>
          <select
            onChange={(e) => handleTypeChange(e.target.value)}
            id="promptType"
            className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-xs focus:ring-blue-500 focus:border-blue-500 block w-50 p-0.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
          >
            <option defaultValue>Seleccione el tipo</option>
            <option value="agent">Agente</option>
            <option value="guardrail">Guardarail</option>
          </select>
        </form>




        {selectedType === "agent" ? (
          <form
            className="max-w-sm w-100 mx-auto"
            style={{
              display: "flex",
              flexDirection: "row",
              alignItems: "center",
            }}
          >
            <label
              htmlFor="agents"
              className="block text-sm w-12 font-medium text-[var(--color-primary_blue)] dark:text-[var(--color-primary_blue)]"
            >
              Agente
            </label>
            <select
              onChange={(e) => handlePromptSelect(e.target.value)}
              id="promptType"
              className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-xs focus:ring-blue-500 focus:border-blue-500 block w-50 p-0.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
            >
              <option defaultValue>Selecciona una opcion</option>
              <option value="General Agent">General Agent</option>
              <option value="General Prompt">General Prompt</option>
              <option value="MCP Agent">MCP Agent</option>
              <option value="Package Analyst Agent">
                Package Analyst Agent
              </option>
              <option value="Railing Agent">Railing Agent</option>
            </select>
          </form>
        ) : selectedType == "guardrail" ? (
          <form
            className="max-w-sm w-100 mx-auto"
            style={{
              display: "flex",
              flexDirection: "row",
              alignItems: "center",
            }}
          >
            <label
              htmlFor="guardrails"
              className="block text-sm w-17 font-medium text-[var(--color-primary_blue)] dark:text-[var(--color-primary_blue)]"
            >
              Guardarail
            </label>
            <select
              onChange={(e) => handlePromptSelect(e.target.value)}
              id="promptType"
              className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-xs focus:ring-blue-500 focus:border-blue-500 block w-50 p-0.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
            >
              <option defaultValue>Seleccione el tipo</option>
              <option value="Input">Input</option>
              <option value="Output">Output</option>
            </select>
          </form>
        ) : (
          <div></div>
        )}
      </div>
    </>
  );
};

export default PromptNav;
