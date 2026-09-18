import os
from datetime import datetime, timezone
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        pass

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from supabase import create_client, Client

load_dotenv()  # reads variables from a .env file in the same folder, if present


# =========================================================
# APP
# =========================================================

app = FastAPI(title="Community API")


# =========================================================
# SUPABASE
# =========================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Optional[Client] = None

if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )


def check_supabase():
    if supabase is None:
        raise HTTPException(
            status_code=500,
            detail="Supabase is not configured."
        )


# =========================================================
# EMERGENCY CONTACTS
# =========================================================

EMERGENCY_CONTACTS = [
    {
        "name": "Campus Security",
        "phone": "+91-0000000001"
    },
    {
        "name": "Medical Emergency",
        "phone": "+91-0000000002"
    },
    {
        "name": "Emergency Services",
        "phone": "112"
    },
    {
        "name": "Community Admin",
        "phone": "+91-0000000003"
    }
]


# =========================================================
# MODELS
# =========================================================

class UserCreate(BaseModel):
    client_id: str
    name: str = Field(
        default="Guest",
        max_length=50
    )


class MessageCreate(BaseModel):
    client_id: str
    name: str = Field(
        default="Guest",
        max_length=50
    )
    message: str = Field(
        default="",
        max_length=2000
    )
    image: Optional[str] = Field(
        default=None,
        description="Base64-encoded image data (data URL), optional."
    )


class PostCreate(BaseModel):
    client_id: str
    name: str = Field(
        default="Guest",
        max_length=50
    )
    message: str = Field(
        default="",
        max_length=5000
    )
    image: Optional[str] = Field(
        default=None,
        description="Base64-encoded image data (data URL), optional."
    )


class ReactionCreate(BaseModel):
    client_id: str
    reaction: str


class PinCreate(BaseModel):
    client_id: str


class ReportCreate(BaseModel):
    client_id: str


class ReportIssueCreate(BaseModel):
    client_id: str
    name: str = Field(
        default="Guest",
        max_length=50
    )
    message: str = Field(
        default="",
        max_length=2000
    )


class ResolveCreate(BaseModel):
    client_id: str


class EmergencyCreate(BaseModel):
    client_id: str
    name: str = "Guest"
    message: str = ""


# =========================================================
# ALLOWED REACTIONS
# =========================================================

REACTIONS = [
    "👍",
    "❤️",
    "😂",
    "😮",
    "😢",
    "🚨"
]


# =========================================================
# FRONTEND
# =========================================================

FRONTEND_DIR = os.path.dirname(__file__)

# Maps a URL path to the file it should serve, plus that file's content type.
FRONTEND_FILES = {
    "/": ("login.html", "text/html"),
    "/login.html": ("login.html", "text/html"),
    "/dashboard.html": ("dashboard.html", "text/html"),
    "/community.html": ("community.html", "text/html"),
    "/config.js": ("config.js", "application/javascript"),
}


def serve_frontend_file(filename: str, media_type: str):

    file_path = os.path.join(FRONTEND_DIR, filename)

    if not os.path.exists(file_path):
        return HTMLResponse(
            f"""
            <h2>{filename} not found</h2>
            <p>Put {filename} in the same folder as main.py.</p>
            """,
            status_code=404
        )

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as file:

        return HTMLResponse(
            content=file.read(),
            media_type=media_type
        )


def _make_route(filename: str, media_type: str):
    def route():
        return serve_frontend_file(filename, media_type)
    return route


for url_path, (filename, media_type) in FRONTEND_FILES.items():
    app.get(url_path, response_class=HTMLResponse)(
        _make_route(filename, media_type)
    )


# =========================================================
# REGISTER / UPDATE USER
# =========================================================

@app.post("/api/community/users")
def create_user(data: UserCreate):

    check_supabase()

    client_id = data.client_id.strip()
    name = data.name.strip() or "Guest"

    if not client_id:
        raise HTTPException(
            status_code=400,
            detail="client_id is required."
        )

    result = (
        supabase
        .table("community_users")
        .upsert(
            {
                "client_id": client_id,
                "name": name
            },
            on_conflict="client_id"
        )
        .execute()
    )

    return {
        "success": True,
        "user": result.data[0] if result.data else None
    }


# =========================================================
# GET ALL COMMUNITY MESSAGES
# =========================================================

