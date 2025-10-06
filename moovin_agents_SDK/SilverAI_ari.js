// App ARI minimalista para:
// - Responder llamadas que entren a la app ARI (env ARI_APP)
// - Crear un bridge mixing/proxy_media
// - Crear un canal ExternalMedia hacia EXTERNAL_HOST
// - Añadir ambos canales al bridge
// - Limpiar recursos al colgar
//
// --------------------------------------------

require('dotenv').config();
const ari = require('ari-client');

const {
  ARI_URL,
  ARI_USER = 'asterisk',
  ARI_PASS = 'asterisk',
  ARI_APP = 'app',

  EXTERNAL_HOST,
  EXTERNAL_FORMAT = 'alaw',         
  EXTERNAL_TRANSPORT = 'udp',        
  EXTERNAL_ENCAPSULATION = 'rtp',    
  EXTERNAL_DIRECTION = 'both',       

  MAX_CALL_MS = '0',
  LOG_LEVEL = 'INFO',
} = process.env;

const LEVELS = ['ERROR', 'WARN', 'INFO', 'DEBUG'];
const CUR_LEVEL_IDX = Math.max(0, LEVELS.indexOf(String(LOG_LEVEL).toUpperCase()));
const log = {
  error: (msg) => CUR_LEVEL_IDX >= 0 && console.error(ts(), '| ERROR |', msg),
  warn:  (msg) => CUR_LEVEL_IDX >= 1 && console.warn (ts(), '| WARN  |', msg),
  info:  (msg) => CUR_LEVEL_IDX >= 2 && console.log  (ts(), '| INFO  |', msg),
  debug: (msg) => CUR_LEVEL_IDX >= 3 && console.log  (ts(), '| DEBUG |', msg),
};
function ts(){ return new Date().toISOString(); }

// --- Estado en memoria ---
class CallState {
  constructor(sipChannelId) {
    this.sipChannelId = sipChannelId;
    this.bridgeId = null;
    this.extChannelId = null;
    this.startedAtMs = Date.now();
    this.limitTimer = null; // para MAX_CALL_MS
  }
}

const CALLS = new Map();        // sipId -> CallState
const EXT_TO_SIP = new Map();   // extChannelId -> sipId
let client;                     // ari-client instance

// --- Utilidades ---
function msSince(tsMs) {
  return Date.now() - tsMs;
}

function safeGet(obj, pathArr, def = undefined) {
  let cur = obj;
  for (const p of pathArr) {
    if (!cur || typeof cur !== 'object' || !(p in cur)) return def;
    cur = cur[p];
  }
  return cur;
}

function isExternalMediaName(name) {
  if (!name) return false;
  return name.startsWith('UnicastRTP') || name.startsWith('AudioSocket') || name.startsWith('WebSocketChannel');
}

// --- Handlers ARI ---
async function onStasisStart(event, channel) {
  const chId   = safeGet(event, ['channel', 'id']);
  const chName = safeGet(event, ['channel', 'name']);
  log.info(`StasisStart: channel_id=${chId} name=${chName}`);

  // Caso: canal ExternalMedia (llega a la app también)
  if (isExternalMediaName(chName)) {
    let sipId = EXT_TO_SIP.get(chId);
    if (!sipId) {
      log.info(`External ${chId} llegó antes de mapear; esperando 300ms…`);
      await delay(300);
      sipId = EXT_TO_SIP.get(chId);
    }

    if (!sipId || !CALLS.has(sipId)) {
      log.warn(`No encuentro SIP asociado para external ${chId}. Ignoro por ahora.`);
      return;
    }

    const state = CALLS.get(sipId);
    if (!state.bridgeId) {
      log.warn(`No hay bridge todavía para SIP ${sipId}. Ignoro external ${chId}.`);
      return;
    }

    try {
      const bridge = await client.bridges.get({ bridgeId: state.bridgeId });
      await bridge.addChannel({ channel: chId });
      log.info(`Añadido external ${chId} al bridge ${state.bridgeId}`);
    } catch (e) {
      log.error(`Error añadiendo external ${chId} al bridge ${state.bridgeId}: ${e.message}`);
    }
    return;
  }

  // Caso: canal SIP entrante
  const sipId = chId;
  CALLS.set(sipId, new CallState(sipId));
  const ch = await client.channels.get({ channelId: sipId });

  try {
    // Contestar
    await ch.answer();
    log.info(`SIP ${sipId} contestado`);

    // Crear bridge mixing + proxy_media
    const bridge = await client.bridges.create({ type: 'mixing,proxy_media' });
    CALLS.get(sipId).bridgeId = bridge.id;
    log.info(`Bridge creado: ${bridge.id}`);

    await bridge.addChannel({ channel: sipId });
    log.info(`SIP ${sipId} agregado al bridge ${bridge.id}`);

    // Límite de duración
    const maxMs = parseInt(MAX_CALL_MS, 10) || 0;
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

    // Crear ExternalMedia apuntando a gateway
    const params = {
      app: ARI_APP,
      external_host: EXTERNAL_HOST,       // host:port en el gateway/SDK
      format: EXTERNAL_FORMAT,            // códec (p.ej. alaw/ulaw/slin16)
      transport: EXTERNAL_TRANSPORT,      // udp/tcp/websocket
      encapsulation: EXTERNAL_ENCAPSULATION, // rtp/audiosocket/none
      connection_type: 'client',
      direction: EXTERNAL_DIRECTION,      // both/in/out
    };

    const extCh = await client.channels.externalMedia(params);
    CALLS.get(sipId).extChannelId = extCh.id;
    EXT_TO_SIP.set(extCh.id, sipId);
    log.info(`ExternalMedia creado: ${extCh.id} -> ${EXTERNAL_HOST} (${EXTERNAL_FORMAT}/${EXTERNAL_TRANSPORT}/${EXTERNAL_ENCAPSULATION})`);

  } catch (e) {
    log.error(`Error preparando llamada para SIP ${sipId}: ${e.message}`);
    try { await ch.hangup(); } catch {}
    await cleanupCall(sipId);
  }
}

