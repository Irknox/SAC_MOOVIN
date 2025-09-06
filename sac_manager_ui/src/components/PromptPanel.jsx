import React, { useState, useEffect } from "react";
import { updatePrompt } from "@/services/ManagerUI_service";
import AgentDescription from "./AgentDescription";

const PromptPanel = ({ value, prompt }) => {
  const [promptValue, setPromptValue] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);

  useEffect(() => {
    setPromptValue(value || "");
  }, [value]);

  const handleChange = (event) => {
    setPromptValue(event.target.value);
  };

  const handleSave = async () => {
    setIsUpdating("loading"); // Indica que está guardando
    try {
      const update_status = await updatePrompt(prompt, promptValue);
      if (update_status.message === "Prompt updated successfully.") {
        console.log("Prompt updated successfully");
        setIsUpdating("updated");
        setTimeout(() => setIsUpdating(false), 2000);
      } else {
        console.error("Failed to update prompt:", update_status.error);
        setIsUpdating(false);
      }
    } catch (error) {
      console.error("Error updating prompt:", error);
      setIsUpdating(false);
    }
  };

  const updatingIndicator = () => {
    if (isUpdating === "loading") {
      return (
        <li className="flex items-center">
          <div role="status">
            <svg
              aria-hidden="true"
              className="w-4 h-4 me-2 text-gray-200 animate-spin dark:text-gray-600 fill-blue-600"
              viewBox="0 0 100 101"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z"
                fill="currentColor"
              />
              <path
                d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z"
                fill="currentFill"
              />
            </svg>
            <span className="sr-only">Loading...</span>
          </div>
          Actualizando prompt...
        </li>
      );
    } else if (isUpdating === "updated") {
      return (
        <li className="flex items-center">
          <svg
            className="w-4 h-4 me-2 text-green-500 dark:text-green-400 shrink-0"
            aria-hidden="true"
            xmlns="http://www.w3.org/2000/svg"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path d="M10 .5a9.5 9.5 0 1 0 9.5 9.5A9.51 9.51 0 0 0 10 .5Zm3.707 8.207-4 4a1 1 0 0 1-1.414 0l-2-2a1 1 0 0 1 1.414-1.414L9 10.586l3.293-3.293a1 1 0 0 1 1.414 1.414Z" />
          </svg>
          Prompt actualizado
        </li>
      );
    }
    return null;
  };

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 35%",
        backgroundColor: "white",
        height: "100%",
        maxHeight: "100%",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          gridColumn: "1",
          height: "100%",
          color: "white",
          fontSize: "larger",
          fontWeight: "bold",
          display: "flex",
          justifyContent: "center",
          padding: "3px 3px 0px 3px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            backgroundColor: "#000b24ff",
          }}
        >
          {prompt ? (
            <div
              style={{
                height: "100%",
                width: "100%",
                padding: "10px",
                overflow: "hidden",
              }}
            >
              <label
                htmlFor="message"
                className="block mb-1 text-sm font-medium text-white dark:text-white p-1 flex justify-between"
              >
                {prompt ?? "Prompt not selected"}
                {updatingIndicator()}
                <button
                  onClick={handleSave}
                  type="button"
                  className="bg-blue-700 hover:bg-blue-800 focus:ring-4 w-30 focus:outline-none focus:ring-blue-300 rounded-xs dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 flex items-center justify-evenly"
                >
                  <svg
                    className="w-4 h-4 text-gray-800 dark:text-white"
                    aria-hidden="true"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke="currentColor"
                      strokeLinecap="round"
                      strokeWidth="2"
                      d="M11 16h2m6.707-9.293-2.414-2.414A1 1 0 0 0 16.586 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V7.414a1 1 0 0 0-.293-.707ZM16 20v-6a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v6h8ZM9 4h6v3a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1V4Z"
                    />
                  </svg>

                  <p className="text-center text-xs ">Actualizar prompt</p>
                </button>
              </label>
              <textarea
                id="message"
                rows="4"
                className="block p-2.5 w-full h-full text-gray-900 bg-white rounded-xs border border-gray-300 focus:ring-blue-500 focus:border-blue-500 dark:bg-white dark:border-gray-600 dark:placeholder-gray-400 dark:text-black dark:focus:ring-blue-500 dark:focus:border-blue-500"
                style={{
                  resize: "none",
                  overflowY: "auto",
                  maxHeight: "96%",
                  justifySelf: "center",
                  fontSize: "clamp(0.2rem, 0.2rem + 0.4vw, 1rem)",
                }}
                value={promptValue}
                onChange={(e) => {
                  handleChange(e);
                }}
              ></textarea>
            </div>
          ) : (
            "Seleccione un tipo y su prompt"
          )}
        </div>
      </div>
      <div
        style={{
          gridColumn: "2",
          display: "grid",
          gridTemplateRows: "minmax(9rem, 30vh) 1fr",
          color: "white",
          height: "100%",
          maxHeight: "100%",
          backgroundColor: "#000b24ff",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            gridRow: "1",
            maxHeight: "100%",
            overflow: "hidden",
            fontSize: "clamp(0.1rem, 0.3rem + 0.3vw, 0.8rem)",
            textAlign: "left",
            padding: "0.5rem",
            display: "flex",
            flexDirection: "column",
            gap: "1px",
          }}
        >
          <h1
            style={{
              textAlign: "center",
            }}
            class=" text-xs text-center text-white"
          >
            Indicaciones Generales
          </h1>

          <p class="text-gray-300 text-center ">
            Es importante que las instrucciones referentes a una herramiente de
            un agente lleven el nombre explicito de la herramienta.
          </p>
          <p class="text-gray-300 text-center">
            Las instrucciones deben ser claras y concisas, evitando ambigüedades
            que puedan complicar el razonamiento de la IA.
          </p>
          <p class="text-gray-300 text-center">
            El nuevo prompt se tomara en cuenta una vez haya sido actualizado,
            actualiza el prompt para que surja efecto
          </p>
          <h2 class=" text-xs text-center text-white">
            Todos los agentes obtienen
          </h2>
          <ul class="max-w-md space-y-1 text-gray-300 list-disc list-inside dark:text-gray-300">
            <li>
              Funcion Remember: Obtiene un resumen de cada una de las ultimas 3
              sesiones en caso de existir.
            </li>
            <li>
              El general prompt es enviado a todos para que compartan un
              contexto.
            </li>
            <li>
              Si el usuario tiene paquetes con nosotros los ultimos 3 y sus
              estados actualizados, ademas del nombre, y correo del usuario en
              nuestro sistema.
            </li>
            <li>
              Si no tiene paquetes, nombre en Whatsapp y numero de telefono.
            </li>
          </ul>
          <div
            style={{
              width: "70%",
              height: "1px",
              display: "flex",
              alignSelf: "center",
              marginTop: "auto",
            }}
            className="bg-gray-700"
          />
        </div>

        <div
          style={{
            gridRow: "2",
            overflow: "hidden",
            maxHeight: "99%",
            padding: "5px",
          }}
        >
          <p className="text-center text-xs ">Descripcion</p>

          <AgentDescription agent={prompt} />
        </div>
      </div>
    </div>
  );
};

export default PromptPanel;
