import PromptNav from "./PromptNav";
import PromptPanel from "./PromptPanel";
import React, { useState, useEffect } from "react";
import { fetchPrompt } from "@/services/ManagerUI_service";

const PromptsView = () => {
  const [selectedPrompt, setSelectedPrompt] = useState(null);
  const [prompt, setPrompt] = useState("");

  useEffect(() => {
    const fetchSelectedPrompt = async () => {
      try {
        const promptData = await fetchPrompt(selectedPrompt);
        setPrompt(promptData.prompt || "");
      } catch (error) {
        console.error("Error fetching prompt:", error);
      }
    };

    fetchSelectedPrompt();
  }, [selectedPrompt]);

  const handlePromptSelect = (prompt) => {
    setSelectedPrompt(prompt);
  };

  return (
      <div
        id="main-cont"
        style={{
          display: "grid",
          gridTemplateRows: "5% 1fr",
          gridTemplateColumns: "1fr",
          height: "100%",
          maxHeight: "100%",
          overflow: "hidden",
        }}
      >
        <PromptNav
          handlePromptSelect={handlePromptSelect}
          style={{ gridRow: "1" }}
        />
        <PromptPanel
          value={prompt}
          prompt={selectedPrompt}
          style={{ gridRow: "2" }}
        />
      </div>
  );
};

export default PromptsView;
