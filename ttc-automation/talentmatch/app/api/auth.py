"""用户认证 API — 注册 / 登录 / 个人信息"""
from __future__ import annotations
import os, json, uuid, hashlib, secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from loguru import logger

router = APIRouter(tags=["auth"])

# 用户数据存储路径
USERS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "users")
os.makedirs(USERS_DIR, exist_ok=True)
USERS_FILE = os.path.join(USERS_DIR, "users.json")

JWT_SECRET = os.environ.get("JWT_SECRET", "talentmatch_fixed_secret_2026")


def _load_users() -> dict:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return json.load(f)
    return {}


def _save_users(users: dict):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def _hash_password(password: str) -> str:
    return hashlib.sha256((password + JWT_SECRET).encode()).hexdigest()


def _create_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": (datetime.utcnow() + timedelta(days=7)).isoformat(),
    }
    token = hashlib.sha256((json.dumps(payload, sort_keys=True) + JWT_SECRET).encode()).hexdigest()
    return f"{user_id}:{token}"


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    display_name: str = Field(default="", max_length=50)
    role: str = Field(default="猎头顾问", max_length=30)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class AuthResponse(BaseModel):
    token: str
    user_id: str
    username: str
    display_name: str
    role: str


@router.post("/auth/register")
async def register(req: RegisterRequest):
    users = _load_users()
    if req.username in users:
        raise HTTPException(409, "用户名已存在")
    user_id = str(uuid.uuid4())[:8]
    users[req.username] = {
        "user_id": user_id,
        "username": req.username,
        "password": _hash_password(req.password),
        "display_name": req.display_name or req.username,
        "role": req.role,
        "created_at": datetime.utcnow().isoformat(),
    }
    users[req.username]["_token"] = token = _create_token(user_id)
    _save_users(users)
    logger.info(f"新用户注册: {req.username} ({user_id})")
    return AuthResponse(token=token, user_id=user_id, username=req.username,
                        display_name=users[req.username]["display_name"],
                        role=users[req.username]["role"])


@router.post("/auth/login")
async def login(req: LoginRequest):
    users = _load_users()
    user = users.get(req.username)
    if not user or user["password"] != _hash_password(req.password):
        raise HTTPException(401, "用户名或密码错误")
    token = _create_token(user["user_id"])
    users[req.username]["_token"] = token
    _save_users(users)
    logger.info(f"用户登录: {req.username}")
    return AuthResponse(token=token, user_id=user["user_id"], username=req.username,
                        display_name=user.get("display_name", req.username),
                        role=user.get("role", "猎头顾问"))


@router.get("/auth/me")
async def get_profile(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else request.query_params.get("token", "")
    if not token or ":" not in token:
        raise HTTPException(401, "未登录")
    user_id, token_hash = token.split(":", 1)
    for u in _load_users().values():
        if u.get("user_id") == user_id:
            stored = u.get("_token", "")
            if stored == token:
                return {"user_id": u["user_id"], "username": u["username"],
                        "display_name": u.get("display_name", u["username"]),
                        "role": u.get("role", "猎头顾问")}
    raise HTTPException(401, "Token 无效")


@router.get("/auth/check")
async def check_auth():
    """检查认证服务是否可用"""
    return {"status": "ok", "message": "认证服务运行中"}
