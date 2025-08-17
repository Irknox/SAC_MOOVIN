import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
import redis.asyncio as redis

SESSION_IDLE_SECONDS = 5 * 60  # 10 minutos

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def to_ts(d: datetime) -> float:
    return d.timestamp()

class RedisSession:
    """
    Guarda TODA la sesión en Redis durante la actividad.
    Claves:
      - session:data:{cid} -> String JSON (state, pending_log, last_seen)
      - session:last_seen  -> ZSET  (score = now + 15min para cada {cid})
    """
    def __init__(self, r: redis.Redis):
        self.r = r
        self.zkey = "session:last_seen"

    def _data_key(self, cid: str) -> str:
        return f"session:data:{cid}"

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
            obj["last_seen"] = utcnow().isoformat()
        else:
            obj = {"state": state_jsonable, "pending_log": [], "last_seen": utcnow().isoformat()}

        await self.r.set(key, json.dumps(obj))
        expiry_ts = to_ts(utcnow()) + SESSION_IDLE_SECONDS
        await self.r.zadd(self.zkey, {cid: expiry_ts})

    async def append_log(self, cid: str, *, role: str, content: str):
        key = self._data_key(cid)
        raw = await self.r.get(key)
        obj = json.loads(raw) if raw else {"state": {}, "pending_log": [], "last_seen": utcnow().isoformat()}
        obj["pending_log"].append({"ts": utcnow().isoformat(), "role": role, "content": content})
        obj["last_seen"] = utcnow().isoformat()
        await self.r.set(key, json.dumps(obj))
        expiry_ts = to_ts(utcnow()) + SESSION_IDLE_SECONDS
        await self.r.zadd(self.zkey, {cid: expiry_ts})

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
