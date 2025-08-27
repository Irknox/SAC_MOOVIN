"use client";
import React, { useState } from "react";
import ConversationsTab from "../../components/ChatsTab";
import Chat from "../../components/Chat";
import OptionsPanel from "../../components/OptionsPanel";
import PromptsView from "../../components/PromptsView";

export default function ManagerUIPage() {
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [activeTab, setActiveTab] = useState("chats"); // Estado para el tab activo

  return (
    <div
      style={{
        display: "grid",
        gridTemplateRows: "50px 1fr",
        gridTemplateColumns: "12% 15% 1fr", 
        height: "99vh",
        maxHeight: "98%",
        width: "100vw",
        minHeight: "100%",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          gridRow: "1",
          gridColumn: "1 / span 3",
          backgroundColor: "#000b24f9",
          display: "flex",
          flexDirection: "row",
          justifyContent: "space-between",
          alignItems: "center",
          height: "100%",
          alignSelf: "start",
          borderRight: "2px solid #ac302c",
          borderBottom: "2px solid #ac302c",
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
              paddingLeft: 15,
            }}
          />
        </div>

        <div
          style={{
            height: "75%",
            backgroundColor: "white",
            borderRadius: "5px",
            margin: "0.75rem",
          }}
        >
          <img
            src="moovin_logo.png"
            alt="Logo Moovin"
            style={{ height: "100%", padding: 8 }}
          />
        </div>
      </div>

      {/* Sidebar (OptionsPanel) */}
      <div
        style={{
          gridRow: "2",
          gridColumn: "1",
          backgroundColor: "#000b24ff",
          borderRight: "2px solid #0b39804f",
        }}
      >
        <OptionsPanel activeTab={activeTab} setActiveTab={setActiveTab} />
      </div>

      {/* ChatsTab (Barra lateral de chats) */}
      {activeTab === "chats" ? (
        <>
          <div
            style={{
              gridRow: "2",
              gridColumn: "2",
              backgroundColor: "#f9fafb",
              borderRight: "2px solid #e5e7eb",
              overflow: "hidden",
            }}
          >
            <ConversationsTab
              onSelectUser={setSelectedUserId}
              selectedUserId={selectedUserId}
            />
          </div>
          {/* Main Content (Chat) */}
          <div
            style={{
              gridRow: "2",
              gridColumn: "3",
              display: "flex",
              flexDirection: "column",
              backgroundColor: "#ffffffff",
              overflow:"auto"
            }}
          >
            {selectedUserId ? (
              <Chat
                userId={selectedUserId}
                style={{
                  height: "100%",
                  width: "100%",
                  display: "flex",
                  backgroundColor: "#ffffffff",
                  flexDirection: "column",
                }}
              />
            ) : (
              <div
                style={{
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
        </>
      ) : (
        <div
          style={{
            gridRow: "2",
            gridColumn: "2 / span 2",
            width: "100%",
            height: "100%",
            maxHeight: "100%",
            overflow: "hidden",
          }}
        >
          {/* PromptsView */}
          <PromptsView />
        </div>
      )}
    </div>
  );
}
