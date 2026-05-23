"""FastAPI server: auth + lobby + WebSocket poker game."""
from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field

from auth import hash_password, verify_password, create_access_token, get_current_user, get_user_from_token
from game_manager import manager, STAKE_TIERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mongo
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
manager.set_db(db)

app = FastAPI()
api = APIRouter(prefix="/api")

STARTING_CHIPS = 1000.0
AVATARS = ["man1", "man2", "man3", "woman1", "woman2", "woman3"]


# -------- Root --------
@app.get("/")
async def root():
    return {"status": "ok", "message": "ALIXAN API işləyir"}


# -------- Models --------
class RegisterReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    username: str = Field(min_length=2, max_length=20)
    avatar_id: str = "man1"


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class UpdateAvatarReq(BaseModel):
    avatar_id: str


class JoinTableReq(BaseModel):
    tier_id: str


# -------- Helpers --------
def _set_cookies(response: Response, token: str):
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=7 * 24 * 3600, path="/",
    )


async def _get_user(request: Request):
    return await get_current_user(request, db)


# -------- Auth Endpoints --------
@api.post("/auth/register")
async def register(req: RegisterReq, response: Response):
    email = req.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    if req.avatar_id not in AVATARS:
        raise HTTPException(status_code=400, detail="Invalid avatar")
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": email,
        "username": req.username,
        "avatar_id": req.avatar_id,
        "password_hash": hash_password(req.password),
        "chips": STARTING_CHIPS,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user_doc)
    token = create_access_token(user_id, email)
    _set_cookies(response, token)
    return {
        "id": user_id, "email": email, "username": req.username,
        "avatar_id": req.avatar_id, "chips": STARTING_CHIPS, "token": token,
    }


@api.post("/auth/login")
async def login(req: LoginReq, response: Response):
    email = req.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user["id"], email)
    _set_cookies(response, token)
    return {
        "id": user["id"], "email": user["email"], "username": user["username"],
        "avatar_id": user["avatar_id"], "chips": user["chips"], "token": token,
    }


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(request: Request):
    user = await _get_user(request)
    return {
        "id": user["id"], "email": user["email"], "username": user["username"],
        "avatar_id": user["avatar_id"], "chips": user["chips"],
    }


@api.patch("/auth/avatar")
async def update_avatar(req: UpdateAvatarReq, request: Request):
    user = await _get_user(request)
    if req.avatar_id not in AVATARS:
        raise HTTPException(status_code=400, detail="Invalid avatar")
    await db.users.update_one({"id": user["id"]}, {"$set": {"avatar_id": req.avatar_id}})
    return {"ok": True, "avatar_id": req.avatar_id}


# -------- Lobby Endpoints --------
@api.get("/tiers")
async def get_tiers():
    return STAKE_TIERS


@api.get("/tables")
async def list_tables():
    return manager.list_tables()


@api.post("/tables/quick-seat")
async def quick_seat(req: JoinTableReq, request: Request):
    user = await _get_user(request)
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    if not fresh:
        raise HTTPException(status_code=404, detail="User not found")
    tier = next((t for t in STAKE_TIERS if t["id"] == req.tier_id), None)
    if not tier:
        raise HTTPException(status_code=400, detail="Invalid tier")
    if fresh["chips"] < tier["min_buyin"]:
        raise HTTPException(status_code=400, detail=f"Need at least {tier['min_buyin']} chips for {tier['name']} stakes")
    table_id = await manager.seat_user(fresh, req.tier_id)
    if not table_id:
        raise HTTPException(status_code=400, detail="No open seats")
    return {"table_id": table_id}


@api.post("/tables/leave")
async def leave_table(request: Request):
    user = await _get_user(request)
    await manager.leave_table(user["id"])
    return {"ok": True}


# -------- WebSocket --------
@app.websocket("/api/ws/table/{table_id}")
async def ws_table(websocket: WebSocket, table_id: str, token: str = ""):
    if not token:
        token = websocket.cookies.get("access_token", "")
    user = await get_user_from_token(token, db) if token else None
    if not user:
        await websocket.close(code=4401)
        return
    table = manager.tables.get(table_id)
    if not table:
        await websocket.close(code=4404)
        return
    seat = table.find_player(user["id"])
    if seat is None:
        await websocket.close(code=4403)
        return
    await websocket.accept()
    await manager.connect(table_id, user["id"], websocket)
    try:
        while True:
            data = await websocket.receive_json()
            t = data.get("type")
            if t == "action":
                action = data.get("action")
                amount = float(data.get("amount") or 0)
                result = await manager.player_action(table, user["id"], action, amount)
                if result.get("error"):
                    await websocket.send_json({"type": "error", "message": result["error"]})
            elif t == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("ws error: %s", e)
    finally:
        await manager.disconnect(table_id, user["id"])


# -------- Mount router & CORS --------
app.include_router(api)

frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    logger.info("DB indexes created")


@app.on_event("shutdown")
async def shutdown():
    client.close()

