

"""
SilverAI_ari.py
--------------
App ARI minimalista para:
- Responder llamadas que entren a la app 'silverai' 
- Crear un bridge mixing/proxy_media
- Crear un canal ExternalMedia hacia 127.0.0.1:40000
- Añadir ambos canales al bridge
- Limpiar recursos al colgar

Es escuchado por el SDK
"""

import os
import sys
import time
import signal
import logging
from typing import Dict, Optional
import ari 



# --------------------------
# Config vía variables de entorno
# --------------------------
ARI_URL            = os.getenv("ARI_URL")
ARI_USER           = os.getenv("ARI_USER", "asterisk")
ARI_PASS           = os.getenv("ARI_PASS", "asterisk")
ARI_APP            = os.getenv("ARI_APP", "app") 

EXTERNAL_HOST         = os.getenv("EXTERNAL_HOST")  # host:port en gateway SDK
EXTERNAL_FORMAT       = os.getenv("EXTERNAL_FORMAT", "alaw")           # alaw | ulaw | slin16
EXTERNAL_TRANSPORT    = os.getenv("EXTERNAL_TRANSPORT", "udp")         # udp | tcp | websocket
EXTERNAL_ENCAPSULATION= os.getenv("EXTERNAL_ENCAPSULATION", "rtp")     # rtp | audiosocket | none
EXTERNAL_DIRECTION    = os.getenv("EXTERNAL_DIRECTION", "both")        # both | in | out

