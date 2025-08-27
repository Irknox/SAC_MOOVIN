import JSON5 from "json5";

const ChangeDeliveryOutputView = ({ output }) => {
  const raw = output?.raw ?? output;
  let parsedOutput = raw;

  if (typeof raw === "string") {
    try {
      parsedOutput = JSON.parse(raw);
    } catch {
      try {
        parsedOutput = JSON5.parse(raw);
      } catch {
        parsedOutput = { error: "No se pudo parsear", raw };
      }
    }
  }

  const mountView = () => {
    return <div>Hola</div>;
  };

  return <div>{parsedOutput?.reason ?? parsedOutput?.error ?? ""}</div>;
};

export default ChangeDeliveryOutputView;
