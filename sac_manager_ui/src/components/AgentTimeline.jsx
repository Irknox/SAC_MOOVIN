import React, { act, useState } from "react";
import ToolOutput from "./ToolOutput";

const AgentTimeline = ({ actions, getToolOutput, agent_response }) => {
  const [hoveredItem, setHoveredItem] = useState(null);
  console.log("actions recibidas", actions);

  const renderTimelineItem = (action, index) => {
    let label = null;
    let extra = null;
    if (action.type === "function_call") {
      const isHandoff = action.name?.startsWith("transfer_to_");
      if (isHandoff) {
        label = `Handoff: ${action.name.replace("transfer_to_", "")}`;
      } else {
        label = `${action.name}`;

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
            <div className="text-sm text-gray-400 mt-1 cursor-pointer hover:text-blue-400 flex justify-center">
              <svg
                className="w-6 h-6 text-gray-800 dark:text-white"
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
                  : `absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
                  w-[28rem] max-w-[calc(100vw-4rem)]
                  max-h-[60vh] overflow-auto
                  bg-white dark:bg-gray-800 rounded shadow
                  text-xs text-gray-700 dark:text-gray-300
                  border border-gray-200 dark:border-gray-700
                  transition-opacity duration-150 z-[1000]                   ${
                    hoveredItem === index ? "opacity-100" : "opacity-0"
                  }`
              }
              style={{ pointerEvents: hoveredItem === index ? "auto" : "none" }}
            >
              <ToolOutput
                tool={action.name}
                output={parsedOutput}
                visible={hoveredItem === index}
                call={call_arguments}
              />
            </div>
          </div>
        );
      }
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
              className="w-6 h-6 text-gray-800 dark:text-white"
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
                  bg-white dark:bg-gray-800 rounded shadow text-xs
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
              className="w-6 h-6 text-gray-800 dark:text-white"
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
                  bg-white dark:bg-gray-800 rounded shadow text-xs
                  text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700
                  transition-opacity duration-150 pointer-events-none
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
              className="w-6 h-6 text-gray-800 dark:text-white"
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
                  bg-white dark:bg-gray-800 rounded shadow text-xs
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
              className="w-6 h-6 text-gray-800 dark:text-white"
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
                  bg-white dark:bg-gray-800 rounded shadow text-xs
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
          {" "}
          <div
            style={{
              gridRow: "1",
              display: "flex",
              width: "100%",
              alignItems: "center",
            }}
          >
            {action.role == "user" ? (
              <></>
            ) : (
              <div className="hidden sm:flex w-full bg-gray-200 h-0.5 dark:bg-gray-700"></div>
            )}
            <div
              style={{
                minWidth: "2.5rem",
                minHeight: "2.5rem",
                padding: "3px",
                display: "flex",
                justifyContent: "right",
              }}
              className="z-10 bg-blue-100 rounded-full ring-0 ring-white dark:bg-blue-900 sm:ring-8 dark:ring-gray-900"
            >
              {action.type === "function_call" ? (
                <svg
                  aria-hidden="true"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke="currentColor"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M7.58209 8.96025 9.8136 11.1917l-1.61782 1.6178c-1.08305-.1811-2.23623.1454-3.07364.9828-1.1208 1.1208-1.32697 2.8069-.62368 4.1363.14842.2806.42122.474.73509.5213.06726.0101.1347.0133.20136.0098-.00351.0666-.00036.1341.00977.2013.04724.3139.24069.5867.52125.7351 1.32944.7033 3.01552.4971 4.13627-.6237.8375-.8374 1.1639-1.9906.9829-3.0736l4.8107-4.8108c1.0831.1811 2.2363-.1454 3.0737-.9828 1.1208-1.1208 1.3269-2.80688.6237-4.13632-.1485-.28056-.4213-.474-.7351-.52125-.0673-.01012-.1347-.01327-.2014-.00977.0035-.06666.0004-.13409-.0098-.20136-.0472-.31386-.2406-.58666-.5212-.73508-1.3294-.70329-3.0155-.49713-4.1363.62367-.8374.83741-1.1639 1.9906-.9828 3.07365l-1.7788 1.77875-2.23152-2.23148-1.41419 1.41424Zm1.31056-3.1394c-.04235-.32684-.24303-.61183-.53647-.76186l-1.98183-1.0133c-.38619-.19746-.85564-.12345-1.16234.18326l-.86321.8632c-.3067.3067-.38072.77616-.18326 1.16235l1.0133 1.98182c.15004.29345.43503.49412.76187.53647l1.1127.14418c.3076.03985.61628-.06528.8356-.28461l.86321-.8632c.21932-.21932.32446-.52801.2846-.83561l-.14417-1.1127ZM19.4448 16.4052l-3.1186-3.1187c-.7811-.781-2.0474-.781-2.8285 0l-.1719.172c-.7811.781-.7811 2.0474 0 2.8284l3.1186 3.1187c.7811.781 2.0474.781 2.8285 0l.1719-.172c.7811-.781.7811-2.0474 0-2.8284Z"
                  />
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
              <></>
            ) : (
              <div className="hidden sm:flex w-full bg-gray-200 h-0.5 dark:bg-gray-700"></div>
            )}
          </div>
          <div
            style={{
              gridRow: "2",
              display: "flex",
              flexDirection: "column",
              alignItems: action.agent
                ? "end"
                : action.role === "user"
                ? "start"
                : "center",
              width: "100%",
              textAlign: "center",
            }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
              }}
            >
              {" "}
              <h4 className="text-base text-gray-900 dark:text-white">
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
    <div className="flex justify-center h-full">
      <ol className="sm:flex" style={{ width: "80%" }}>
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