async function onStasisEnd(event, channel) {
  const chId   = safeGet(event, ['channel', 'id']);
  const chName = safeGet(event, ['channel', 'name']);
  log.info(`StasisEnd: channel_id=${chId} name=${chName}`);

  // Si terminó un ExternalMedia, solo desmapear y salir
  if (EXT_TO_SIP.has(chId)) {
    const sipId = EXT_TO_SIP.get(chId);
    EXT_TO_SIP.delete(chId);
    log.info(`External ${chId} terminó (SIP asociado: ${sipId})`);
    return;
  }

  // Si terminó un SIP, limpiar todo
  await cleanupCall(chId);
}

// --- Limpieza de recursos por llamada ---
async function cleanupCall(sipId) {
  const state = CALLS.get(sipId);
  if (!state) return;

  // detener límite
  if (state.limitTimer) {
    clearInterval(state.limitTimer);
    state.limitTimer = null;
  }

  // colgar external si existe
  if (state.extChannelId) {
    try {
      await client.channels.hangup({ channelId: state.extChannelId });
      log.info(`External ${state.extChannelId} colgado`);
    } catch {}
    EXT_TO_SIP.delete(state.extChannelId);
  }

  // destruir bridge si existe
  if (state.bridgeId) {
    try {
      const br = await client.bridges.get({ bridgeId: state.bridgeId });
      await br.destroy();
      log.info(`Bridge ${state.bridgeId} destruido`);
    } catch {}
  }

  // colgar SIP (por si sigue vivo)
  try {
    await client.channels.hangup({ channelId: sipId });
  } catch {}

  CALLS.delete(sipId);
}

// --- Señales ---
async function shutdown(sig) {
  log.info(`Señal ${sig} recibida. Cerrando…`);
  try {
    // limpiar todas las llamadas activas
    const ids = Array.from(CALLS.keys());
    for (const id of ids) {
      await cleanupCall(id);
    }
  } finally {
    try { client && client.close && client.close(); } catch {}
    process.exit(0);
  }
}

process.on('SIGINT',  () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

// --- Main ---
(async () => {
  if (!ARI_URL) {
    log.error('Falta ARI_URL en variables de entorno.');
    process.exit(1);
  }
  if (!EXTERNAL_HOST) {
    log.error('Falta EXTERNAL_HOST (host:port del gateway).');
    process.exit(1);
  }

  try {
    log.info(`Conectando a ARI: ${ARI_URL} (app=${ARI_APP})`);
    client = await ari.connect(ARI_URL, ARI_USER, ARI_PASS);

    // Suscripción a eventos
    client.on('StasisStart', onStasisStart);
    client.on('StasisEnd',   onStasisEnd);
    client.on('error', (err) => log.error(`ARI error: ${err.message}`));
    client.on('close', () => log.info('Conexión ARI cerrada'));

    // Iniciar la app
    await client.start(ARI_APP);
    log.info('Escuchando eventos…');
  } catch (e) {
    log.error(`No se pudo conectar o iniciar ARI: ${e.message}`);
    process.exit(1);
  }
})();

// --- Helpers ---
function delay(ms){ return new Promise(r => setTimeout(r, ms)); }
