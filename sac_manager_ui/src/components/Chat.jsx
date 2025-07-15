import { useState, useEffect, useRef } from "react";
import AgentResponseModal from "./AgentResponseModal";
import { fetchUserHistory } from "../services/ManagerUI_service";

const Chat = ({ userId, style }) => {
  const containerRef = useRef(null);
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [msg_idx, setMsg_idx] = useState(null);
  const [message_range, setMessage_range] = useState(20);
  const [user_history, setUser_history] = useState([]);

  useEffect(() => {
    fetchUserHistory(userId, message_range).then((data) => {
      setUser_history(data.reverse());
    });
  }, [userId, message_range]);

  const handleAgentClick = (entry, idx) => {
    setSelectedEntry(entry);
    setMsg_idx(idx);
    setShowModal(true);
  };

  const loadMoreMessages = async () => {
    if (user_history.length === 0) return;

    const first_id = user_history[0].id;
    const container = containerRef.current;

    const previousScrollTop = container.scrollTop;
    const previousHeight = container.scrollHeight;

    const newMessages = await fetchUserHistory(userId, message_range, first_id);

    if (newMessages.length > 0) {
      const reversedNew = newMessages.reverse();
      setUser_history((prev) => [...reversedNew, ...prev]);

      // Espera a que el DOM se actualice
      requestAnimationFrame(() => {
        const newHeight = container.scrollHeight;
        const delta = newHeight - previousHeight;
        container.scrollTop = previousScrollTop + delta;
      });
    }
  };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      if (container.scrollTop === 0) {
        loadMoreMessages();
      }
    };

    container.addEventListener("scroll", handleScroll);
    return () => container.removeEventListener("scroll", handleScroll);
  }, [user_history]);

  useEffect(() => {
    if (user_history.length === 0) return;

    const container = containerRef.current;
    // Solo hacer scroll al fondo si el scroll ya estaba abajo o es primera carga
    const isInitialLoad =
      container.scrollTop === 0 ||
      container.scrollTop === container.scrollHeight;
    if (isInitialLoad) {
      setTimeout(() => {
        container.scrollTop = container.scrollHeight;
      }, 0);
    }
  }, [user_history.length === message_range]); // se ejecuta solo cuando cambia el lote inicial

  return (
    <div
      ref={containerRef}
      style={{ ...style, overflowY: "auto" }}
      className="p-4 flex flex-col gap-4"
    >
      {user_history.map((entry, idx) => (
        <div key={idx} className="flex flex-col gap-2">
          
          {/* Mensaje del Usuario */}
          {entry.mensaje_entrante && (
            <div className="flex items-start gap-2.5">
              <div className="flex flex-col w-full max-w-[320px] leading-1.5 p-4 rounded-e-xl rounded-es-xl" style={{backgroundColor:"#ac302c"}}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-gray-900 dark:text-white">
                    Usuario
                  </span>
                  <span className="text-xs">
                    {new Date(
                      new Date(entry.fecha).getTime() - 6 * 60 * 60 * 1000
                    ).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-sm text-gray-900 dark:text-white mt-2">
                  {entry.mensaje_entrante}
                </p>
              </div>
            </div>
          )}
          {/* Mensaje del Agente */}
          {entry.mensaje_saliente && (
            <div className="flex items-start justify-end gap-3 cursor-pointer">
              <div
                className="flex flex-col w-full max-w-[320px] leading-1.5 p-4 rounded-s-xl rounded-ee-xl mr-6"
                style={{backgroundColor:'#013544'}}
                onClick={() => handleAgentClick(entry, idx)}
              >
                <div className="flex items-center justify-between ">
                  <span className="text-sm font-semibold text-gray-900 dark:text-white">
                    Agente
                  </span>
                  <span className="text-xs text-gray-500 dark:text-gray-300">
                    {new Date(
                      new Date(entry.fecha).getTime() - 6 * 60 * 60 * 1000
                    ).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-sm text-gray-900 dark:text-white mt-2">
                  {entry.mensaje_saliente}
                </p>
              </div>
            </div>
          )}
        </div>
      ))}

      {showModal && selectedEntry && (
        <AgentResponseModal
          msg_selected={msg_idx}
          entry={selectedEntry}
          show={showModal}
          onClose={() => setShowModal(false)}
        />
      )}
    </div>
  );
};

export default Chat;
