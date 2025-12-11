import json
import redis
from datetime import datetime
import os
import pymongo

REDIS_URL = os.environ["REDIS_URL"]
rdb = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
)

def save_to_mongodb(sessions_collection: pymongo.collection.Collection, data: dict) -> bool:
    """Inserta el documento final de la sesión en la colección de MongoDB."""
    try:
        data["_id"] = data.pop("session_id", data.get("session_id", f"error_{datetime.now().timestamp()}"))
        def convert_to_datetime(iso_string):
            if isinstance(iso_string, str):
                return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
            return iso_string
        data["init_date"] = convert_to_datetime(data.get("init_date"))
        data["finish_date"] = convert_to_datetime(data.get("finish_date"))
        result = sessions_collection.insert_one(data) 
        print(f"[INFO] Sesión guardada en Mongo: ID={result.inserted_id}, Resumen: {data.get('summary')}, Total Interacciones: {len(data.get('interactions',[]))}")
        return True
    except Exception as e:
        print(f"[ERROR] Falló la inserción en MongoDB para call_id={data.get('_id', 'Unknown')}: {e}")
        return False

def redis_key(call_id: str) -> str:
    """Clave para la metadata de la llamada (calls:{call_id})."""
    return f"calls:{call_id}"

def save_call_meta(call_id: str, meta: dict, ttl_seconds: int = 3600) -> None:
    """Guarda la metadata de la llamada en Redis (como String)."""
    rdb.set(redis_key(call_id), json.dumps(meta), ex=ttl_seconds)

def interaction_key(call_id: str) -> str:
    """Clave para la lista de interacciones (interactions:{call_id})."""
    return f"interactions:{call_id}"

def append_interaction(call_id: str, interaction_obj: dict) -> None:
    """Agrega una nueva interacción a la lista de Redis de forma atómica (RPUSH)."""
    interaction_json = json.dumps(interaction_obj)
    rdb.rpush(interaction_key(call_id), interaction_json)
    
def get_session_data(call_id: str) -> tuple[str | None, list]:
    """Recupera la metadata (JSON string) y la lista de interacciones (objetos Python) de Redis."""
    meta_json = rdb.get(redis_key(call_id))
    interactions_list_json = rdb.lrange(interaction_key(call_id), 0, -1)
    interactions_list = [json.loads(i) for i in interactions_list_json]
    return meta_json, interactions_list

def delete_session_data(call_id: str) -> None:
    """Limpia ambas claves de Redis al finalizar la sesión."""
    rdb.delete(redis_key(call_id))
    rdb.delete(interaction_key(call_id))