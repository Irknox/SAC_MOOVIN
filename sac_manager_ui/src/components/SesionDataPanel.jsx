const SesionDataPanel = ({ session }) => {
  let context = session.context || {};
  let emotional_state = context.user_env.emotional_state || "No disponible";
  let input_items = Array.isArray(session?.input_items)
    ? session.input_items
    : [];
  let user_messages = 0;
  let tools_called = 0;
  let guardrails_called = 0;
  input_items.forEach((interacion) => {
    user_messages = user_messages + 1;
  });
  let agent_messages = 0;

  const parseMaybeJSON = (raw) => {
    if (typeof raw !== "string") return raw;
    try {
      return JSON.parse(raw);
    } catch {
      try {
        const fixed = raw
          .replaceAll(/'/g, '"')
          .replaceAll("None", "null")
          .replaceAll("True", "true")
          .replaceAll("False", "false");
        return JSON.parse(fixed);
      } catch {
        return raw;
      }
    }
  };

  input_items.forEach((interaction) => {
    if (interaction.agent_message.content != "") {
      agent_messages = agent_messages + 1;
    }
    if (interaction.steps_taken != []) {
      let steps_taken = interaction.steps_taken;
      steps_taken.forEach((step) => {
        if (step.type === "function_call_output") {
          let parsedOutput=parseMaybeJSON(step.output)
          if (parsedOutput.assistant) {
            guardrails_called = guardrails_called + 1;
          } else {
            tools_called = tools_called + 1;
          }
        }
      });
    }
  });

  const parseISO = (s) => (s ? new Date(s) : null);

  const getSessionBounds = (items) => {
    if (!Array.isArray(items) || items.length === 0)
      return { start: null, end: null };

    const firstUserStr =
      items.find((it) => it?.user_message?.date)?.user_message?.date ?? null;

    const rev = [...items].reverse();
    const lastAgentStr =
      rev.find((it) => it?.agent_message?.date)?.agent_message?.date ?? null;

    const lastUserStr =
      rev.find((it) => it?.user_message?.date)?.user_message?.date ?? null;

    const start = parseISO(firstUserStr);
    const end = lastAgentStr
      ? parseISO(lastAgentStr)
      : lastUserStr
      ? parseISO(lastUserStr)
      : null;
    return { start, end };
  };

  const formatDuration = (ms) => {
    if (typeof ms !== "number" || !isFinite(ms) || ms < 0)
      return "No disponible";
    const totalSec = Math.floor(ms / 1000);
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    if (h) return `${h} h ${m} min`;
    if (m) return `${m} min ${s} s`;
    return `${s} s`;
  };

  const { start, end } = getSessionBounds(input_items);
  const sessionDuration =
    start && end ? formatDuration(end - start) : "No disponible";

  return (
    <>
      <div style={{ textAlign: "center", alignContent: "center" }}>
        <h1>Tiempo de Sesión</h1>
        <p className="text-gray-400">{sessionDuration}</p>
      </div>
      <div style={{ textAlign: "center", alignContent: "center" }}>
        <h1>Mensajes del usuario</h1>
        <p className="text-gray-400">{user_messages || "No disponible"}</p>
      </div>
      <div style={{ textAlign: "center", alignContent: "center" }}>
        <h1>Mensajes del Agente</h1>
        <p className="text-gray-400">{agent_messages || "No disponible"}</p>
      </div>
      <div style={{ textAlign: "center", alignContent: "center" }}>
        <h1>Herramientas usadas</h1>
        <p className="text-gray-400">{tools_called || "Ninguna"}</p>
      </div>
      <div style={{ textAlign: "center", alignContent: "center" }}>
        <h1>Guardarailes activados</h1>
        <p className="text-gray-400">{guardrails_called || "0"}</p>
      </div>
      <div style={{ textAlign: "center", alignContent: "center" }}>
        <h1>Estado emocional al finalizar</h1>
        <p className="text-gray-400">
          {emotional_state || "Estado no disponible"}
        </p>
      </div>
      <div style={{ textAlign: "center", alignContent: "center" }}>
        <h1>Recordó sesiones anteriores?</h1>
        <p className="text-gray-400">
          {context.backup_memory_called ? "Sí" : "No"}
        </p>
      </div>
    </>
  );
};

export default SesionDataPanel;