@app.get("/api/community/messages")
def get_messages():

    check_supabase()

    result = (
        supabase
        .table("community_messages")
        .select("*")
        .order(
            "pinned",
            desc=True
        )
        .order(
            "created_at",
            desc=False
        )
        .execute()
    )

    messages = result.data or []

    # Add reaction counts
    for message in messages:

        reaction_result = (
            supabase
            .table("community_reactions")
            .select("reaction")
            .eq(
                "message_id",
                message["id"]
            )
            .execute()
        )

        counts = {}

        for reaction in REACTIONS:
            counts[reaction] = 0

        for row in reaction_result.data or []:

            reaction = row.get("reaction")

            if reaction in counts:
                counts[reaction] += 1

        message["reaction_counts"] = counts

    return {
        "success": True,
        "messages": messages
    }


# =========================================================
# SEND NORMAL CHAT MESSAGE
# =========================================================

@app.post("/api/community/message")
def send_message(data: MessageCreate):

    check_supabase()

    client_id = data.client_id.strip()
    name = data.name.strip() or "Guest"
    message = data.message.strip()
    image = data.image

    if not message and not image:
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty."
        )

    # -----------------------------------------
    # Make sure user exists
    # -----------------------------------------

    (
        supabase
        .table("community_users")
        .upsert(
            {
                "client_id": client_id,
                "name": name
            },
            on_conflict="client_id"
        )
        .execute()
    )

    # -----------------------------------------
    # Save message
    # -----------------------------------------

    result = (
        supabase
        .table("community_messages")
        .insert(
            {
                "client_id": client_id,
                "author_name": name,
                "message": message,
                "image_data": image,
                "message_type": "chat",
                "pinned": False,
                "reported": False,
                "resolved": False
            }
        )
        .execute()
    )

    return {
        "success": True,
        "type": "chat",
        "message": result.data[0]
        if result.data
        else None
    }


# =========================================================
# CREATE POST
# =========================================================

@app.post("/api/community/post")
def create_post(data: PostCreate):

    check_supabase()

    client_id = data.client_id.strip()
    name = data.name.strip() or "Guest"
    message = data.message.strip()
    image = data.image

    if not message and not image:
        raise HTTPException(
            status_code=400,
            detail="Post cannot be empty."
        )

    # Make sure user exists

    (
        supabase
        .table("community_users")
        .upsert(
            {
                "client_id": client_id,
                "name": name
            },
            on_conflict="client_id"
        )
        .execute()
    )

    # Save post

    result = (
        supabase
        .table("community_messages")
        .insert(
            {
                "client_id": client_id,
                "author_name": name,
                "message": message,
                "image_data": image,
                "message_type": "post",
                "pinned": False,
                "reported": False,
                "resolved": False
            }
        )
        .execute()
    )

    return {
        "success": True,
        "type": "post",
        "post": result.data[0]
        if result.data
        else None
    }


# =========================================================
# REACTION
# =========================================================

@app.post("/api/community/reaction/{message_id}")
def reaction(
    message_id: str,
    data: ReactionCreate
):

    check_supabase()

    if data.reaction not in REACTIONS:

        raise HTTPException(
            status_code=400,
            detail="Invalid reaction."
        )

    # Check whether user already reacted
    existing = (
        supabase
        .table("community_reactions")
        .select("id")
        .eq(
            "message_id",
            message_id
        )
        .eq(
            "client_id",
            data.client_id
        )
        .eq(
            "reaction",
            data.reaction
        )
        .limit(1)
        .execute()
    )

    # -----------------------------------------
    # Remove reaction if it already exists
    # -----------------------------------------

    if existing.data:

        (
            supabase
            .table("community_reactions")
            .delete()
            .eq(
                "id",
                existing.data[0]["id"]
            )
            .execute()
        )

        return {
            "success": True,
            "action": "removed"
        }

    # -----------------------------------------
    # Otherwise add reaction
    # -----------------------------------------

    (
        supabase
        .table("community_reactions")
        .insert(
            {
                "message_id": message_id,
                "client_id": data.client_id,
                "reaction": data.reaction
            }
        )
        .execute()
    )

    return {
        "success": True,
        "action": "added"
    }


# =========================================================
# PIN / UNPIN
# =========================================================

