from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config import create_mysql_pool
from handlers.main_handler import get_users_last_messages, get_last_messages_by_user
import traceback
import os, httpx,re, shutil,json
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import redis.asyncio as redis
from handlers.redis_handler import RedisSession
from datetime import datetime, timezone


##-------------------Drive-------------------##
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]

def _get_service_account_credentials():
    proj = os.environ.get("DRIVE_PROJECT_ID")
    email = os.environ.get("DRIVE_CLIENT_EMAIL")
    pkey = os.environ.get("DRIVE_KEY")

    if not (proj and email and pkey):
        raise RuntimeError("Credenciales de Drive no configuradas (JSON o ENV).")

    pkey = pkey.replace("\\n", "\n")

    info = {
        "type": "service_account",
        "project_id": proj,
        "private_key_id": "dummy",
        "private_key": pkey,
        "client_email": email,
        "client_id": "dummy",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{email}"
    }
    return service_account.Credentials.from_service_account_info(info, scopes=DRIVE_SCOPES)

def get_drive_service():
    creds = _get_service_account_credentials()
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def ensure_subfolder(drive, parent_id: str, folder_name: str) -> str:
    q = (
        f"mimeType = 'application/vnd.google-apps.folder' and "
        f"name = '{folder_name}' and "
        f"'{parent_id}' in parents and trashed = false"
    )
    resp = drive.files().list(q=q, fields="files(id,name)", pageSize=1).execute()
    files = resp.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    created = drive.files().create(body=metadata, fields="id").execute()
    return created["id"]

def upload_version_file(drive, folder_id: str, local_path: str) -> dict:
    filename = os.path.basename(local_path)
    metadata = {"name": filename, "parents": [folder_id]}
    media = MediaFileUpload(local_path, mimetype="text/plain", resumable=True)
    created = drive.files().create(
        body=metadata,
        media_body=media,
        fields="id, name, webViewLink"
    ).execute()
    return created

def find_file_in_folder(drive, parent_id: str, filename: str) -> str | None:
    q = (
        f"name = '{filename}' and "
        f"'{parent_id}' in parents and trashed = false"
    )
    resp = drive.files().list(
        q=q,
        fields="files(id,name)",
        pageSize=1,
    ).execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None

def update_drive_file(drive, file_id: str, local_path: str) -> dict:
    media = MediaFileUpload(local_path, mimetype="text/plain", resumable=True)
    updated = drive.files().update(
        fileId=file_id,
        media_body=media,
        fields="id,name,webViewLink"
    ).execute()
    return updated
##-------------------Fin Drive-------------------##


##-------------------Inicio de Archivos en Disco-------------------##
BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "prompts"
BACKUP_DIR = BASE_DIR / "prompts_backup"

PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


SEMVER_RE = re.compile(r"_v(\d+\.\d+\.\d+\.\d+)\.txt$")


prompt_bases = {
    "General Agent":         "general_agent",
    "General Prompt":        "general_prompt",
    "MCP Agent":             "mcp_agent",
    "Package Analyst Agent": "package_analyst",
    "Railing Agent":         "railing_agent",
    "Input":                 "input_guardrail_prompt",
    "Output":                "output_guardrail_prompt",
}

def parse_semver(v: str):
    # "1.2.3.4" -> (1,2,3,4)
    return tuple(int(x) for x in v.split("."))

def semver_str(tup):
    return ".".join(str(x) for x in tup)

def find_latest_version_file(slug: str) -> tuple[str|None, tuple|None]:
    """
    Escanea prompts/ y devuelve (filepath, (maj,min,patch,build)) de la versión más alta para el slug.
    Si no hay ninguno, devuelve (None, None).
    """
    latest = (None, None)
    for p in PROMPTS_DIR.glob(f"{slug}_v*.txt"):
        m = SEMVER_RE.search(p.name)
        if not m:
            continue
        ver = parse_semver(m.group(1))
        if latest[1] is None or ver > latest[1]:
            latest = (str(p), ver)
    return latest

def next_version_tuple(curr: tuple|None) -> tuple:
    if curr is None:
        return (0,0,0,1)
    return (curr[0], curr[1], curr[2], curr[3] + 1)

def write_atomic(path: Path, content: str):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path) 

def purge_slug_files(dir_path: Path, slug: str, keep: set[str] | None = None):
    """
    Elimina todos los archivos {slug}_v*.txt en dir_path,
    excepto los cuyo nombre esté en 'keep'.
    """
    keep = keep or set()
    for p in dir_path.glob(f"{slug}_v*.txt"):
        if p.name in keep:
            continue
        try:
            p.unlink()
        except FileNotFoundError:
            pass
