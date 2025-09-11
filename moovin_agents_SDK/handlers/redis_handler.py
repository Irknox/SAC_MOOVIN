import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Union
import redis.asyncio as redis


SESSION_IDLE_SECONDS = 10  * 60  # 10 minutos


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def to_ts(d: datetime) -> float:
    return d.timestamp()

class RedisSession:
    """
    Guarda TODA la sesión en Redis durante la actividad.
    Claves:
      - session:data:{cid} -> String JSON (state, pending_log, last_seen, audit_items?)
      - session:last_seen  -> ZSET  (score = now + 15min para cada {cid})
    """
    def __init__(self, r: redis.Redis):
        self.r = r
        self.zkey = "session:last_seen"

    def _data_key(self, cid: str) -> str:
        return f"session:data:{cid}"

    async def _touch(self, cid: str):
        expiry_ts = to_ts(utcnow()) + SESSION_IDLE_SECONDS
        await self.r.zadd(self.zkey, {cid: expiry_ts})

    async def _load_session_obj(self, cid: str) -> Dict[str, Any]:
        raw = await self.r.get(self._data_key(cid))
        if raw:
            obj = json.loads(raw)
            
            obj.setdefault("state", {})
            obj.setdefault("pending_log", [])
            obj.setdefault("last_seen", utcnow().isoformat())
            obj.setdefault("audit_items", []) 
            return obj
        
        return {"state": {}, "pending_log": [], "last_seen": utcnow().isoformat(), "audit_items": []}

    async def _save_session_obj(self, cid: str, obj: Dict[str, Any]):
        obj["last_seen"] = utcnow().isoformat()
        await self.r.set(self._data_key(cid), json.dumps(obj))
        await self._touch(cid)

    async def upsert_state(self, cid: str, state: Dict[str, Any]):
        key = self._data_key(cid)

        state_jsonable = dict(state)

        ctx = state_jsonable.get("context")
        if hasattr(ctx, "model_dump"):
            state_jsonable["context"] = ctx.model_dump()

        raw = await self.r.get(key)
        if raw:
            obj = json.loads(raw)
            obj["state"] = state_jsonable
            obj.setdefault("audit_items", [])
            obj["last_seen"] = utcnow().isoformat()
        else:
            obj = {
                "state": state_jsonable,
                "pending_log": [],
                "last_seen": utcnow().isoformat(),
                "audit_items": [] 
            }

        await self.r.set(key, json.dumps(obj))
        await self._touch(cid)

    async def append_log(self, cid: str, *, role: str, content: str):
        obj = await self._load_session_obj(cid)
        obj["pending_log"].append({"ts": utcnow().isoformat(), "role": role, "content": content})
        await self._save_session_obj(cid, obj)

    async def get_session(self, cid: str) -> Optional[Dict[str, Any]]:
        raw = await self.r.get(self._data_key(cid))
        return json.loads(raw) if raw else None

    async def delete_session(self, cid: str):
        await self.r.delete(self._data_key(cid))
        await self.r.zrem(self.zkey, cid)

    async def due_sessions(self) -> List[str]:
        now_ts = to_ts(utcnow())
        cids = await self.r.zrangebyscore(self.zkey, min=0, max=now_ts)
        if cids:
            await self.r.zrem(self.zkey, *cids)
        return [cid.decode() for cid in cids]

    # -------------------- Helpers para input_items oficiales --------------------

    async def get_input_items(self, cid: str) -> List[Dict[str, Any]]:
        obj = await self._load_session_obj(cid)
        state = obj.get("state") or {}
        return state.get("input_items", []) or []

    async def set_input_items(self, cid: str, items: List[Dict[str, Any]]):
        obj = await self._load_session_obj(cid)
        state = obj.get("state") or {}
        state["input_items"] = items or []
        obj["state"] = state
        await self._save_session_obj(cid, obj)

    # -------------------- Helpers para audit_items --------------------

    async def get_audit_items(self, cid: str) -> List[Dict[str, Any]]:
        obj = await self._load_session_obj(cid)
        return obj.get("audit_items", []) or []

    async def replace_audit_items(self, cid: str, items: List[Dict[str, Any]]):
        obj = await self._load_session_obj(cid)
        obj["audit_items"] = items or []
        await self._save_session_obj(cid, obj)

    async def append_audit_items(self, cid: str, items: Union[Dict[str, Any], List[Dict[str, Any]]]):
        obj = await self._load_session_obj(cid)
        if isinstance(items, list):
            obj["audit_items"].extend(items)
        else:
            obj["audit_items"].append(items)
        await self._save_session_obj(cid, obj)

    async def clear_audit_items(self, cid: str):
        obj = await self._load_session_obj(cid)
        obj["audit_items"] = []
        await self._save_session_obj(cid, obj)

    # -------------------- Helper para “cerrar sesión” con preferencia audit --------------------

    async def get_session_for_persist(self, cid: str, prefer_audit: bool = True) -> Optional[Dict[str, Any]]:
        """
        Devuelve una COPIA del objeto de sesión para persistencia.
        Si prefer_audit es True y hay audit_items, retorna state.input_items REEMPLAZADOS por audit_items.
        No modifica lo que está guardado en Redis.
        """
        current = await self.get_session(cid)
        if not current:
            return None

        # Deep-ish copy
        session_obj = json.loads(json.dumps(current))

        if prefer_audit:
            audit = (session_obj.get("audit_items") or [])
            if audit:
                session_obj.setdefault("state", {})
                session_obj["state"]["input_items"] = audit

        return session_obj
