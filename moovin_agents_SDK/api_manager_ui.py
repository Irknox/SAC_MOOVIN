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



##-------------------Drive-------------------##
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


def _get_service_account_credentials():
    proj = os.environ.get("DRIVE_PROJECT_ID")
    email = os.environ.get("DRIVE_CLIENT_EMAIL")
    pkey = os.environ.get("DRIVE_KEY")

    if not (proj and email and pkey):
        raise RuntimeError("Credenciales de Drive no configuradas (JSON o ENV).")

    # La private_key necesita saltos de línea reales
    pkey = pkey.replace("\\n", "\n")

    info = {
        "type": "service_account",
        "project_id": proj,
        "private_key_id": "dummy",  # opcional
        "private_key": pkey,
        "client_email": email,
        "client_id": "dummy",       # opcional
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{email}"
    }
    return service_account.Credentials.from_service_account_info(info, scopes=DRIVE_SCOPES)

def get_drive_service():
    creds = _get_service_account_credentials()
    # cache_discovery=False para evitar warnings en algunos entornos
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def ensure_subfolder(drive, parent_id: str, folder_name: str) -> str:
    # Busca carpeta hijo con nombre exacto bajo parent_id
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
    # Busca un archivo por nombre dentro de la carpeta raíz
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
    # Sube como revisión del mismo archivo
    media = MediaFileUpload(local_path, mimetype="text/plain", resumable=True)
    updated = drive.files().update(
        fileId=file_id,
        media_body=media,
        fields="id,name,webViewLink"
    ).execute()
    return updated


##-------------------Fin Drive-------------------##




BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "prompts"
BACKUP_DIR = BASE_DIR / "prompts_backup"

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        mysql_pool = await create_mysql_pool()
        app.state.mysql_pool = mysql_pool 
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

@app.post("/Handler")
async def manager_ui(request: Request):
    try:
        payload = await request.json()
        if payload.get('request') == 'UsersLastMessages':
            agent_history = await get_users_last_messages(request.app.state.mysql_pool)
            return {"history": agent_history}
        elif payload.get('request') == 'UserHistory':
            request_body = payload.get('request_body')
            user_id = request_body.get('user')
            range = request_body.get('range')
            last_message_id = request_body.get('last_id')
            agent_history = await get_last_messages_by_user(
                request.app.state.mysql_pool, user_id, limit=range, last_id=last_message_id
            )
            return {"history": agent_history}
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
                if current_path:
                    curr_file = Path(current_path)
                    backup_path = BACKUP_DIR / curr_file.name 
                    shutil.copy2(curr_file, backup_path)
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
    
    