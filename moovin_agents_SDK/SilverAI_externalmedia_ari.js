// - Responde SIP entrante
// - Bridge mixing,proxy_media
// - Crea canal ExternalMedia RTP (Opus por defecto) hacia EXTERNAL_HOST
// - Añade SIP y External al bridge
// - Límite de duración opcional
// - Limpieza simétrica y manejo de StasisStart/End para EM

require("dotenv").config();
const ari = require("ari-client");

// --- ENV ---
const {
  ARI_URL,
  ARI_USER = "asterisk",
  ARI_PASS = "asterisk",
  ARI_APP = "app",
  EXTERNAL_HOST,
  EXTERNAL_FORMAT = "ulaw",
  EXTERNAL_TRANSPORT = "udp",
  EXTERNAL_ENCAPSULATION = "rtp",
  EXTERNAL_DIRECTION = "both",
  MAX_CALL_MS = "0",
  LOG_LEVEL = "INFO",
} = process.env;

const LEVELS = ["ERROR", "WARN", "INFO", "DEBUG"];
const CUR_LEVEL_IDX = Math.max(
  0,
  LEVELS.indexOf(String(LOG_LEVEL).toUpperCase())
);
const log = {
  error: (msg) => CUR_LEVEL_IDX >= 0 && console.error(ts(), "| ERROR |", msg),
  warn: (msg) => CUR_LEVEL_IDX >= 1 && console.warn(ts(), "| WARN  |", msg),
  info: (msg) => CUR_LEVEL_IDX >= 2 && console.log(ts(), "| INFO  |", msg),
  debug: (msg) => CUR_LEVEL_IDX >= 3 && console.log(ts(), "| DEBUG |", msg),
};
function ts() {
  return new Date().toISOString();
}

class CallState {
  constructor(sipChannelId) {
    this.sipChannelId = sipChannelId;
    this.bridgeId = null;
    this.extChannelId = null;
    this.startedAtMs = Date.now();
    this.limitTimer = null;
  }
}
const CALLS = new Map();
const EXT_TO_SIP = new Map();
let client;

// --- Utils ---
function msSince(t0) {
  return Date.now() - t0;
}
function delay(ms) {
  return new Promise((r) => setTimeout(r, ms));
}
function safeGet(obj, pathArr, def = undefined) {
  let cur = obj;
  for (const p of pathArr) {
    if (!cur || typeof cur !== "object" || !(p in cur)) return def;
    cur = cur[p];
  }
  return cur;
}
function isExternalMediaName(name) {
  if (!name) return false;
  return name.startsWith("UnicastRTP");
}

// --- Handlers ---
async function addExtToBridgeWithRetry(bridgeId, extId, retries = 5, delayMs = 300) {
  for (let i = 0; i < retries; i++) {
    try {
      const br = await client.bridges.get({ bridgeId });
      await br.addChannel({ channel: extId });
      log.info(`Añadido external ${extId} al bridge ${bridgeId}`);
      return true;
    } catch (e) {
      if (i === retries - 1) throw e;
      await delay(delayMs);
    }
  }
}

async function onStasisStart(event, channel) {
  const chId = safeGet(event, ["channel", "id"]);
  const chName = safeGet(event, ["channel", "name"]);
  log.info(`StasisStart: channel_id=${chId} name=${chName}`);

  if (isExternalMediaName(chName)) {
    let sipId = EXT_TO_SIP.get(chId);
    if (!sipId) {
      log.info(`External ${chId} llegó antes de mapear; esperando 300ms…`);
      await delay(300);
      sipId = EXT_TO_SIP.get(chId);
    }
    if (!sipId || !CALLS.has(sipId)) {
      log.warn(
        `No encuentro SIP asociado para external ${chId}. Ignoro por ahora.`
      );
      return;
    }
    const state = CALLS.get(sipId);
    if (!state.bridgeId) {
      log.warn(
        `No hay bridge todavía para SIP ${sipId}. Ignoro external ${chId}.`
      );
      return;
    }
    try {
      const bridge = await client.bridges.get({ bridgeId: state.bridgeId });
      await addExtToBridgeWithRetry(state.bridgeId, chId, 5, 300);
    } catch (e) {
      log.error(
        `Error añadiendo external ${chId} al bridge ${state.bridgeId}: ${e.message}`
      );
    }
    return;
  }

  // SIP entrante
  const sipId = chId;
  CALLS.set(sipId, new CallState(sipId));
  const ch = await client.channels.get({ channelId: sipId });

  try {
    await ch.answer();
    log.info(`SIP ${sipId} contestado`);
    const bridge = await client.bridges.create({ type: "mixing,proxy_media" });
    CALLS.get(sipId).bridgeId = bridge.id;
    log.info(`Bridge creado: ${bridge.id}`);

    await bridge.addChannel({ channel: sipId });
    log.info(`SIP ${sipId} agregado al bridge ${bridge.id}`);
    const maxMs = parseInt(MAX_CALL_MS, 0) || 0;
    if (maxMs > 0) {
      const st = CALLS.get(sipId);
      st.limitTimer = setInterval(async () => {
        try {
          if (!CALLS.has(sipId)) return;
          if (msSince(st.startedAtMs) > maxMs) {
            log.info(`Max call time superado para ${sipId}. Colgando.`);
            await client.channels.hangup({ channelId: sipId });
          }
        } catch (err) {
          log.warn(`Al forzar límite: ${err.message}`);
        }
      }, 3000);
    }
    const em = await client.channels.externalMedia({
      app: ARI_APP,
      external_host: EXTERNAL_HOST, 
      format: EXTERNAL_FORMAT,
      transport: EXTERNAL_TRANSPORT,
      encapsulation: EXTERNAL_ENCAPSULATION,
      direction: EXTERNAL_DIRECTION,
      originator: sipId,
    });
    const addrVar = await client.channels.getChannelVar({
      channelId: em.id, variable: "UNICASTRTP_LOCAL_ADDRESS"
    });
    const portVar = await client.channels.getChannelVar({
      channelId: em.id, variable: "UNICASTRTP_LOCAL_PORT"
    });
    const astIp   = String(addrVar?.value || "127.0.0.1");
    const astPort = parseInt(String(portVar?.value || "0"), 10);
    log.info(`Asterisk RTP dst aprendido por ARI: ${astIp}:${astPort}`);
    const dgram = require("dgram");
    const sock  = dgram.createSocket("udp4");
    const [bridgeHost, bridgePortStr] = String(EXTERNAL_HOST).split(":");
    const bridgePort = parseInt(bridgePortStr, 10);
    const ctrlMsg = Buffer.from(`CTRL ${astIp}:${astPort}`);
    sock.send(ctrlMsg, bridgePort, bridgeHost, (err) => {
      if (err) log.warn(`No pude enviar CTRL al bridge: ${err.message}`);
      try { sock.close(); } catch {}
    });
    CALLS.get(sipId).extChannelId = em.id;
    EXT_TO_SIP.set(em.id, sipId);
  } catch (e) {
    log.error(`Error preparando llamada para SIP ${sipId}: ${e.message}`);
    try {
      await ch.hangup();
    } catch {}
    await cleanupCall(sipId);
  }
}

