import { useState, useEffect, useRef } from "react";
import AgentResponseModal from "./AgentResponseModal";
import { fetchUserHistory } from "../services/ManagerUI_service";
import JSON5 from "json5";

function formatDate(date) {
  const dias = [
    "Domingo",
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
  ];

  const meses = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "setiembre",
    "octubre",
    "noviembre",
    "diciembre",
  ];

  const d = new Date(date);

  const nombreDia = dias[d.getDay()];
  const dia = d.getDate();
  const nombreMes = meses[d.getMonth()];
  const anio = d.getFullYear();

  return `${nombreDia}, ${dia} de ${nombreMes} del ${anio}`;
}

const Chat = ({ userId, style }) => {
  const containerRef = useRef(null);
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [selectedContext, setSelectedContext] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [msg_idx, setMsg_idx] = useState(null);
  const [session_range, setMessage_range] = useState(5);
  const [session_history, set_Session_history] = useState([]);
  const didInitialScroll = useRef(false);
  const [was_oldest_session_called, setWas_oldest_session_called] =
    useState(false);
  const [is_loading_more, setIs_loading_more] = useState(false);

  const format_input_items = (input_items) => {
    const result = [];
    let i = 0;

    while (i < input_items.length) {
      if (input_items[i].role === "user" && input_items[i].date) {
        const user_message = input_items[i];

        const steps_taken = [];
        let agent_message = null;
        let j = i + 1;

        while (j < input_items.length) {
          const item = input_items[j];

          if (item.role === "user" && !item.date) {
            j++;
            continue;
          }
          if (item.role === "user" && item.date) {
            break;
          }

          if (item.output && item.type === "function_call_output") {
            try {
              const raw =
                typeof item.output === "string"
                  ? item.output.trim()
                  : item.output;
              let parsed = null;

              if (typeof raw === "string") {
                if (raw.startsWith("{") || raw.startsWith("[")) {
                  try {
                    parsed = JSON.parse(raw);
                  } catch {
                    const fixed = raw
                      .replace(/\bNone\b/g, "null")
                      .replace(/\bTrue\b/g, "true")
                      .replace(/\bFalse\b/g, "false");
                    parsed = JSON5.parse(fixed);
                  }
                } else {
                  parsed = null;
                }
              } else {
                parsed = raw;
              }
            } catch {
              console.log("Error al parsear");
            }
          }

          if (item.role === "assistant" && item.content) {
            agent_message = item;
          } else {
            steps_taken.push(item);
          }
          j++;
        }

        if (agent_message) {
          result.push({
            user_message,
            agent_message,
            steps_taken,
          });
          i = j;
        } else {
          i++;
        }
      } else {
        i++;
      }
    }

    return result;
  };

  useEffect(() => {
    didInitialScroll.current = false;
    setWas_oldest_session_called(false);
    setIs_loading_more(false);
    fetchUserHistory(userId, session_range).then((data) => {
      let session_history = [];
      data.forEach((session) => {
        let raw_entry = session.contexto;
        let entry = JSON.parse(raw_entry);
        if (!entry.input_items) {
          return;
        }
        let input_items = format_input_items(entry.input_items);
        session_history.push({
          id: session.id,
          context: entry.context,
          fecha: session.fecha,
          input_items,
        });
      });

      set_Session_history(session_history.reverse());
      console.log("Valor de la session ", session_history);
    });
  }, [userId, session_range]);

  const handleAgentClick = (ctx, entry, idx) => {
    setSelectedContext(ctx);
    setSelectedEntry(entry);
    setMsg_idx(idx);
    setShowModal(true);
  };

  const loadMoreMessages = async () => {
    if (is_loading_more || was_oldest_session_called) return;
    if (session_history.length === 0) return;

    setIs_loading_more(true);

    try {
      const first_id = session_history[0].id;
      const container = containerRef.current;
      const prevTop = container.scrollTop;
      const prevHeight = container.scrollHeight;

      const newMessages = await fetchUserHistory(
        userId,
        session_range,
        first_id
      );

      if (!Array.isArray(newMessages) || newMessages.length === 0) {
        setWas_oldest_session_called(true);
        return;
      }

      const mapped = newMessages
        .map((session) => {
          const entry = JSON.parse(session.contexto);
          if (!entry.input_items) return null;
          return {
            id: session.id,
            context: entry.context,
            fecha: session.fecha,
            input_items: format_input_items(entry.input_items),
          };
        })
        .filter(Boolean) // quita nulos
        .reverse(); // mantén orden como antes

      set_Session_history((prev) => [...mapped, ...prev]);

      requestAnimationFrame(() => {
        const newHeight = container.scrollHeight;
        container.scrollTop = prevTop + (newHeight - prevHeight);
      });
    } finally {
      setIs_loading_more(false);
    }
  };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      if (
        container.scrollTop === 0 &&
        !is_loading_more &&
        !was_oldest_session_called
      ) {
        loadMoreMessages();
      }
    };

    container.addEventListener("scroll", handleScroll);
    return () => container.removeEventListener("scroll", handleScroll);
  }, [session_history, is_loading_more, was_oldest_session_called]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    if (session_history.length > 0 && !didInitialScroll.current) {
      requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
        didInitialScroll.current = true;
      });
    }
  }, [session_history.length]);

  return (
    <div
      ref={containerRef}
      style={{ ...style, overflow: "auto" }}
      className="p-4 flex flex-col gap-4"
    >
      {session_history.map((entry, idx) => (
        <div key={entry.id || idx} className="flex flex-col gap-2">
          <div
            style={{
              fontSize: "medium",
              color: "black",
              display: "flex",
              alignSelf: "center",
              width: "35rem",
              border: "1px solid #000b244e",
              backgroundColor: "#f2f2f2ff",
              borderRadius: "5px",
              justifyContent: "center",
              color: "#000b24ff",
            }}
          >
            <p
              style={{
                display: "flex",
                justifyContent: "right",
                textAlign: "right",
                paddingRight: "0.2rem",
              }}
            >
              Inicio Sesion
            </p>
            <p
              style={{
                display: "flex",
                justifyContent: "left",
                textAlign: "left",
                paddingLeft: "0.2rem",
              }}
            >
              {formatDate(entry.fecha)}
            </p>
          </div>
          {Array.isArray(entry.input_items) &&
            entry.input_items.map((item, itemIdx) => (
              <div key={itemIdx}>
                {/* Mensaje del Usuario */}
                <div className="flex items-start gap-2.5">
                  <div
                    className="flex flex-col w-full max-w-[320px] leading-1.5 p-4 rounded-e-xl rounded-es-xl"
                    style={{ backgroundColor: "#ac302c" }}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-gray-900 dark:text-white">
                        Usuario
                      </span>
                      <span className="text-xs">
                        {item.user_message?.date
                          ? new Date(
                              new Date(item.user_message?.date).getTime()
                            ).toLocaleTimeString()
                          : ""}
                      </span>
                    </div>
                    <p className="text-sm text-gray-900 dark:text-white mt-2">
                      {item.user_message?.content}
                    </p>
                  </div>
                </div>

                {/* Mensaje del Agente */}
                <div className="flex items-start justify-end gap-3 cursor-pointer">
                  <div
                    className="flex flex-col w-full max-w-[320px] leading-1.5 p-4 rounded-s-xl rounded-ee-xl mr-6"
                    style={{ backgroundColor: "#013544" }}
                    onClick={() => handleAgentClick(entry.context, item, idx)}
                  >
                    <div className="flex items-center justify-between ">
                      <span className="text-sm font-semibold text-gray-900 dark:text-white">
                        {item.agent_message.agent || "Agente"}
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-300">
                        {item.agent_message.date
                          ? new Date(
                              new Date(item.agent_message.date).getTime()
                            ).toLocaleTimeString()
                          : ""}
                      </span>
                    </div>
                    <p className="text-sm text-gray-900 dark:text-white mt-2">
                      {Array.isArray(item.agent_message?.content)
                        ? JSON.parse(item.agent_message.content[0].text)
                            .response
                        : item.agent_message.content}
                    </p>
                  </div>
                </div>
              </div>
            ))}
        </div>
      ))}

      {showModal && selectedEntry && (
        <AgentResponseModal
          ctx={selectedContext}
          msg_selected={msg_idx}
          entry={selectedEntry}
          show={showModal}
          onClose={() => setShowModal(false)}
          style={{
            display: "flex",
            alignSelf: "center",
            justifyContent: "center",
          }}
        />
      )}
    </div>
  );
};

export default Chat;