##-------------------Fin de Archivos en Disco-------------------##
##-------------------Inicio Auxiliares redis-------------------##


def _utcnow_ts() -> float:
    return datetime.now(timezone.utc).timestamp()

async def _list_active_cids(r) -> list[str]:
    """
    Lee el ZSET 'session:last_seen' y devuelve los CIDs que aún NO han expirado.
    (score = instante en que 'vence' la inactividad; si es > ahora => sigue activa)
    """
    now_ts = _utcnow_ts()
    # min = now, max = +inf: activas
    cids = await r.zrangebyscore("session:last_seen", min=now_ts, max="+inf")
    return [cid.decode() if isinstance(cid, bytes) else cid for cid in cids]

async def _mysql_like_row_from_redis(app, cid: str) -> dict | None:
    """
    Fila idéntica a la que terminaría en sac_agent_memory tras persist_session_to_mysql:
      id, user_id, mensaje_entrante, mensaje_saliente, contexto(OBJETO), fecha(ISO str)
    """
    rs: RedisSession = app.state.redis_session
    sess = await rs.get_session(cid)
    if not sess:
        return None

    state = (sess.get("state") or {}).copy()
    ctx = state.get("context")
    if hasattr(ctx, "model_dump"):  # pydantic
        state["context"] = ctx.model_dump()

    audit_items = await rs.get_audit_items(cid)
    state["input_items"] = audit_items or []

    input_items = state["input_items"]

    def extract_text_from_item(item: dict) -> str | None:
        content = item.get("content")
        if isinstance(content, str):
            return content.strip() or None
        if isinstance(content, list):
            for block in reversed(content):
                text = block.get("text")
                if not isinstance(text, str):
                    continue
                text = text.strip()
                if not text:
                    continue
                # JSON {"response": "..."} soportado
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict) and "response" in parsed and isinstance(parsed["response"], str):
                        return parsed["response"].strip() or None
                except Exception:
                    pass
                return text
        return None

    last_user_msg = None
    last_assistant_msg = None
    for it in reversed(input_items):
        role = it.get("role")
        if not last_assistant_msg and role == "assistant":
            last_assistant_msg = extract_text_from_item(it)
        if not last_user_msg and role == "user":
            last_user_msg = extract_text_from_item(it)
        if last_user_msg and last_assistant_msg:
            break

    mensaje_entrante  = last_user_msg or "[SESSION_FLUSH]"
    mensaje_saliente  = last_assistant_msg or "[BATCHED_SESSION]"

    from datetime import datetime, timezone
    dt = None
    for it in reversed(input_items):
        d = it.get("date")
        if isinstance(d, str) and d:
            try:
                dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
                break
            except Exception:
                pass
    if dt is None:
        dt = datetime.now(timezone.utc)

    dt_naive_utc = dt.astimezone(timezone.utc).replace(tzinfo=None)
    fecha_str = dt_naive_utc.strftime("%Y-%m-%dT%H:%M:%S")

    synth_id = int(9_000_000_000 + dt.timestamp())
    contexto = state
    contexto_json = json.dumps(contexto, ensure_ascii=False)
    

    return {
        "id": synth_id,
        "user_id": cid,
        "mensaje_entrante": mensaje_entrante,
        "mensaje_saliente": mensaje_saliente,
        "contexto": contexto_json, 
        "fecha": fecha_str,      
    }


##-------------------Fin Auxiliares redis-------------------##
##-------------------Inicio de Lifespan-------------------##
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        mysql_pool = await create_mysql_pool()
        app.state.mysql_pool = mysql_pool 
        REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        app.state.redis = redis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=False
        )
        app.state.redis_session = RedisSession(app.state.redis)

        yield
        mysql_pool.close()
        await mysql_pool.wait_closed()
    except Exception as e:
        print("🔥 Error al iniciar FastAPI:", e)
        raise e
app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
##-------------------Fin de Lifespan-------------------##


