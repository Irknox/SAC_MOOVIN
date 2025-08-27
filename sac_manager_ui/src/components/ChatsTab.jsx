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
      console.log("Last messages es:",lastMessages);
      
    };

    fetchAndSet();
    const interval = setInterval(fetchAndSet, 60*1000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);
  //
  return (
    <>
      <div
        className="conversations-tab"
        style={{
          display: "flex",
          height: "100%",
          width: "100%",
          backgroundColor: "#000b24ff",
          overflow:"hidden"
        }}
      >
        <div className="no-scrollbar" style={{ listStyle: "none", overflow: "auto", }}>
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
                  display: "flex",
                  alignSelf: "center",
                  height: "100%",
                  overflow: "hidden",
                  gridColumn: "1 / span 2",
                  gridRow: 2,
                }}
              >
                {entry.mensaje_entrante || entry.mensaje_saliente}
              </div>
            </li>
          ))}
        </div>
      </div>
    </>
  );
};

export default ConversationsTab;