MAX_CALL_MS        = int(os.getenv("MAX_CALL_MS", "0"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# --------------------------
# Logging
# --------------------------
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("silverai_ari")

# --------------------------
# Estado en memoria
# --------------------------
class CallState:
    """Estructura para trackear recursos por canal SIP."""
    def __init__(self, sip_channel_id: str):
        self.sip_channel_id = sip_channel_id
        self.bridge_id: Optional[str] = None
        self.ext_channel_id: Optional[str] = None
        self.started_at_ms = int(time.time() * 1000)

CALLS: Dict[str, CallState] = {}
EXT_TO_SIP: Dict[str, str] = {}

client: Optional[ari.Client] = None
_running = True

# --------------------------
# Utilidades
# --------------------------
def ms_since(ts_ms: int) -> int:
    return int(time.time() * 1000) - ts_ms

def safe_get(dct: dict, *path, default=None):
    cur = dct
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur

# --------------------------
# Manejadores de eventos ARI
# --------------------------
def on_stasis_start(channel_obj, event):
    """
    Se dispara cuando un canal entra a la app ARI (StasisStart).
    Puede ser:
      - El canal SIP entrante 
      - El canal ExternalMedia
    """
    ch_id = safe_get(event, "channel", "id")
    ch_name = safe_get(event, "channel", "name")
    log.info(f"StasisStart: channel_id={ch_id} name={ch_name}")

    is_external = ch_name and (ch_name.startswith("UnicastRTP") or ch_name.startswith("AudioSocket") or ch_name.startswith("WebSocketChannel"))
    if is_external:
        sip_id = EXT_TO_SIP.get(ch_id)
        if not sip_id:
            log.info(f"External channel {ch_id} llegó antes de mapear; pequeño delay para resolver bridge…")
            time.sleep(0.3)
            sip_id = EXT_TO_SIP.get(ch_id)

        if not sip_id or sip_id not in CALLS:
            log.warning(f"No encuentro SIP asociado para external channel {ch_id}. Ignoro por ahora.")
            return

        state = CALLS[sip_id]
        if not state.bridge_id:
            log.warning(f"No hay bridge todavía para SIP {sip_id}. Ignoro external {ch_id}.")
            return

        try:
            bridge = client.bridges.get(bridgeId=state.bridge_id)
            bridge.addChannel(channel=ch_id)
            log.info(f"Añadido external channel {ch_id} al bridge {state.bridge_id}")
        except Exception as e:
            log.error(f"Error añadiendo external {ch_id} al bridge {state.bridge_id}: {e}")
        return
    sip_id = ch_id
    CALLS[sip_id] = CallState(sip_channel_id=sip_id)

    channel = client.channels.get(channelId=sip_id)
    try:
        channel.answer()
        log.info(f"SIP {sip_id} contestado")
        bridge = client.bridges.create(type="mixing,proxy_media")
        CALLS[sip_id].bridge_id = bridge.id
        log.info(f"Bridge creado: {bridge.id}")
        bridge.addChannel(channel=sip_id)
        log.info(f"SIP {sip_id} agregado al bridge {bridge.id}")

        # Cortar al límite de duración (Desactivado)
        if MAX_CALL_MS > 0:
            def _enforce_limit():
                try:
                    if sip_id in CALLS and ms_since(CALLS[sip_id].started_at_ms) > MAX_CALL_MS:
                        log.info(f"Max call time superado para {sip_id}. Colgando.")
                        client.channels.hangup(channelId=sip_id)
                except Exception as e:
                    log.warning(f"Al forzar límite: {e}")
            client.add_periodic_task(3.0, _enforce_limit)

        # Canar ExternalMedia apuntado al Getaway
        params = {
            "app": ARI_APP,
            "external_host": EXTERNAL_HOST,      
            "format": EXTERNAL_FORMAT,           
            "transport": EXTERNAL_TRANSPORT,      
            "encapsulation": EXTERNAL_ENCAPSULATION, 
            "connection_type": "client",         
            "direction": EXTERNAL_DIRECTION    
        }
        ext_ch = client.channels.externalMedia(**params)
        CALLS[sip_id].ext_channel_id = ext_ch.id
        EXT_TO_SIP[ext_ch.id] = sip_id
        log.info(f"ExternalMedia creado: {ext_ch.id} -> {EXTERNAL_HOST} ({EXTERNAL_FORMAT}/{EXTERNAL_TRANSPORT}/{EXTERNAL_ENCAPSULATION})")

    except Exception as e:
        log.error(f"Error preparando llamada para SIP {sip_id}: {e}")
        try:
            channel.hangup()
        except Exception:
            pass
        cleanup_call(sip_id)

def on_stasis_end(channel_obj, event):
    """ Limpieza cuando un canal sale de la app (colgado). """
    ch_id = safe_get(event, "channel", "id")
    ch_name = safe_get(event, "channel", "name")
    log.info(f"StasisEnd: channel_id={ch_id} name={ch_name}")

    if ch_id in EXT_TO_SIP:
        sip_id = EXT_TO_SIP.pop(ch_id, None)
        log.info(f"External {ch_id} terminó (SIP asociado: {sip_id})")
        return

    cleanup_call(ch_id)

def cleanup_call(sip_id: str):
    """ Cierra bridge, cuelga external (si existe) y borra estado. """
    state = CALLS.pop(sip_id, None)
    if not state:
        return

    if state.ext_channel_id:
        try:
            client.channels.hangup(channelId=state.ext_channel_id)
            log.info(f"External {state.ext_channel_id} colgado")
        except Exception:
            pass
        EXT_TO_SIP.pop(state.ext_channel_id, None)

    if state.bridge_id:
        try:
            br = client.bridges.get(bridgeId=state.bridge_id)
            br.destroy()
            log.info(f"Bridge {state.bridge_id} destruido")
        except Exception:
            pass

    try:
        client.channels.hangup(channelId=sip_id)
    except Exception:
        pass

# --------------------------
# Señales del sistema
# --------------------------
def _signal_handler(sig, frame):
    global _running
    log.info(f"Señal {sig} recibida. Cerrando…")
    _running = False
    try:
        for sip_id in list(CALLS.keys()):
            cleanup_call(sip_id)
    finally:
        try:
            client.close()
        except Exception:
            pass
        sys.exit(0)

# --------------------------
# Main
# --------------------------
def main():
    global client
    try:
        log.info(f"Conectando a ARI: {ARI_URL} (app={ARI_APP})")
        client = ari.connect(ARI_URL, ARI_USER, ARI_PASS)
    except Exception as e:
        log.error(f"No se pudo conectar a ARI: {e}")
        sys.exit(1)

    client.on_channel_event('StasisStart', on_stasis_start)
    client.on_channel_event('StasisEnd', on_stasis_end)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    log.info("Escuchando eventos…")
    try:
        client.run(apps=[ARI_APP])
    except KeyboardInterrupt:
        _signal_handler("SIGINT", None)
    except Exception as e:
        log.error(f"Fallo run(): {e}")
        _signal_handler("SIGTERM", None)

if __name__ == "__main__":
    main()
