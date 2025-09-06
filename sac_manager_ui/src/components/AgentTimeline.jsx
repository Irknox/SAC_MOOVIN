import React, { act, useState } from "react";
import ToolOutput from "./ToolOutput";

const AgentTimeline = ({ actions, getToolOutput, agent_response }) => {
  const [hoveredItem, setHoveredItem] = useState(null);
  const renderTimelineItem = (action, index) => {
    let label = null;
    let extra = null;
    if (action.type === "function_call") {
      const isHandoff = action.name?.startsWith("transfer_to_");
      label = isHandoff
        ? `Handoff: ${action.name.replace("transfer_to_", "")}`
        : `${action.name}`;

      const result = getToolOutput(action.call_id);
      let parsedOutput = result;
      if (typeof result === "string") {
        try {
          const fixedOutput = result
            .replace(/None/g, "null")
            .replace(/'/g, '"');
          parsedOutput = JSON.parse(fixedOutput);
        } catch (e) {
          parsedOutput = {
            raw: result,
          };
        }
      }

      label = isHandoff ? `Handoff` : label;
      let call_arguments = action.arguments || {};
      if (typeof call_arguments === "string") {
        try {
          const fixedOutput = call_arguments
            .replace(/None/g, "null")
            .replace(/'/g, '"');
          call_arguments = JSON.parse(fixedOutput);
        } catch (e) {
          call_arguments = {
            raw: action.arguments || {},
          };
        }
      }

      extra = parsedOutput && (
        <div
          className="relative flex justify-center"
          onMouseEnter={() => setHoveredItem(index)}
          onMouseLeave={() => setHoveredItem(null)}
        >
          <div
            className={
              isHandoff
                ? "text-sm text-gray-400 mt-1 flex justify-center"
                : "text-sm text-gray-400 mt-1 cursor-pointer hover:text-blue-400 flex-column"
            }
          >
            {isHandoff ? (
              <p className="w-auto text-xs">{parsedOutput.assistant}</p>
            ) : (
              <>
                <svg
                  className="w-5 h-5 text-gray-900 dark:text-white"
                  aria-hidden="true"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke="currentColor"
                    strokeWidth="2"
                    d="M21 12c0 1.2-4.03 6-9 6s-9-4.8-9-6c0-1.2 4.03-6 9-6s9 4.8 9 6Z"
                  />
                  <path
                    stroke="currentColor"
                    strokeWidth="2"
                    d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
                  />
                </svg>
              </>
            )}
          </div>
          <div
            className={
              parsedOutput.error
                ? `absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
                  w-[28rem] max-w-[calc(100vw-4rem)]
                  max-h-[60vh] overflow-auto
                  bg-white dark:bg-gray-800 rounded shadow
                  text-xs text-gray-700 dark:text-gray-300
                  border border-gray-200 dark:border-gray-700
                  transition-opacity duration-150 z-[1000]                   ${
                    hoveredItem === index ? "opacity-100" : "opacity-0"
                  }`
                : isHandoff
                ? "none"
                : `absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
                  w-[20rem] max-w-[calc(100vw-4rem)]
                  max-h-[60vh] overflow-auto
                  bg-white dark:bg-gray-800 rounded shadow
                  text-xs text-gray-700 dark:text-gray-300
                  border border-gray-200 dark:border-gray-700
                  transition-opacity duration-150 z-[1000]                   ${
                    hoveredItem === index ? "opacity-100" : "opacity-0"
                  }`
            }
            style={
              isHandoff
                ? { pointerEvents: null }
                : { pointerEvents: hoveredItem === index ? "auto" : "none" }
            }
          >
            {isHandoff ? null : (
              <ToolOutput
                tool={action.name}
                output={parsedOutput}
                visible={hoveredItem === index}
                call={call_arguments}
              />
            )}
          </div>
        </div>
      );
    } else if (action.agent) {
      label = "Agente";
      extra = (
        <div
          className="relative"
          style={{
            display: "flex",
            justifyContent: "center",
          }}
        >
          <div
            className="text-sm text-gray-400 mt-1 cursor-pointer hover:text-blue-400"
            onMouseEnter={() => setHoveredItem(index)}
            onMouseLeave={() => setHoveredItem(null)}
          >
            <svg
              className="w-5 h-5 text-gray-800 dark:text-white"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <path
                stroke="currentColor"
                strokeWidth="2"
                d="M21 12c0 1.2-4.03 6-9 6s-9-4.8-9-6c0-1.2 4.03-6 9-6s9 4.8 9 6Z"
              />
              <path
                stroke="currentColor"
                strokeWidth="2"
                d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
              />
            </svg>
          </div>
          <div
            className={`absolute top-8 left-1/2 -translate-x-1/2 w-80 
                  g-[var(--color-selected)] dark:bg-[var(--color-selected)] p-3 rounded shadow text-xs
                  text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700
                  transition-opacity duration-150 pointer-events-none
                  ${hoveredItem === index ? "opacity-100" : "opacity-0"}`}
          >
            {action.content}
          </div>
        </div>
      );
    } else if (
      action.action === "tripwire_triggered" &&
      action.guardrail === "To Specialized Agent"
    ) {
      label = "Redireccion";
      extra = (
        <div
          className="relative"
          style={{
            display: "flex",
            justifyContent: "center",
          }}
        >
          <div
            className="text-sm text-gray-400 mt-1 cursor-pointer hover:text-blue-400"
            onMouseEnter={() => setHoveredItem(index)}
            onMouseLeave={() => setHoveredItem(null)}
          >
            <svg
              className="w-5 h-5  text-gray-800 dark:text-white"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <path
                stroke="currentColor"
                strokeWidth="2"
                d="M21 12c0 1.2-4.03 6-9 6s-9-4.8-9-6c0-1.2 4.03-6 9-6s9 4.8 9 6Z"
              />
              <path
                stroke="currentColor"
                strokeWidth="2"
                d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
              />
            </svg>
          </div>
          <div
            className={`absolute top-8 left-1/2 -translate-x-1/2 w-80 
                  bg-white dark:bg-gray-900 rounded shadow text-xs
                  text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700
                  transition-opacity duration-150 pointer-events-none p-2
                  ${hoveredItem === index ? "opacity-100" : "opacity-0"}`}
          >
            {action.reason}
          </div>
        </div>
      );
    } else if (
      action.guardrail === "Basic Relevance Check" ||
      action.guardrail === "Basic Output Guardrail"
    ) {
      label = "Guardrail";
      extra = (
        <div
          className="relative"
          style={{
            display: "flex",
            justifyContent: "center",
          }}
        >
          <div
            className="text-sm text-gray-400 mt-1 cursor-pointer hover:text-blue-400"
            onMouseEnter={() => setHoveredItem(index)}
            onMouseLeave={() => setHoveredItem(null)}
          >
            <svg
              className="w-5 h-5 text-gray-800 dark:text-white"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <path
                stroke="currentColor"
                strokeWidth="2"
                d="M21 12c0 1.2-4.03 6-9 6s-9-4.8-9-6c0-1.2 4.03-6 9-6s9 4.8 9 6Z"
              />
              <path
                stroke="currentColor"
                strokeWidth="2"
                d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
              />
            </svg>
          </div>
          <div
            className={`absolute top-8 left-1/2 -translate-x-1/2 w-80 
                  bg-white dark:bg-gray-900 rounded shadow text-xs p-2
                  text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700
                  transition-opacity duration-150 pointer-events-none
                  ${hoveredItem === index ? "opacity-100" : "opacity-0"}`}
          >
            {action.reason}
          </div>
        </div>
      );
    } else if (action.role === "user") {
      label = "Usuario";
      extra = (
        <div
          className="relative"
          style={{
            display: "flex",
            justifyContent: "center",
            alignSelf: "center",
          }}
        >
          <div
            className="text-sm text-gray-400 mt-1 cursor-pointer hover:text-blue-400"
            style={{
              display: "flex",
              justifyContent: "center",
            }}
            onMouseEnter={() => setHoveredItem(index)}
            onMouseLeave={() => setHoveredItem(null)}
          >
            <svg
              className="w-5 h-5  text-gray-800 dark:text-white"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <path
                stroke="currentColor"
                strokeWidth="2"
                d="M21 12c0 1.2-4.03 6-9 6s-9-4.8-9-6c0-1.2 4.03-6 9-6s9 4.8 9 6Z"
              />
              <path
                stroke="currentColor"
                strokeWidth="2"
                d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
              />
            </svg>
          </div>
          <div
            className={`absolute top-8 left-1/2 -translate-x-1/2 w-80 
                  g-[var(--color-selected)] dark:bg-[var(--color-selected)] p-3 rounded shadow text-xs
                  text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700
                  transition-opacity duration-150 pointer-events-none
                  ${hoveredItem === index ? "opacity-100" : "opacity-0"}`}
          >
            {action.content}
          </div>
        </div>
      );
    }

    if (!label) return null;

    return (
      <li
        key={index}
        className="relative mb-6 sm:mb-0"
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          width: "100%",
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateRows: "70% 30%",
            width: "100%",
          }}
        >
          <div
            style={{
              gridRow: "1",
              display: "flex",
              width: "100%",
              alignItems: "center",
            }}
          >
            {action.role == "user" ? (
              <div className="hidden sm:flex w-full" />
            ) : (
              <div className="hidden sm:flex w-full bg-gray-200 h-0.5 dark:bg-green-500"></div>
            )}

            <div
              style={{
                minWidth: "2.5rem",
                minHeight: "2.5rem",
                padding: "5px",
                display: "flex",
                justifyContent: "right",
              }}
              className="z-10 bg-blue-100 rounded-full ring-0 ring-white dark:bg-blue-900 sm:ring-3 dark:ring-green-500"
            >
              {action.type === "function_call" &&
              action.name?.startsWith("transfer_to_") ? (
                <svg
                  aria-hidden="true"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke="currentColor"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="m16 10 3-3m0 0-3-3m3 3H5v3m3 4-3 3m0 0 3 3m-3-3h14v-3"
                  />
                </svg>
              ) : action.type === "function_call" ? (
                <svg
                  aria-hidden="true"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M8.4 6.763c-.251.1-.383.196-.422.235L6.564 5.584l2.737-2.737c1.113-1.113 3.053-1.097 4.337.187l1.159 1.159a1 1 0 0 1 1.39.022l4.105 4.105a1 1 0 0 1 .023 1.39l1.345 1.346a1 1 0 0 1 0 1.415l-2.052 2.052a1 1 0 0 1-1.414 0l-1.346-1.346a1 1 0 0 1-1.323.039L11.29 8.983a1 1 0 0 1 .04-1.324l-.849-.848c-.18-.18-.606-.322-1.258-.25a3.271 3.271 0 0 0-.824.202Zm1.519 3.675L3.828 16.53a1 1 0 0 0 0 1.414l2.736 2.737a1 1 0 0 0 1.414 0l6.091-6.091-4.15-4.15Z" />
                </svg>
              ) : action.action === "tripwire_triggered" &&
                action.guardrail === "To Specialized Agent" ? (
                <svg
                  aria-hidden="true"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M5.027 10.9a8.729 8.729 0 0 1 6.422-3.62v-1.2A2.061 2.061 0 0 1 12.61 4.2a1.986 1.986 0 0 1 2.104.23l5.491 4.308a2.11 2.11 0 0 1 .588 2.566 2.109 2.109 0 0 1-.588.734l-5.489 4.308a1.983 1.983 0 0 1-2.104.228 2.065 2.065 0 0 1-1.16-1.876v-.942c-5.33 1.284-6.212 5.251-6.25 5.441a1 1 0 0 1-.923.806h-.06a1.003 1.003 0 0 1-.955-.7A10.221 10.221 0 0 1 5.027 10.9Z" />
                </svg>
              ) : action.guardrail === "Basic Relevance Check" ||
                action.guardrail === "Basic Output Guardrail" ? (
                <svg
                  aria-hidden="true"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M13.09 3.294c1.924.95 3.422 1.69 5.472.692a1 1 0 0 1 1.438.9v9.54a1 1 0 0 1-.562.9c-2.981 1.45-5.382.24-7.25-.701a38.739 38.739 0 0 0-.622-.31c-1.033-.497-1.887-.812-2.756-.77-.76.036-1.672.357-2.81 1.396V21a1 1 0 1 1-2 0V4.971a1 1 0 0 1 .297-.71c1.522-1.506 2.967-2.185 4.417-2.255 1.407-.068 2.653.453 3.72.967.225.108.443.216.655.32Z" />
                </svg>
              ) : action.role === "user" ? (
                <svg
                  aria-hidden="true"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    fillRule="evenodd"
                    d="M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm-2 9a4 4 0 0 0-4 4v1a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-1a4 4 0 0 0-4-4h-4Z"
                    clipRule="evenodd"
                  />
                </svg>
              ) : (
                <svg
                  aria-hidden="true"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke="currentColor"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M14.079 6.839a3 3 0 0 0-4.255.1M13 20h1.083A3.916 3.916 0 0 0 18 16.083V9A6 6 0 1 0 6 9v7m7 4v-1a1 1 0 0 0-1-1h-1a1 1 0 0 0-1 1v1a1 1 0 0 0 1 1h1a1 1 0 0 0 1-1Zm-7-4v-6H5a2 2 0 0 0-2 2v2a2 2 0 0 0 2 2h1Zm12-6h1a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2h-1v-6Z"
                  />
                </svg>
              )}
            </div>

            {action.agent ? (
              <div className="hidden sm:flex w-full" />
            ) : (
              <div className="hidden sm:flex w-full bg-gray-200 h-0.5 dark:bg-green-500"></div>
            )}
          </div>

          <div
            style={{
              gridRow: "2",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              width: "100%",
              height: "60px",
              textAlign: "center",
            }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignContent: "center",
                maxHeight: "auto",
                padding: "auto",
              }}
            >
              <h4 className="text-xs text-gray-900 dark:text-white pr-2 pl-2">
                {label}
              </h4>
              {extra}
            </div>
          </div>
        </div>
      </li>
    );
  };

  return (
    <div
      style={{
        height: "80%",
        maxHeight: "100%",
        display: "flex",
        justifyItems: "center",
      }}
    >
      <ol
        className="sm:flex"
        style={{
          minWidth: "70em",
          maxWidth: "70em",
          justifySelf: "center",
        }}
      >
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