##-------------------Inicio de Endpoint-------------------##
@app.post("/Handler")
async def manager_ui(request: Request):
    try:
        payload = await request.json()
        if payload.get('request') == 'UsersLastMessages':
            mysql_pool = request.app.state.mysql_pool
            persisted = await get_users_last_messages(mysql_pool)

            by_user = {}
            for row in persisted:
                uid = row.get("user_id") or row.get("user") or row.get("cid")
                if uid:
                    by_user[uid] = row
            active_cids = await _list_active_cids(request.app.state.redis)
            for cid in active_cids:
                redis_row = await _mysql_like_row_from_redis(request.app, cid)
                if redis_row:
                    by_user[cid] = redis_row 

            return {"history": list(by_user.values())}
        elif payload.get('request') == 'UserHistory':
            request_body = payload.get('request_body') or {}
            user_id = request_body.get('user')
            rng = request_body.get('range')
            last_message_id = request_body.get('last_id')

            persisted_history = await get_last_messages_by_user(
                request.app.state.mysql_pool, user_id, limit=rng, last_id=last_message_id
            )

            merged = []
            if not last_message_id:
                live_row = await _mysql_like_row_from_redis(request.app, user_id)
                if live_row:
                    merged.append(live_row)

            merged.extend(persisted_history)
            return {"history": merged}
        
        elif payload.get("request") == "Prompt":
            request_body = payload.get('request_body')
            prompt_type = request_body.get('type')  
            try:
                slug = prompt_bases[prompt_type]
                latest_path, _ = find_latest_version_file(slug)
                if not latest_path:
                    return {"error": f"No existe un archivo versionado para '{prompt_type}'."}
                with open(latest_path, 'r', encoding='utf-8') as f:
                    return {"prompt": f.read(), "path": latest_path}
            except KeyError:
                return {"error": "Invalid prompt type."}
        elif payload.get("request") == "Prompt_update":
            request_body = payload.get('request_body')
            new_prompt = request_body.get('updated_prompt')
            prompt_owner = request_body.get('prompt_owner')  
            try:
                slug = prompt_bases[prompt_owner]
                current_path, current_ver = find_latest_version_file(slug)
                new_ver = next_version_tuple(current_ver)
                new_name = f"{slug}_v{semver_str(new_ver)}.txt"
                new_path = PROMPTS_DIR / new_name

                backup_prev_name = None
                if current_path:
                    curr_file = Path(current_path)

                    purge_slug_files(BACKUP_DIR, slug)
                    shutil.move(str(curr_file), str(BACKUP_DIR / curr_file.name))
                    backup_prev_name = curr_file.name

                    purge_slug_files(PROMPTS_DIR, slug, keep={new_name})

                else:
                    purge_slug_files(PROMPTS_DIR, slug)
                    purge_slug_files(BACKUP_DIR, slug)
                write_atomic(new_path, new_prompt)
                notify_payload = {
                    "request": "promptUpdate",
                    "body": {
                        "prompt": prompt_owner,
                        "content": new_prompt,
                        "version": semver_str(new_ver),
                        "path": str(new_path)
                    }
                }
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.post(f"{os.environ.get('SAC_SDK_URL')}/promptUpdate", json=notify_payload)
                    r.raise_for_status()
                    
                drive_file_id = None
                drive_link = None
                try:
                    drive = get_drive_service()
                    drive_root = os.environ["DRIVE_ROOT_FOLDER_ID"]

                    drive_filenames = {
                        "General Agent":         "General Agent.txt",
                        "General Prompt":        "General Prompt.txt",
                        "MCP Agent":             "MCP Agent.txt",
                        "Package Analyst Agent": "Package Analyst Agent.txt",
                        "Railing Agent":         "Railing Agent.txt",
                        "Input":                 "Input.txt",
                        "Output":                "Output.txt",
                    }
                    target_name = drive_filenames[prompt_owner]
                    file_id = find_file_in_folder(drive, drive_root, target_name)
                    if not file_id:
                        raise RuntimeError(
                            f"No encontré '{target_name}' en la carpeta raíz de Drive. "
                            f"Créalo manualmente y compártelo con la service account como Editor."
                        )

                    updated = update_drive_file(drive, file_id, str(new_path))
                    drive_file_id = updated["id"]
                    drive_link = updated.get("webViewLink")

                except Exception as e:
                    print("⚠️ Error subiendo revisión a Drive:", e)
            
                return {
                    "message": "Prompt updated successfully.",
                    "version": semver_str(new_ver),
                    "path": str(new_path),
                    "backup_prev": (Path(current_path).name if current_path else None)
                }
            except KeyError:
                return {"error": "Invalid prompt type."}
    except Exception as e:
        print("❌ Error en ManagerUI:", e)
        traceback.print_exc()
        return {"error": str(e)}
    
##-------------------Fin de Endpoint-------------------##