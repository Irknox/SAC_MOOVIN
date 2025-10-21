'use strict';
const ari = require("ari-client");

const ARI_URL   = process.env.ARI_URL   || 'http://127.0.0.1:8088';
const ARI_USER  = process.env.ARI_USER  || 'ari';
const ARI_PASS  = process.env.ARI_PASS  || 'secret';
const APP_NAME  = process.env.ARI_APP   || 'app';

const EXT_HOST  = process.env.EM_EXTERNAL_HOST || '127.0.0.1';
const EXT_PORT  = parseInt(process.env.EM_EXTERNAL_PORT || '40010', 10);
const EM_FORMAT = process.env.EM_FORMAT || 'slin16';

function log(...args) { console.log('[ARI]', ...args); }
function err(...args) { console.error('[ARI][ERR]', ...args); }

ari.connect(ARI_URL, ARI_USER, ARI_PASS)
  .then(client => {
    log('Conectado a ARI:', ARI_URL, 'app=', APP_NAME);

    client.on('StasisStart', async (event, incoming) => {
    if (event.application !== APP_NAME) return;

    const chName = (incoming.name || incoming.json?.name || "");
    const isExternalMedia = chName.startsWith('UnicastRTP/');

    if (isExternalMedia) {
        return; 
    }
    await incoming.answer();
    const bridge = client.Bridge();
    await bridge.create({ type: 'mixing' });
    const em = await client.channels.externalMedia({
        app: APP_NAME,
        external_host: `${EXT_HOST}:${EXT_PORT}`,
        format: EM_FORMAT,
        direction: 'both'
    });
    await bridge.addChannel({ channel: incoming.id });
    await bridge.addChannel({ channel: em.id });
        log('Canales agregados al bridge. SIP=', incoming.id, ' EM=', em.id);

        const hangupAll = async () => {
          try {
            if (em && em.id)    await em.hangup().catch(()=>{});
            if (incoming && incoming.id) await incoming.hangup().catch(()=>{});
            if (bridge && bridge.id) await bridge.destroy().catch(()=>{});
            log('Limpieza OK');
          } catch (e) { err('Errores en cleanup:', e.message); }
        };

        const onEnd = (ev, ch) => {
          if (!ch || (ch.id !== incoming.id && ch.id !== em.id)) return;
          log('StasisEnd:', ch.id);
          hangupAll();
        };
        client.on('StasisEnd', onEnd);
        await incoming.setChannelVar({variable: 'BRIDGE_ID', value: bridge.id}).catch(()=>{});
        await em.setChannelVar({variable: 'BRIDGE_ID', value: bridge.id}).catch(()=>{});
        await incoming.setChannelVar({variable: 'EM_EXTERNAL', value: `${EXT_HOST}:${EXT_PORT}`}).catch(()=>{});
        await em.setChannelVar({variable: 'EM_FORMAT', value: EM_FORMAT}).catch(()=>{});

      } catch (e) {
        err('Fallo en StasisStart handler:', e.stack || e.message);
        try { await incoming.hangup(); } catch(_) {}
      }
    });

    client.start(APP_NAME);
    log('App ARI iniciada:', APP_NAME, '| ExternalMedia →', `${EXT_HOST}:${EXT_PORT}`, 'format=', EM_FORMAT);
  })
  .catch(e => {
    err('No se pudo conectar a ARI:', e.message);
    process.exit(1);
  });