@app.post("/api/community/pin/{message_id}")
def pin_message(
    message_id: str,
    data: PinCreate
):

    check_supabase()

    # Find message

    result = (
        supabase
        .table("community_messages")
        .select("id,pinned")
        .eq(
            "id",
            message_id
        )
        .limit(1)
        .execute()
    )

    if not result.data:

        raise HTTPException(
            status_code=404,
            detail="Message not found."
        )

    current_value = bool(
        result.data[0]["pinned"]
    )

    new_value = not current_value

    (
        supabase
        .table("community_messages")
        .update(
            {
                "pinned": new_value
            }
        )
        .eq(
            "id",
            message_id
        )
        .execute()
    )

    return {
        "success": True,
        "pinned": new_value
    }


# =========================================================
# REPORT A MESSAGE
# (highlights it light red + pins it to top)
# =========================================================

@app.post("/api/community/report/{message_id}")
def report_message(
    message_id: str,
    data: ReportCreate
):

    check_supabase()

    result = (
        supabase
        .table("community_messages")
        .select("id")
        .eq("id", message_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Message not found."
        )

    (
        supabase
        .table("community_messages")
        .update(
            {
                "reported": True,
                "pinned": True,
                "resolved": False
            }
        )
        .eq("id", message_id)
        .execute()
    )

    return {
        "success": True,
        "reported": True
    }


# =========================================================
# REPORT AN ISSUE  (top-bar Report button)
# Creates a brand new message that is immediately
# highlighted red and pinned to the top.
# =========================================================

@app.post("/api/community/report-issue")
def report_issue(data: ReportIssueCreate):

    check_supabase()

    client_id = data.client_id.strip()
    name = data.name.strip() or "Guest"
    message = data.message.strip()

    if not message:
        raise HTTPException(
            status_code=400,
            detail="Please describe the issue."
        )

    # Make sure user exists
    (
        supabase
        .table("community_users")
        .upsert(
            {
                "client_id": client_id,
                "name": name
            },
            on_conflict="client_id"
        )
        .execute()
    )

    result = (
        supabase
        .table("community_messages")
        .insert(
            {
                "client_id": client_id,
                "author_name": name,
                "message": message,
                "image_data": None,
                "message_type": "report",
                "pinned": True,
                "reported": True,
                "resolved": False
            }
        )
        .execute()
    )

    return {
        "success": True,
        "type": "report",
        "message": result.data[0] if result.data else None
    }


# =========================================================
# TOGGLE RESOLVED / NOT RESOLVED
# (red highlight -> green when marked resolved)
# =========================================================

@app.post("/api/community/resolve/{message_id}")
def resolve_message(
    message_id: str,
    data: ResolveCreate
):

    check_supabase()

    result = (
        supabase
        .table("community_messages")
        .select("id,resolved")
        .eq("id", message_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Message not found."
        )

    current_value = bool(result.data[0]["resolved"])
    new_value = not current_value

    (
        supabase
        .table("community_messages")
        .update(
            {
                "resolved": new_value
            }
        )
        .eq("id", message_id)
        .execute()
    )

    return {
        "success": True,
        "resolved": new_value
    }


# =========================================================
# EMERGENCY  (broadcasts contact list into the shared chat)
# =========================================================

@app.post("/api/community/emergency")
def emergency(
    data: EmergencyCreate
):

    check_supabase()

    client_id = data.client_id.strip()
    name = data.name.strip() or "Guest"

    contact_lines = "\n".join(
        f"📞 {c['name']}: {c['phone']}"
        for c in EMERGENCY_CONTACTS
    )

    broadcast_text = (
        f"🚨 Emergency contacts requested by {name}\n\n"
        f"{contact_lines}"
    )

    # Make sure user exists
    (
        supabase
        .table("community_users")
        .upsert(
            {
                "client_id": client_id,
                "name": name
            },
            on_conflict="client_id"
        )
        .execute()
    )

    # Insert as a real chat message so everyone sees it
    result = (
        supabase
        .table("community_messages")
        .insert(
            {
                "client_id": client_id,
                "author_name": "WaterSafe Alerts",
                "message": broadcast_text,
                "image_data": None,
                "message_type": "emergency",
                "pinned": False,
                "reported": False,
                "resolved": False
            }
        )
        .execute()
    )

    return {
        "success": True,
        "type": "emergency",
        "message": result.data[0] if result.data else None,
        "contacts": EMERGENCY_CONTACTS
    }


# =========================================================
# CONFIG
# =========================================================

@app.get("/api/community/config")
def config():

    return {
        "reactions": REACTIONS,
        "emergency_contacts": EMERGENCY_CONTACTS,
        "supabase_configured": supabase is not None
    }


# =========================================================
# RUN LOCALLY
# =========================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )