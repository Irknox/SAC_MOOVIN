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
  const interval = setInterval(fetchAndSet, 3000);

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
          height: "100%",
          width: "100%",
          backgroundColor: "#000b24ff",
        }}
      >
        <h2
          style={{
            textAlign: "center",
            height: "35px",
            alignContent: "center",
            fontWeight: "bold",
            fontSize: "large",
            backgroundColor: "#000b24ff",
            borderBottom: "3px solid #ac302c",
          }}
        >
          Chats
        </h2>
        <div style={{ listStyle: "none" }}>
          {lastMessages.map((entry) => (
            <li
              key={entry.user_id}
              style={{
                padding: "2px",
                cursor: "pointer",
                background:
                  selectedUserId === entry.user_id ? "#010716ff" : "#000b24ff",
                borderBottom: "2px solid #0b39804f",
                height: "5.25rem",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-evenly",
                paddingLeft: "8px",
              }}
              onClick={() => onSelectUser(entry.user_id)}
            >
              <strong style={{ fontSize: 14}}>
                {entry.contexto.context.user_env.username || entry.user_id}
              </strong>
              <div
                style={{ fontSize: 11, display: "flex", alignSelf: "center" }}
              >
                {entry.mensaje_entrante || entry.mensaje_saliente}
              </div>
              <div style={{ fontSize: 9, textAlign: "right" }}>
                Recibido:{" "}
                {new Date(
                  new Date(entry.fecha).getTime() - 6 * 60 * 60 * 1000
                ).toLocaleString()}
              </div>
            </li>
          ))}
        </div>
      </div>
    </>
  );
};

export default ConversationsTab;
