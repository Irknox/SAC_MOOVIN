import { fetchAgentHistory } from "../services/ManagerUI_service";
import React, { useState, useEffect } from "react";

const ConversationsTab = ({ onSelectUser, selectedUserId }) => {
  const [history, setHistory] = useState([]);
  const [lastMessages, setLastMessages] = useState([]);

  useEffect(() => {
    fetchAgentHistory().then((history) => {
      setHistory(history);

      const grouped = {};
      history.forEach((entry) => {
        grouped[entry.user_id] = entry;
      });
      setLastMessages(Object.values(grouped));
    });
  }, []);

  return (
    <>
      <div
        className="conversations-tab"
        style={{
          height: "100%",
          width: "100%",
          backgroundColor: "#060025",
        }}
      >
        <h2 style={{ textAlign: "center",height:"25px",alignContent:"center" }}>Chats</h2>
        <div style={{ listStyle: "none", padding: 0 }}>
          {lastMessages.map((entry) => (
            <li
              key={entry.user_id}
              style={{
                padding: "10px",
                cursor: "pointer",
                background:
                  selectedUserId === entry.user_id ? "#000014" : "#060025",
                borderBottom: "1px solid rgb(0, 0, 0)",
              }}
              onClick={() => onSelectUser(entry.user_id)}
            >
              <strong>{entry.user_id}</strong>
              <div style={{ fontSize: 12 }}>
                {entry.mensaje_entrante || entry.mensaje_saliente}
              </div>
              <div style={{ fontSize: 10 }}>
                {new Date(new Date(entry.fecha).getTime() - 6 * 60 * 60 * 1000).toLocaleString()}
              </div>
            </li>
          ))}
        </div>
      </div>
    </>
  );
};

export default ConversationsTab;
