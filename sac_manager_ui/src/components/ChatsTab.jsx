import { fetchHistoryPreview } from "../services/ManagerUI_service";
import React, { useState, useEffect } from "react";

const ConversationsTab = ({ onSelectUser, selectedUserId }) => {
  const [history, setHistory] = useState([]);
  const [lastMessages, setLastMessages] = useState([]);

  useEffect(() => {
    let isMounted = true;
    const fetchAndSet = async () => {
      const history = await fetchHistoryPreview();
      if (!isMounted) return;
      const grouped = {};
      const lastMessages = [];
      history
        .sort((a, b) => new Date(b.fecha) - new Date(a.fecha))
        .forEach((entry) => {
          try {
            const raw = entry.contexto;
            const parsedOnce = JSON.parse(raw);
            entry.contexto =
              typeof parsedOnce === "string"
                ? JSON.parse(parsedOnce)
                : parsedOnce;
          } catch (e) {
            entry.contexto = {};
          }
          if (!grouped[entry.user_id]) {
            grouped[entry.user_id] = entry;
            lastMessages.push(entry);
          }
        });
      setHistory(history);
      setLastMessages(lastMessages);
    };

    fetchAndSet();
    const interval = setInterval(fetchAndSet, 5 * 1000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);
  //
  return (
    <div
      className="conversations-tab"
      style={{
        display: "flex",
        height: "100%",
        width: "100%",
        backgroundColor: "#000b24ff",
        overflow: "hidden",
      }}
    >
      <div
        className="no-scrollbar"
        style={{ listStyle: "none", overflow: "auto", width: "100%" }}
      >
        {lastMessages.map((entry) => (
          <li
            key={entry.user_id}
            className={
              selectedUserId === entry.user_id
                ? "text-white bg-[var(--color-selected)] dark:bg-[var(--color-selected)]"
                : "hover:text-white bg-[var(--color-primary_blue)] hover:bg-[var(--color-primary_hover)] dark:bg-[var(--color-primary_blue)] dark:hover:bg-[var(--color-primary_hover)]"
            }
            style={{
              cursor: "pointer",
              borderBottom: "2px solid #0b39804f",
              height: "5.25rem",
              padding: "8px",
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gridTemplateRows: "20% 1fr",
            }}
            onClick={() => onSelectUser(entry.user_id)}
          >
            <strong
              style={{
                fontSize: 11,
                gridColumn: 1,
                gridRow: 1,
                overflow: "hidden",
              }}
            >
              {entry.contexto.context.user_env.username || entry.user_id}
            </strong>
            <div
              style={{
                fontSize: 8,
                textAlign: "right",
                gridColumn: 2,
                gridRow: 1,
                overflow: "hidden",
              }}
            >
              {" "}
              {new Date(
                new Date(entry.fecha).getTime() - 6 * 60 * 60 * 1000
              ).toLocaleString()}
            </div>
            <div
              style={{
                fontSize: 11,
                display: "grid",
                gridTemplateColumns: "85% 1fr",
                alignSelf: "center",
                height: "100%",
                overflow: "hidden",
                gridColumn: "1 / span 2",
                gridRow: 2,
                justifyContent: "space-between",
                padding: "5px",
              }}
            >
              {entry.mensaje_saliente==="[BATCHED_SESSION]"? entry.mensaje_entrante:entry.mensaje_saliente}
              <div className="col-start-2 col-end-3 h-10 flex items-center ">
                <span className="inline-flex items-center justify-center w-5 h-5 text-xs p-0.5 font-semibold text-blue-800 bg-blue-400 rounded-full ">
                  <svg
                    className="w-6 h-6 text-gray-800 dark:text-white"
                    aria-hidden="true"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="white"
                    viewBox="0 0 24 24"
                  >
                    <path d="M17.133 12.632v-1.8a5.406 5.406 0 0 0-4.154-5.262.955.955 0 0 0 .021-.106V3.1a1 1 0 0 0-2 0v2.364a.955.955 0 0 0 .021.106 5.406 5.406 0 0 0-4.154 5.262v1.8C6.867 15.018 5 15.614 5 16.807 5 17.4 5 18 5.538 18h12.924C19 18 19 17.4 19 16.807c0-1.193-1.867-1.789-1.867-4.175ZM6 6a1 1 0 0 1-.707-.293l-1-1a1 1 0 0 1 1.414-1.414l1 1A1 1 0 0 1 6 6Zm-2 4H3a1 1 0 0 1 0-2h1a1 1 0 1 1 0 2Zm14-4a1 1 0 0 1-.707-1.707l1-1a1 1 0 1 1 1.414 1.414l-1 1A1 1 0 0 1 18 6Zm3 4h-1a1 1 0 1 1 0-2h1a1 1 0 1 1 0 2ZM8.823 19a3.453 3.453 0 0 0 6.354 0H8.823Z" />
                  </svg>
                </span>
              </div>
            </div>
          </li>
        ))}
      </div>
    </div>
  );
};

export default ConversationsTab;
