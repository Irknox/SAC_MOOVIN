const AgentDescription = ({ agent }) => {
  const mountDescription = () => {
    let agent_description = "";
    switch (agent) {
      case "Package Analyst Agent":
        agent_description = `Este agente está diseñado para gestionar consultas relacionadas con paquetes y proporcionar información clara sobre su estado, fechas de entrega, direcciones de entrega y procesos asociados.
                            Herramientas disponibles:

                                get_SLA
                                Función: Obtiene la fecha estimada de entrega de un paquete.
                                Parámetros requeridos: Número de seguimiento (tracking) y numero de telefono del paquete.

                                get_timeline
                                Función: Recupera los estados de un paquete en orden cronológico, junto con información asociada como la tienda de compra, el número de teléfono y el nombre del dueño del paquete.
                                Parámetros requeridos: Número de seguimiento (tracking) y número de teléfono.
                                Devuelve un orden cronologico de los eventos de mas reciente a mas antiguo, nombre en el paquete, telefono en el paquete y tienda donde se compro si esta disponible.

                                get_likely_package_timelines
                                Función: Devuelve timelines de paquetes similares al del usuario, esto con el fin de que el agente pueda obtener contexto sobre lo que pasa con paquetes parecidos al del usuario.
                                Parámetros requeridos: Número de seguimiento (tracking).

                                send_current_delivery_address
                                Función: Envia la direccion de entrega actual en nuestro sistema para el paquete del cliente.
                                Parámetros requeridos: Número de seguimiento (tracking) y número de teléfono.`;
        break;

      case "MCP Agent":
        agent_description = `Este agente está diseñado para ejecutar acciones directas y específicas sobre paquetes y solicitudes de los usuarios en el sistema de Moovin. 
                            Sus herramientas generan tickets o realizan acciones operativas reales con lo cual sus instrucciones deben ser muy especificas.

                            Herramientas disponibles

                            pickup_ticket
                                Función: Crea un ticket para solicitar el retiro en sede de un paquete.
                                Parámetros necesarios:
                                    Número de seguimiento (tracking)
                                    Descripción o razón de la solicitud (obligatoria)
                                Restricciones:
                                    No aplicable a paquetes cancelados, devueltos a origen o con dos intentos fallidos de entrega.

                            request_electronic_receipt_ticket
                                Función: Solicita la emisión de una factura electrónica por impuestos pagados.
                                Parámetros necesarios:
                                    Cédula jurídica
                                    Nombre jurídico
                                    Dirección completa
                                    Número de seguimiento (tracking)
                                    Descripción de la solicitud
                                Notas: Todos los parámetros son obligatorios. La solicitud es enviada a Zoho Desk.

                            package_damaged_ticket
                                Función: Reporta que un paquete llegó dañado.
                                Parámetros necesarios:
                                    Número de seguimiento
                                    Descripción del daño
                                    Fotografía del daño
                                Restricciones:
                                    El reporte debe realizarse dentro de los 2 días posteriores a la entrega.
                                Notas: El ticket únicamente informa el daño; cualquier compensación debe gestionarse con la tienda donde se compró el producto.

                            change_delivery_address
                                Función: Cambia la dirección de entrega de un paquete.
                                Parámetros necesarios:
                                    Número de seguimiento (tracking)
                                    Número de teléfono asociado
                                    Confirmación de la dirección actual (enviada al usuario con send_current_delivery_address)
                                    Confirmación de la nueva dirección (enviada con send_delivery_address_requested)
                                Flujo de uso:
                                    Verificar datos iniciales (tracking y teléfono).
                                    Confirmar dirección actual con send_current_delivery_address.
                                    Confirmar dirección nueva enviada por el usuario en formato de ubicación de WhatsApp con send_delivery_address_requested.
                                    Ejecutar el cambio de dirección solo después de ambas confirmaciones.
                                Restricciones: La nueva dirección debe recibirse en formato de ubicación válido de WhatsApp (texto no es aceptado).

                            send_current_delivery_address
                                Función: Envía al usuario, en formato de ubicación, la dirección de entrega actual del paquete.
                                Parámetros necesarios:
                                    Número de seguimiento (tracking)
                                    Número de teléfono
                                Uso: Es el primer paso obligatorio antes de change_delivery_address. Al realizar este paso se confirma que el usuario desea cambiarla.

                            send_delivery_address_requested
                                Función: Envía al usuario, en formato de ubicación, la nueva dirección que él mismo proporcionó.
                                Requisitos:
                                    El usuario debe haber enviado una ubicación válida de WhatsApp.
                                Uso: Es el segundo paso obligatorio antes de change_delivery_address. Al realizar este paso, se confirma la nueva direccion.`;
        break;
      case "General Agent":
        agent_description = `Este agente esta pensado en dar una atencion general.
            Es quien inicia el Flujo, redirige al agente correcto en caso de ser necesario o atiende al usuario.`;
        break;
      case "Railing Agent":
        agent_description = `Este agente está diseñado para mantener las conversaciones dentro del flujo de atención de Moovin, asegurando que tanto los mensajes de los usuarios (input) como las respuestas generadas por otros agentes (output) se mantengan dentro de los parámetros deseados.
                            Su tarea principal es intervenir cuando se activa un guardrail, ya sea por un mensaje inadecuado del usuario o por una salida incorrecta de un agente::
                            Este Agente obtiene la razon por la que el guardarail fue activado.
                            
                            Este prompt sirve para dirigir su comportamiento cuando alguna de estas excepciones pase
                            
                            El Agente puede realizar handoffs, pero los otros agentes no pueden hacer un handoff a este agente, este agente entra en el flujo UNICAMENTE si un guardarail fue activado.
                            Si el Agente realiza un handoff, el nuevo agente obtendra como parte de su prompt el motivo por el cual el agente hizo el handoff a el`;
        break;
      case "General Prompt":
        agent_description = `Prompt general que es compartido por todos los agentes.
                            
                            Es el lugar ideal para establecer reglas de comportamiento general para todos los agentes, o contexto compartido.
                            Almacena instrucciones especificas para el comportamiento de los agentes y el flujo.`;
        break;
      case "Input":
        agent_description = `Prompt que contiene las excepciones por la que se activa el guardrail del Input.
                            
                            Establece que cosas y que no son deseadas para la conversacion.
                            En caso de que alguna de las excepciones comentadas sea detectada, el guardarail se activara y pasara la consulta al Railing Agent, este atendera la consula o redigira al agente correcto, en este ultimo caso informando el por que hizo el handoff a el directamente.`;
        break;

      case "Output":
        agent_description = `Prompt que contiene las excepciones por la que se activa el guardrail del Output.
                            
                            Establece una serie de prohibiciones o reglas sobre lo que los agentes pueden o no mencionar en su respuesta.
                            En caso de que alguna de las excepciones comentadas sea detectada, el guardarail se activara y pasara la consulta al Railing Agent, este atendera la consula o redigira al agente correcto, en este ultimo caso informando el por que hizo el handoff a el directamente.`;
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
        }}
      >
        <p
          style={{
            textAlign: "left",
            fontSize: "clamp(0.2rem, 0.3rem + 0.3vw, 0.6rem)",
          }}
        >
          {agent_description}
        </p>
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
