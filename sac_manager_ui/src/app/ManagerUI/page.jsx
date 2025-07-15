"use client";
import React, { useState, useEffect } from "react";
import ConversationsTab from "../../components/ConversationsTab";
import Chat from "../../components/Chat";

export default function ManagerUIPage() {
  const [selectedUserId, setSelectedUserId] = useState(null);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateRows: "70px 1fr",
        gridTemplateColumns: "300px 1fr",
        height: "100vh",
        width: "100vw",
        minHeight: 0,
      }}
    >
      <div
        style={{
          gridRow: "1 / span 2",
          gridColumn: "1",
          height: "100%",
          borderRight: "2px solid white",
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
          backgroundColor: "#000b24f9",
          display: "flex",
          flexDirection: "row",
          justifyContent: "space-between",
          alignItems: "center",
          height: "85%",
          alignSelf: "start",
          margin: "0 0.25rem 0 0.15rem",
          borderRight:'2px solid #ac302c',
          borderLeft:'2px solid #ac302c',
          borderBottom:'2px solid #ac302c',
          borderRadius: "0 0 4px 4px",
          position: "static",
          zIndex: 20,
        }}
      >
        <div
          style={{
            height: "100%",
            display: "flex",
            justifyItems: "center",
            alignItems: "center",
            
          }}
        >
          <img
            src="SAC-manager-Title.png"
            alt="Logo Moovin"
            style={{
              height: "60%",
              paddingLeft:15
            }}
          />
        </div>

        <div style={{ height: "75%", backgroundColor:'white', borderRadius:'5px',margin:'0.75rem' }}>
          <img
            src="moovin_logo.png"
            alt="Logo Moovin"
            style={{ height: "100%", padding: 8 }}
          />
        </div>
      </div>

      {selectedUserId ? (
        <Chat
          userId={selectedUserId}
          style={{
            gridRow: "1 /span 2",
            gridColumn: "2",
            height: "100%",
            width: "100%",
            display: "flex",
            backgroundColor: "#ffffffff",
            flexDirection: "column",
            padding: 40,
          }}
        />
      ) : (
        <div
          style={{
            gridRow: "2",
            backgroundColor: "#ebe4eb",
            gridColumn: "2",
            flex: 1,
            padding: 20,
            justifyContent: "center",
            alignItems: "center",
            display: "flex",
            color: "#00255a",
            fontSize: "larger",
            fontWeight: "bold",
          }}
        >
          <h3>Selecciona una conversación</h3>
        </div>
      )}
    </div>
  );
}