async function onStasisEnd(event, channel) {
  const chId = safeGet(event, ["channel", "id"]);
  const chName = safeGet(event, ["channel", "name"]);
  log.info(`StasisEnd: channel_id=${chId} name=${chName}`);

  if (EXT_TO_SIP.has(chId)) {
    const sipId = EXT_TO_SIP.get(chId);
    EXT_TO_SIP.delete(chId);
    log.info(`External ${chId} terminó (SIP asociado: ${sipId})`);
    return;
  }


  await cleanupCall(chId);
  notifyBridgeCallEnded(); 
}

function notifyBridgeCallEnded() {
  const dgram = require("dgram");
  const sock = dgram.createSocket("udp4");
  const [bridgeHost, bridgePortStr] = String(EXTERNAL_HOST).split(":");
  const bridgePort = parseInt(bridgePortStr, 10);
  const ctrlMsg = Buffer.from("CALL_ENDED");
  sock.send(ctrlMsg, bridgePort, bridgeHost, (err) => {
    if (err) log.warn(`No pude enviar CALL_ENDED al bridge: ${err.message}`);
    else log.info(`CALL_ENDED enviado al bridge ${bridgeHost}:${bridgePort}`);
    try {
      sock.close();
    } catch {}
  });
}

async function cleanupCall(sipId) {
  const state = CALLS.get(sipId);
  if (!state) return;

  if (state.limitTimer) {
    clearInterval(state.limitTimer);
    state.limitTimer = null;
  }

  if (state.extChannelId) {
    try {
      await client.channels.hangup({ channelId: state.extChannelId });
      log.info(`External ${state.extChannelId} colgado`);
    } catch {}
    EXT_TO_SIP.delete(state.extChannelId);
  }

  if (state.bridgeId) {
    try {
      const br = await client.bridges.get({ bridgeId: state.bridgeId });
      await br.destroy();
      log.info(`Bridge ${state.bridgeId} destruido`);
    } catch {}
  }

  try {
    await client.channels.hangup({ channelId: sipId });
  } catch {}
  CALLS.delete(sipId);
}

async function shutdown(sig) {
  log.info(`Señal ${sig} recibida. Cerrando…`);
  try {
    const ids = Array.from(CALLS.keys());
    for (const id of ids) await cleanupCall(id);
  } finally {
    try {
      client && client.close && client.close();
    } catch {}
    process.exit(0);
  }
}
process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

// --- Main ---
(async () => {
  if (!ARI_URL) {
    log.error("Falta ARI_URL en variables de entorno.");
    process.exit(1);
  }
  try {
    log.info(`Conectando a ARI: ${ARI_URL} (app=${ARI_APP})`);
    client = await ari.connect(ARI_URL, ARI_USER, ARI_PASS);

    client.on("StasisStart", onStasisStart);
    client.on("StasisEnd", onStasisEnd);
    client.on("error", (err) => log.error(`ARI error: ${err.message}`));
    client.on("close", () => log.info("Conexión ARI cerrada"));

    await client.start(ARI_APP);
    log.info(
      `Escuchando eventos… ExternalMedia -> ${EXTERNAL_HOST} format=${EXTERNAL_FORMAT} encap=${EXTERNAL_ENCAPSULATION} transport=${EXTERNAL_TRANSPORT} dir=${EXTERNAL_DIRECTION}`
    );
  } catch (e) {
    log.error(`No se pudo conectar o iniciar ARI: ${e.message}`);
    process.exit(1);
  }
})();
