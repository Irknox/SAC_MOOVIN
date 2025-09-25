const AgentDescription = ({ agent }) => {
  const mountDescription = () => {
    let agent_description = "";
    switch (agent) {
      case "Package Analyst Agent":
        agent_description = (
          <>
            <p>
              Este agente está diseñado para gestionar consultas relacionadas
              con paquetes y proporcionar información clara sobre su estado,
              fechas de entrega, direcciones de entrega y procesos asociados.
            </p>
            <h1>Herramientas disponibles</h1>
            <ul
              className="max-w-md space-y-1 list-disc list-inside"
              style={{ color: "#02ffa2ff" }}
            >
              <li>
                get_SLA Función
                <div style={{ marginLeft: "20px" }}>
                  <p className="text-gray-300">
                    Obtiene la fecha estimada de entrega de un paquete.
                  </p>
                  <p className="text-gray-300"> Parámetros necesarios</p>
                  <ul className="ml-5 max-w-md space-y-1 text-gray-300 list-disc list-inside dark:text-gray-300">
                    <li>Número de seguimiento (tracking)</li>
                    <li>Número de telefono del paquete.</li>
                  </ul>
                </div>
              </li>
              <li>
                get_timeline{" "}
                <div style={{ marginLeft: "20px" }}>
                  <p className="text-gray-300">
                    Devuelve un orden cronologico de los eventos de mas reciente
                    a mas antiguo, nombre en el paquete, telefono en el paquete
                    y tienda donde se compro si esta disponible.
                  </p>
                  <p className="text-gray-300"> Parámetros necesarios</p>
                  <ul className="ml-5 max-w-md space-y-1 text-gray-300 list-disc list-inside dark:text-gray-300">
                    <li>Número de seguimiento (tracking)</li>
                    <li>Número de telefono del paquete.</li>
                  </ul>
                </div>
              </li>
              <li>
                get_likely_package_timelines
                <div style={{ marginLeft: "20px" }}>
                  <p className="text-gray-300">
                    Devuelve timelines de paquetes similares al del usuario,
                    esto con el fin de que el agente pueda obtener contexto
                    sobre lo que pasa con paquetes parecidos al del usuario.
                  </p>
                  <p className="text-gray-300"> Parámetros necesarios</p>
                  <ul className="ml-5 max-w-md space-y-1 text-gray-300 list-disc list-inside dark:text-gray-300">
                    <li>Número de seguimiento (tracking)</li>
                  </ul>
                </div>
              </li>
              <li>
                send_current_delivery_address
                <div style={{ marginLeft: "20px" }}>
                  <p className="text-gray-300">
                    Envia la direccion de entrega actual en nuestro sistema para
                    el paquete del cliente.
                  </p>
                  <p className="text-gray-300"> Parámetros necesarios</p>
                  <ul className="ml-5 max-w-md space-y-1 text-gray-300 list-disc list-inside dark:text-gray-300">
                    <li>Número de seguimiento (tracking)</li>
                    <li>Número de telefono del paquete.</li>
                  </ul>
                </div>
              </li>
            </ul>
          </>
        );
        break;
      case "MCP Agent":
        agent_description = (
          <>
            <p>
              Este agente está diseñado para ejecutar acciones directas y
              específicas sobre paquetes y solicitudes de los usuarios en el
              sistema de Moovin.
            </p>
            <p>
              Sus herramientas generan tickets o realizan acciones operativas
              reales con lo cual sus instrucciones deben ser muy especificas.
            </p>
            <h1>Herramientas disponibles</h1>
            <ul
              className="max-w-md space-y-1 list-disc list-inside"
              style={{ color: "#02ffa2ff" }}
            >
              <li>
                pickup_ticket
                <div style={{ marginLeft: "20px", color: "#d1d1d1ff" }}>
                  <p className="text-gray-300">
                    Crea un Ticket en Zoho Desk para solicitar el retiro en sede
                    de un paquete.
                  </p>
                  <p className="text-gray-300"> Parámetros necesarios</p>
                  <ul className="ml-5 max-w-md space-y-1 text-gray-300 list-disc list-inside dark:text-gray-300">
                    <li> Número de seguimiento (tracking)</li>
                    <li>Descripción o razón de la solicitud (obligatoria)</li>
                  </ul>
                  <p>
                    No aplicable a paquetes cancelados, devueltos a origen o con
                    dos intentos fallidos de entrega.
                  </p>
                  <p>
                    El Agente obtiene numero de Ticket
                  </p>
                </div>
              </li>
              <li>
                escalate_to_human
                <div style={{ marginLeft: "20px", color: "#d1d1d1ff" }}>
                  <p className="text-gray-300">
                    Crea un Ticket en Zoho Desk para informar a Servicio al
                    Cliente sobre una Escalacion.
                  </p>
                  <p className="text-gray-300"> Parámetros necesarios</p>
                  <ul className="ml-5 max-w-md space-y-1 text-gray-300 list-disc list-inside dark:text-gray-300">
                    <li>Correo y Numero de Telefono de referencia(Minimo 1)</li>
                    <li> Nombre de Referencia (Obligatorio)</li>
                    <li> Número de seguimiento (Opcional)</li>
                    <li> Descripción de la escalacion (Obligatorio)</li>
                  </ul>
                  <p>
                    El Agente obtiene numero de Ticket
                  </p>
                </div>
              </li>
              <li>
                request_electronic_receipt_ticket
                <div style={{ marginLeft: "20px", color: "#d1d1d1ff" }}>
                  <p>
                    Crea un Ticket en Zoho Desk solicitando la emisión de una
                    factura electrónica con los datos dados.
                  </p>
                  <p className="text-gray-300">Parámetros necesarios</p>
                  <ul className="ml-5 max-w-md space-y-1 text-gray-300 list-disc list-inside dark:text-gray-300">
                    <li> Cédula jurídica</li>
                    <li>Nombre jurídico</li>
                    <li>Dirección completa</li>
                    <li>Número de seguimiento (tracking)</li>
                    <li>Descripción de la solicitud</li>
                  </ul>
                  <p>Todos los parámetros son obligatorios.</p>
                  <p>
                    El Agente obtiene numero de Ticket
                  </p>
                </div>
              </li>
              <li>
                package_damaged_ticket
                <div style={{ marginLeft: "20px", color: "#d1d1d1ff" }}>
                  <p className="text-gray-300">
                    Crea un Ticket en Zoho Desk para reportar el Daño de un
                    paquete.
                  </p>
                  <p className="text-gray-300"> Parámetros necesarios</p>
                  <ul className="ml-5 max-w-md space-y-1 text-gray-300 list-disc list-inside dark:text-gray-300">
                    <li>Número de seguimiento (tracking)</li>
                    <li>Descripción del daño</li>
                    <li>Fotografía del daño</li>
                  </ul>
                  <p className="text-gray-300">
                    El reporte debe realizarse dentro de los 2 días posteriores
                    a la entrega
                  </p>
                  <p className="text-gray-300">
                    El proposito del ticket es únicamente informar el daño;
                    cualquier compensación debe gestionarse con la tienda donde
                    se compró el producto.
                  </p>
                  <p>
                    El Agente obtiene numero de Ticket
                  </p>
                </div>
              </li>
              <li>
                change_delivery_address
                <div style={{ marginLeft: "20px", color: "#d1d1d1ff" }}>
                  <p className="text-gray-300">
                    Cambia la dirección de entrega de un paquete en API de
                    Desarrollo de Moovin.
                  </p>
                  <p className="text-gray-300"> Parámetros necesarios</p>
                  <ul className="ml-5 max-w-md space-y-1 list-disc list-inside">
                    <li>Número de seguimiento (tracking)</li>
                    <li>Número de teléfono asociado</li>
                    <li>
                      Confirmación de la dirección actual (enviada al usuario
                      con send_current_delivery_address)
                    </li>
                    <li>
                      Confirmación de la nueva dirección (enviada con
                      send_delivery_address_requested)
                    </li>
                  </ul>
                  <p className="text-gray-300">
                    Ideal de uso por parte del Agente
                  </p>
                  <ol className="ps-5  space-y-1 list-decimal list-inside">
                    <li>Verificar datos iniciales (tracking y teléfono).</li>
                    <li>
                      Confirmar dirección actual con
                      send_current_delivery_address.
                    </li>
                    <li>
                      Confirmar dirección nueva enviada por el usuario en
                      formato de ubicación de WhatsApp con
                      send_delivery_address_requested.
                    </li>
                    <li>
                      Ejecutar el cambio de dirección solo después de ambas
                      confirmaciones.
                    </li>
                  </ol>
                  <p>
                    La nueva dirección debe recibirse en formato de ubicación
                    válido de WhatsApp (texto no es aceptado).
                  </p>
                </div>
              </li>
              <li>
                send_current_delivery_address
                <div style={{ marginLeft: "20px" }}>
                  <p className="text-gray-300">
                    Envía al usuario mediante Whatsapp, en formato de ubicación,
                    la dirección de entrega actual del paquete.
                  </p>
                  <p className="text-gray-300">Parámetros necesarios</p>
                  <ul className="ml-5 max-w-md space-y-1 text-gray-300 list-disc list-inside dark:text-gray-300">
                    <li> Número de seguimiento (tracking)</li>
                    <li> Número de teléfono</li>
                  </ul>
                  <p className="text-gray-300">
                    Es el segundo paso obligatorio en la herramienta
                    change_delivery_address, con esto se confirma la intencion
                    del usuario de cambiar esa direccción a una nueva.
                  </p>
                  <p className="text-gray-300"></p>
                </div>
              </li>
              <li>
                send_delivery_address_requested
                <div style={{ marginLeft: "20px" }}>
                  <p className="text-gray-300">
                    Envía al usuario mediante Whatsapp, en formato de ubicación,
                    la nueva dirección que él mismo proporcionó.
                  </p>
                  <p className="text-gray-300">Parámetros necesarios</p>
                  <ul className="ml-5 max-w-md space-y-1 text-gray-300 list-disc list-inside dark:text-gray-300">
                    <li>
                      El usuario debe haber enviado una ubicación válida en
                      formato ubicación de Whatsapp
                    </li>
                  </ul>
                  <p className="text-gray-300">
                    Es el tercer paso obligatorio en la herramienta
                    change_delivery_address Al realizar este paso, se confirma
                    la nueva dirección como correcta.
                  </p>
                </div>
              </li>
            </ul>
          </>
        );
        break;
      case "General Agent":
        agent_description = (
          <>
            <p>
              Este agente esta pensado para dar una atencion General, encargado
              de responder las consultas generales.
            </p>
            <p>
              Es quien inicia el Flujo, al recibir un mensaje redirige al agente
              correcto en caso de ser necesario o atiende al usuario.
            </p>
          </>
        );
        break;
      case "Railing Agent":
        agent_description = (
          <>
            <div
              style={{ display: "flex", flexDirection: "column", gap: "5px" }}
            >
              <p>
                Esta agente esta diseñado para intervenir cuando se activa un
                guardrail, ya sea por un mensaje inadecuado del usuario o por
                una respuesta incorrecta de un agente
              </p>
              <p>
                Este prompt sirve para dirigir su comportamiento cuando alguna
                de estas excepciones pase, es por esto que el agente recibe
                tambien el motivo por el que el guardarail fue activado.
              </p>
              <p>
                El Agente puede realizar handoffs a otros agentes, pero los
                otros agentes NO pueden hacer un handoff a este agente, por lo
                que este agente entra en el flujo UNICAMENTE si un guardarail
                fue activado, ademas de esto si el Railing Agent realiza un
                handoff, el nuevo agente obtendra como parte de su prompt el
                motivo por el cual el agente hizo el handoff a el.
              </p>
            </div>
          </>
        );
        break;
      case "General Prompt":
        agent_description = (
          <>
            <p>Prompt general que compartido por todos los agentes.</p>
            <p>
              Es el lugar ideal para establecer reglas de comportamiento general
              para todos los agentes, o contexto compartido.
            </p>
          </>
        );
        break;
      case "Input":
        agent_description = (
          <>
            <p>
              Prompt que contiene las Instrucciones por la que se activa el
              guardrail del Input o no.
            </p>
            <p>
              Establece que cosas y que no son deseadas para la conversación. En
              caso de que alguna de las excepciones comentadas en este prompt
              sea detectada, el guardarail se activará y pasará la consulta al
              Railing Agent, este atenderá la consula o redigirá al agente
              correcto, en este último caso informando el por que hizo el
              handoff a él directamente.
            </p>
          </>
        );
        break;
      case "Output":
        agent_description = (
          <>
            <p>
              Establece una serie de prohibiciones o reglas sobre lo que los
              agentes pueden o no mencionar en su respuesta.
            </p>
            <p>
              En caso de que alguna de las excepciones comentadas en este prompt
              sea detectada, el guardarail se activará y pasará la consulta al
              Railing Agent, este atenderá la consula o redigirá al agente
              correcto, en este último caso informando el por que hizo el
              handoff a él directamente.
            </p>
          </>
        );
        break;

      default:
        break;
    }

    return (
      <div
        style={{
          whiteSpace: "pre-line",
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
          maxHeight: "98%",
          width: "100%",
          padding: "0.4rem",
          fontSize: "clamp(0.1rem, 0.3rem + 0.3vw, 0.8rem)",
        }}
      >
        {agent_description}
      </div>
    );
  };

  return (
    <div
      style={{
        maxHeight: "100%",
        overflow: "auto",
      }}
    >
      {mountDescription()}
    </div>
  );
};

export default AgentDescription;
