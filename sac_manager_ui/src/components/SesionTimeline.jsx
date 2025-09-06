import React, { useState } from "react";
import ToolOutput from "./ToolOutput";

const SesionTimeline = ({ session }) => {
  const items = Array.isArray(session?.input_items) ? session.input_items : [];
  const [hoveredStepKey, setHoveredStepKey] = useState(null);

  const parseMaybeJSON = (raw) => {
    if (typeof raw !== "string") return raw;
    try {
      return JSON.parse(raw);
    } catch {
      try {
        const fixed = raw
          .replaceAll(/'/g, '"')
          .replaceAll("None", "null")
          .replaceAll("True", "true")
          .replaceAll("False", "false");
        return JSON.parse(fixed);
      } catch {
        return raw;
      }
    }
  };

  const formatDateTime = (dateString) => {
    if (!dateString) return "";
    const date = new Date(dateString);
    return date.toLocaleString("es-CR", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div style={{ minHeight: "250px", gridColumn: "1" }}>
      <ol className="relative border-s border-gray-200 dark:border-gray-700">
        {items.length === 0 ? (
          <li className="ms-4">
            <h3 className="text-xs font-semibold text-gray-900 dark:text-white">
              Sin actividades en esta sesión
            </h3>
          </li>
        ) : (
          items.map((interaction, i) => (
            <React.Fragment key={i}>
              {/* Mensaje del usuario */}
              <li className="ms-4">
                <div className="absolute w-3 h-3 bg-gray-200 rounded-full mt-1.5 -start-1.5 border border-white dark:border-gray-900 dark:bg-blue-700" />
                <div
                  className="relative"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "3px",
                  }}
                >
                  <h3 className="text-xs font-semibold text-gray-900 dark:text-white">
                    Mensaje del Usuario
                  </h3>
                  <div
                    className="text-sm text-gray-400 cursor-pointer hover:text-blue-400"
                    onMouseEnter={() =>
                      setHoveredStepKey(interaction?.user_message?.content)
                    }
                    onMouseLeave={() => setHoveredStepKey(null)}
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
                        d="M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm-2 9a4 4 0 0 0-4 4v1a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-1a4 4 0 0 0-4-4h-4Z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </div>
                  <div
                    style={{ zIndex: "500" }}
                    className={`absolute top-1/2 left-[15%] -translate-y-1/2 w-80 
                  bg-white dark:bg-[var(--color-selected)] rounded shadow p-3 text-xs
                  border border-gray-200 dark:border-gray-700
                  transition-opacity duration-150 pointer-events-none
                  ${
                    hoveredStepKey == interaction?.user_message?.content
                      ? "opacity-100"
                      : "opacity-0"
                  }`}
                  >
                    {interaction.user_message.content}
                  </div>
                </div>
                <time className="text-xs leading-none text-gray-400 dark:text-gray-500">
                  {formatDateTime(interaction?.user_message?.date)}
                </time>
              </li>

              {/* Pasos / herramientas */}
              {Array.isArray(interaction?.steps_taken) &&
                interaction.steps_taken.map((step, j) => {
                  if (step?.type !== "function_call_output") return null;
                  const stepKey = step?.id ?? step?.call_id ?? `step-${i}-${j}`;

                  const toolCall = interaction.steps_taken.find(
                    (it) =>
                      it?.type === "function_call" &&
                      it?.call_id === step?.call_id
                  );
                  const toolName =
                    toolCall?.tool_name ??
                    toolCall?.name ??
                    toolCall?.function_name ??
                    toolCall?.function?.name ??
                    "Paso";

                  const parsedOutput = parseMaybeJSON(step?.output);
                  if (parsedOutput.assistant) return null;
                  return (
                    <li
                      style={{
                        display: "flex",
                        flexDirection: "row",
                        alignContent: "center",
                      }}
                      key={stepKey}
                      className="m-3 ms-4"
                    >
                      <div className="absolute w-3 h-3  bg-yellow-700 rounded-full mt-1.5 -start-1.5 border border-white dark:border-gray-900 dark:bg-yellow-500" />
                      <h3
                        style={{ alignContent: "center", paddingRight: "5px" }}
                        className="text-xs font-semibold text-gray-900 dark:text-white mr-0.5"
                      >
                        {toolName}
                      </h3>

                      <div
                        className="relative flex justify-center"
                        onMouseEnter={() => setHoveredStepKey(stepKey)}
                        onMouseLeave={() => setHoveredStepKey(null)}
                      >
                        <div className="text-sm text-gray-400 cursor-pointer hover:text-blue-400 flex justify-center">
                          <svg
                            className="w-6 h-6 text-gray-800 dark:text-white"
                            aria-hidden="true"
                            xmlns="http://www.w3.org/2000/svg"
                            width="24"
                            height="24"
                            fill="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path d="M8.4 6.763c-.251.1-.383.196-.422.235L6.564 5.584l2.737-2.737c1.113-1.113 3.053-1.097 4.337.187l1.159 1.159a1 1 0 0 1 1.39.022l4.105 4.105a1 1 0 0 1 .023 1.39l1.345 1.346a1 1 0 0 1 0 1.415l-2.052 2.052a1 1 0 0 1-1.414 0l-1.346-1.346a1 1 0 0 1-1.323.039L11.29 8.983a1 1 0 0 1 .04-1.324l-.849-.848c-.18-.18-.606-.322-1.258-.25a3.271 3.271 0 0 0-.824.202Zm1.519 3.675L3.828 16.53a1 1 0 0 0 0 1.414l2.736 2.737a1 1 0 0 0 1.414 0l6.091-6.091-4.15-4.15Z" />
                          </svg>
                        </div>

                        <div
                          className={`absolute top-1/2 left-[15%] -translate-y-1/2
                                      w-[28rem] max-w-[calc(100vw-4rem)]
                                      max-h-[60vh] overflow-auto
                                      bg-white dark:bg-gray-800 rounded shadow
                                      text-xs text-gray-700 dark:text-gray-300
                                      border border-gray-200 dark:border-gray-700
                                      transition-opacity duration-150 z-[9999]
                                      ${
                                        hoveredStepKey === stepKey
                                          ? "opacity-100"
                                          : "opacity-0"
                                      }`}
                          style={{
                            pointerEvents:
                              hoveredStepKey === stepKey ? "auto" : "none",
                            zIndex: "500",
                          }}
                        >
                          <ToolOutput
                            tool={toolName}
                            output={parsedOutput}
                            visible={hoveredStepKey === stepKey}
                          />
                        </div>
                      </div>
                    </li>
                  );
                })}

              {/* Mensaje del agente */}
              <li className=" ms-4">
                <div className="absolute w-3 h-3 bg-gray-200 rounded-full mt-1.5 -start-1.5 border border-white dark:border-gray-900 dark:bg-green-400" />
                <div
                  className="relative"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "5px",
                  }}
                >
                  <h3 className="text-xs font-semibold text-gray-900 dark:text-white">
                    Respuesta del Agente
                  </h3>
                  <div
                    className="text-sm text-gray-400 cursor-pointer hover:text-blue-400"
                    onMouseEnter={() =>
                      setHoveredStepKey(interaction?.agent_message?.content)
                    }
                    onMouseLeave={() => setHoveredStepKey(null)}
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
                        d="M3 6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-6.616l-2.88 2.592C8.537 20.461 7 19.776 7 18.477V17H5a2 2 0 0 1-2-2V6Zm4 2a1 1 0 0 0 0 2h5a1 1 0 1 0 0-2H7Zm8 0a1 1 0 1 0 0 2h2a1 1 0 1 0 0-2h-2Zm-8 3a1 1 0 1 0 0 2h2a1 1 0 1 0 0-2H7Zm5 0a1 1 0 1 0 0 2h5a1 1 0 1 0 0-2h-5Z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </div>
                  <div
                    style={{ zIndex: "500" }}
                    className={`absolute top-1/2 left-[50%] -translate-y-1/2 w-80 
                  bg-[var(--color-selected)] dark:bg-[var(--color-selected)] rounded shadow p-3 text-xs
                  border border-gray-200 dark:border-gray-700
                  transition-opacity duration-150 pointer-events-none 
                  ${
                    hoveredStepKey == interaction?.agent_message?.content
                      ? "opacity-100"
                      : "opacity-0"
                  }`}
                  >
                    {interaction.agent_message.content}
                  </div>
                </div>{" "}
                <time className="text-xs leading-none text-gray-400 dark:text-gray-500">
                  {formatDateTime(interaction?.agent_message?.date)}
                </time>
              </li>
            </React.Fragment>
          ))
        )}
      </ol>
    </div>
  );
};

export default SesionTimeline;
