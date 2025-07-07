"use client";
import React, { useState, useEffect } from "react";
import ConversationsTab from "../../components/ConversationsTab";
import Chat from "../../components/Chat";
import { fetchAgentHistory } from "../../services/ManagerUI_service";

export default function ManagerUIPage() {
  const [history, setHistory] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState(null);

  useEffect(() => {
    fetchAgentHistory().then(setHistory);
  }, []);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateRows: "60px 1fr",
        gridTemplateColumns: "300px 1fr",
        height: "1000px",
        width: "100vw",
        minHeight: 0,
      }}
    >
      <div
        style={{
          gridRow: "1 / span 2",
          gridColumn: "1",
          height: "100%",
          borderRight: "3px solid rgb(183, 12, 12)",
        }}
      >
        <ConversationsTab
          onSelectUser={setSelectedUserId}
          selectedUserId={selectedUserId}
        />
      </div>
      <div
        style={{
          gridRow: "1",
          gridColumn: "2",
          padding: 20,
          borderBottom: "1px solid rgb(183, 12, 12)",
          backgroundColor: "#060025",
        }}
      >
        <h2>SAC-Manager</h2>
      </div>
      {selectedUserId ? (
        <Chat
          history={history}
          userId={selectedUserId}
          style={{
            gridRow: "2",
            gridColumn: "2",
            height: "100%",
            width: "100%",
            display: "flex",
            backgroundColor: "#00255a",
            flexDirection: "column",
            padding: 20,
          }}
        />
      ) : (
        <div style={{ gridRow: "2", gridColumn: "2", flex: 1, padding: 20 }}>
          <h3>Selecciona una conversación</h3>
        </div>
      )}
    </div>
  );
}
