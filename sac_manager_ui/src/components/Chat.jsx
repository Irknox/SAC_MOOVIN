import { useState, useEffect, useRef } from "react";
import AgentResponseModal from "./AgentResponseModal";
import { fetchUserHistory } from "../services/ManagerUI_service";
import JSON5 from "json5";
import SesionTimeline from "./SesionTimeline";
import SesionDataPanel from "./SesionDataPanel";
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
  const [openId, setOpenId] = useState(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [isAllRead, setIsAllRead] = useState(true);

  //-------------Nuevos mensajes en redis-------------//
  const POLL_MS = 5 * 1000;

  const mapOneSession = (session) => {
    const entry = JSON.parse(session.contexto);
    if (!entry?.input_items) return null;
    return {
      id: session.id,
      context: entry.context,
      fecha: session.fecha,
      input_items: format_input_items(entry.input_items),
    };
  };

  const getAgentText = (agent_message) => {
    if (!agent_message) return "";
    const raw = agent_message.content;
    if (Array.isArray(raw)) {
      try {
        const txt = raw[0]?.text ?? "";
        return JSON.parse(txt)?.response ?? txt ?? "";
      } catch {
        return raw[0]?.text ?? "";
      }
    }
    return typeof raw === "string" ? raw : "";
  };

  const messagesEqual = (a, b) => {
    if (!a || !b) return false;
    const u1 = (a.user_message?.content || "").trim();
    const u2 = (b.user_message?.content || "").trim();
    const ag1 = getAgentText(a.agent_message).trim();
    const ag2 = getAgentText(b.agent_message).trim();
    return u1 === u2 && ag1 === ag2;
  };

  const isPrevPrefixOfLatest = (prevItems = [], latestItems = []) => {
    if (prevItems.length > latestItems.length) return false;
    for (let i = 0; i < prevItems.length; i++) {
      if (!messagesEqual(prevItems[i], latestItems[i])) return false;
    }
    return true;
  };

  const itemsEqual = (aItems = [], bItems = []) => {
    if (aItems.length !== bItems.length) return false;
    for (let i = 0; i < aItems.length; i++) {
      if (!messagesEqual(aItems[i], bItems[i])) return false;
    }
    return true;
  };

  //-------------Nuevos mensajes en redis-------------//

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

  //-------------Boton de scroll a bottom-------------//
  const isNearBottom = (el, offset = 24) => {
    if (!el) return true;
    const { scrollTop, clientHeight, scrollHeight } = el;
    return scrollTop + clientHeight >= scrollHeight - offset;
  };

  const scrollToBottom = () => {
    const el = containerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    setIsAllRead(true);
    setIsAtBottom(true);
  };
  //-------------Boton de scroll a bottom-------------//

  //-------------Carga de nuevos mensajes-------------//
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
    });
  }, [userId, session_range]);

  useEffect(() => {
    if (!userId) return;
    let isMounted = true;
    const tick = async () => {
      if (!isMounted) return;
      try {
        const latestList = await fetchUserHistory(userId, 1);
        if (!Array.isArray(latestList) || latestList.length === 0) return;

        const latestMapped = mapOneSession(latestList[0]);
        if (!latestMapped) return;
        const atBottomNow = isNearBottom(containerRef.current);
        set_Session_history((prev) => {
          if (!Array.isArray(prev) || prev.length === 0) {
            return [latestMapped];
          }
          const prevLatest = prev[prev.length - 1];
          if (prevLatest?.id === latestMapped.id) {
            const prevLen = prevLatest.input_items?.length ?? 0;
            const newLen = latestMapped.input_items?.length ?? 0;

            if (prevLen === newLen) return prev;

            if (!atBottomNow) setIsAllRead(false);
            const next = [...prev];
            next[next.length - 1] = latestMapped;
            return next;
          }
          const prevItems = prevLatest.input_items || [];
          const newItems = latestMapped.input_items || [];

          if (
            isPrevPrefixOfLatest(prevItems, newItems) ||
            itemsEqual(prevItems, newItems)
          ) {
            if (!atBottomNow) setIsAllRead(false);
            const next = [...prev];
            next[next.length - 1] = latestMapped;
            return next;
          }

          if (!atBottomNow) setIsAllRead(false);
          return [...prev, latestMapped];
        });
      } catch (e) {
        console.warn("[Chat][poll] error refrescando sesión más reciente", e);
      }
    };

    const interval = setInterval(tick, POLL_MS);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [userId]);

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
        .filter(Boolean)
        .reverse();

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
    // carga histórica si llegas arriba (tu lógica)
    if (
      container.scrollTop === 0 &&
      !is_loading_more &&
      !was_oldest_session_called
    ) {
      loadMoreMessages();
    }

    // marcar si estás al fondo
    const atBottom = isNearBottom(container);
    setIsAtBottom(atBottom);

    // ⚠️ limpiar “Mensajes Nuevos” si llegaste al fondo manualmente
    if (atBottom) {
      setIsAllRead(true);
    }
  };

  container.addEventListener("scroll", handleScroll, { passive: true });

  // estado inicial
  const initialAtBottom = isNearBottom(container);
  setIsAtBottom(initialAtBottom);
  if (initialAtBottom) setIsAllRead(true);

  return () => container.removeEventListener("scroll", handleScroll);
}, [session_history, is_loading_more, was_oldest_session_called]); // deps originales

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    if (session_history.length > 0 && !didInitialScroll.current) {
      requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
        didInitialScroll.current = true;
        setIsAtBottom(true);
      });
    }
  }, [session_history.length]);

  //-------------Carga de nuevos mensajes-------------//

  //-------------Click al Msj del Agente-------------//

  const handleAgentClick = (ctx, entry, idx) => {
    setSelectedContext(ctx);
    setSelectedEntry(entry);
    setMsg_idx(idx);
    setShowModal(true);
  };
  //-------------Click al Msj del Agente-------------//

  return (
    <div
      ref={containerRef}
      style={{ ...style, overflowY: "auto", overflowX: "hidden" }}
      className="p-4 flex flex-col gap-4"
    >
      {session_history.map((entry, idx) => (
        <div key={entry.id || idx} className="flex flex-col gap-2">
          <div>
            {(() => {
              const panelId = `accordion-body-${entry.id ?? idx}`;
              const headingId = `accordion-heading-${entry.id ?? idx}`;
              const isOpen = openId === panelId;

              return (
                <div data-accordion="collapse">
                  <h2 id={headingId}>
                    <button
                      type="button"
                      onClick={() => setOpenId(isOpen ? null : panelId)}
                      className={
                        isOpen
                          ? "flex items-center justify-center w-full p-1 border-b-0 border-gray-200 rounded-t-xl focus:ring-4 focus:ring-blue-200 dark:focus:ring-[var(--color-primary_button)] dark:border-gray-700 gap-3"
                          : "flex items-center justify-center w-full p-1 border-b-0 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-200 dark:focus:ring-[var(--color-primary_button)] dark:border-gray-700 gap-3"
                      }
                      aria-expanded={isOpen}
                      aria-controls={panelId}
                      style={{
                        backgroundColor: "#23c0c0",
                        width: "30%",
                        maxWidth: "50%",
                        justifySelf: "center",
                        color: "white",
                        fontFamily: "AvocadoFont, Arial",
                      }}
                    >
                      <p>{formatDate(entry.fecha)}</p>

                      <svg
                        className={`w-3 h-3 shrink-0 transition-transform ${
                          isOpen ? "rotate-180" : ""
                        }`}
                        aria-hidden="true"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 10 6"
                      >
                        <path
                          stroke="currentColor"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M9 5 5 1 1 5"
                        />
                      </svg>
                    </button>
                  </h2>

                  <div
                    id={panelId}
                    aria-labelledby={headingId}
                    className={isOpen ? "" : "hidden"}
                  >
                    <div className="p-5  border border-b-0 border-gray-200 dark:border-gray-700 dark:bg-gray-900">
                      <p className="mb-2 text-gray-500 dark:text-gray-400">
                        Actividad en esta sesión
                      </p>
                      <div
                        style={{
                          padding: "5px",
                          display: "grid",
                          gridTemplateColumns: "30% 1fr",
                        }}
                      >
                        <SesionTimeline session={entry} />
                        <div
                          style={{
                            gridColumn: "2",
                            height: "300px",
                            maxHeight: "auto",
                            display: "grid",
                            gridTemplate: " 1fr 1fr 1fr / 1fr 1fr 1fr",
                          }}
                        >
                          <SesionDataPanel session={entry} />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })()}
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
                <div className="flex items-start justify-end gap-3 cursor-pointer min-w-0">
                  <div
                    className="min-w-0 flex flex-col w-full max-w-[380px] p-4 rounded-s-xl rounded-ee-xl mr-6"
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
                    <p
                      className="min-w-0 text-sm text-gray-900 dark:text-white mt-2 whitespace-pre-wrap break-words"
                      style={{ overflowWrap: "anywhere" }}
                    >
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

      {didInitialScroll.current && !isAtBottom && (
        <div
          onClick={scrollToBottom}
          className="flex fixed right-6 bottom-6 cursor-pointer hover:bg-[var(--color-primary_button_hovered)] z-[1000] rounded-full bg-[var(--color-primary_button)] p-2"
          title="Ir al mensaje más reciente"
        >
          <svg
            className="w-6 h-6 text-white"
            aria-hidden="true"
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            fill="none"
            viewBox="0 0 24 24"
          >
            <path
              stroke="#ffffffff"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="m19 9-7 7-7-7"
            />
          </svg>
          {!isAllRead && (
            <>
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
                  d="M2 12C2 6.477 6.477 2 12 2s10 4.477 10 10-4.477 10-10 10S2 17.523 2 12Zm11-4a1 1 0 1 0-2 0v5a1 1 0 1 0 2 0V8Zm-1 7a1 1 0 1 0 0 2h.01a1 1 0 1 0 0-2H12Z"
                  clipRule="evenodd"
                />
              </svg>
              <p className="text-gray-200 text-xs text-center self-center p-1">
                Mensajes Nuevos
              </p>
            </>
          )}
        </div>
      )}

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
