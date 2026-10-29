"""
main.py — High-Performance API Server powered by FastAPI & LangChain
Features:
  - Cryptographically secure Admin Token Authentication (HMAC-SHA256)
  - Rate limiting on AI review endpoints against bot spam
  - Security headers & CORS middleware
  - Asynchronous background tasks for LangChain reviews generation
  - OpenAPI / Swagger docs at /docs
"""
import os
import json
import re
import time
import hmac
import hashlib
import secrets
import traceback
from collections import defaultdict
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, parse_qs, unquote_plus
import httpx

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse
from pydantic import BaseModel, Field

import database as db
import ai_service as ai

load_dotenv()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin423").strip()
SECRET_KEY = os.getenv("SECRET_KEY", "secret-super-key-change-me").strip()
FRONTEND_URL = os.getenv("FRONTEND_URL", "").strip().rstrip("/")

app = FastAPI(
    title="Google NFC Review System API",
    description="High-performance modern backend powered by FastAPI & LangChain with Admin Authentication & Rate Limiting.",
    version="2.2.0",
)

# ── CORS & Security Headers Middleware ────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# ── Error Logging Helper & Global Exception Handler ──────────

def record_error(endpoint: str, error_type: str, message: str, tb: str = ""):
    """Safely log error to database for Admin Notification."""
    try:
        db.log_error(endpoint=endpoint, error_type=error_type, message=message, traceback_str=tb)
    except Exception as e:
        print(f"[ErrorLogging] Failed to log error: {e}")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb_str = traceback.format_exc()
    err_type = exc.__class__.__name__
    err_msg = str(exc)
    endpoint = request.url.path
    print(f"[UNHANDLED EXCEPTION] {endpoint}: {err_type} - {err_msg}")
    record_error(endpoint=endpoint, error_type=err_type, message=err_msg, tb=tb_str)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "message": err_msg, "type": err_type}
    )

# Initialize DB on startup
db.init_db()

# Bearer token security scheme
security_scheme = HTTPBearer(auto_error=False)


# ── Cryptographic Token Authentication ─────────────────────────

def create_admin_token(secret: str, hours: int = 72) -> str:
    """Generates an HMAC-SHA256 signed tamper-proof token with expiration."""
    expires_at = int(time.time()) + (hours * 3600)
    payload = f"admin:{expires_at}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"

def verify_admin_token(token: str, secret: str) -> bool:
    """Constant-time token validation against tampering and expiration."""
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return False
        role, expires_at_str, sig = parts
        if role != "admin":
            return False
        expires_at = int(expires_at_str)
        if time.time() > expires_at:
            return False
        payload = f"{role}:{expires_at_str}"
        expected_sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return secrets.compare_digest(sig, expected_sig)
    except Exception:
        return False

def get_current_admin(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    """FastAPI Dependency: verifies caller has valid admin bearer token."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_admin_token(credentials.credentials, SECRET_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin session. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True


# ── IP Rate Limiter (Protects AI Generation Endpoints) ─────────

_rate_limits = defaultdict(list)

def enforce_rate_limit(ip: str, max_requests: int = 5, window_seconds: int = 300):
    """Allows max 5 AI review generations per IP in 5 minutes."""
    now = time.time()
    timestamps = [t for t in _rate_limits[ip] if now - t < window_seconds]
    if len(timestamps) >= max_requests:
        _rate_limits[ip] = timestamps
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many review generation requests. Please wait 5 minutes before generating another."
        )
    timestamps.append(now)
    _rate_limits[ip] = timestamps


# ── Pydantic Request Models ───────────────────────────────────

class AdminLoginRequest(BaseModel):
    password: str

class SmartDetectRequest(BaseModel):
    url: Optional[str] = ""
    shop_name: Optional[str] = ""

class CreateCardRequest(BaseModel):
    google_review_url: Optional[str] = ""
    place_id: Optional[str] = ""
    shop_name: Optional[str] = "My Shop"
    card_id: Optional[str] = ""
    shop_type: Optional[str] = "Other"
    description: Optional[str] = ""
    keywords: Optional[List[str]] = Field(default_factory=list)
    ai_json: Optional[Any] = None

class UpdateCardRequest(BaseModel):
    shop_name: str
    shop_type: str
    description: Optional[str] = ""
    keywords: Optional[List[str]] = Field(default_factory=list)

class ToggleStatusRequest(BaseModel):
    is_active: Optional[bool] = None

class UseReviewRequest(BaseModel):
    card_id: Optional[str] = None

class CustomReviewRequest(BaseModel):
    user_input: Optional[str] = ""


# ── Link Parsing Helpers ─────────────────────────────────────

def build_review_url(place_id: str) -> str:
    return f"https://search.google.com/local/writereview?placeid={place_id}"

def parse_google_url(url: str) -> dict:
    url = (url or "").strip()
    if not url:
        return {"place_id": None, "review_url": None, "name": None, "expanded_url": url}

    expanded_url = url
    name = None
    place_id = None

    if "goo.gl" in url or "g.co" in url or "maps.app" in url:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            with httpx.Client(follow_redirects=True, timeout=8.0, headers=headers) as client:
                r = client.get(url)
                expanded_url = str(r.url)
        except Exception as e:
            print(f"[LinkResolver] Error following redirect: {e}")

    if "placeid=" in expanded_url:
        try:
            parsed = urlparse(expanded_url)
            params = parse_qs(parsed.query)
            pid = params.get("placeid", [None])[0]
            if pid:
                place_id = pid
        except Exception:
            pass

    if not place_id:
        m_chij = re.search(r'!1s(ChIJ[\w-]+)', expanded_url)
        if m_chij:
            place_id = m_chij.group(1)

    m_name = re.search(r'/maps/place/([^/@?]+)', expanded_url)
    if m_name:
        raw_name = m_name.group(1)
        name = unquote_plus(raw_name).strip()
        name = re.sub(r'[\?#].*$', '', name).strip()
        if name.lower() in ["", "google maps", "maps"]:
            name = None

    review_url = build_review_url(place_id) if place_id else expanded_url
    return {
        "place_id": place_id,
        "review_url": review_url,
        "name": name,
        "expanded_url": expanded_url
    }

def extract_place_id(url: str) -> Optional[str]:
    return parse_google_url(url).get("place_id")


# ── Background Review Tasks (LangChain) ──────────────────────

def _bg_pre_generate_reviews(shop: dict):
    try:
        print(f"[LangChain-BG] Pre-generating 10 natural reviews for card: {shop['card_id']}")
        reviews = ai.generate_natural_reviews_batch(
            shop_name=shop["shop_name"],
            shop_type=shop.get("shop_type", "Store"),
            count=10
        )
        if reviews:
            db.save_reviews(shop["id"], reviews)
            print(f"[LangChain-BG] Saved {len(reviews)} natural reviews for {shop['card_id']}.")
    except Exception as e:
        tb_str = traceback.format_exc()
        record_error(
            endpoint=f"Background: /api/cards/{shop.get('card_id')}/generate",
            error_type=e.__class__.__name__,
            message=f"Failed to generate reviews for '{shop.get('shop_name')}': {str(e)}",
            tb=tb_str
        )
        print(f"[LangChain-BG Error] {e}")

def _bg_replenish_reviews(shop: dict):
    try:
        print(f"[LangChain-Replenish] Generating 10 new natural reviews for {shop['card_id']}...")
        new_reviews = ai.generate_natural_reviews_batch(
            shop_name=shop["shop_name"],
            shop_type=shop.get("shop_type", "Store"),
            count=10
        )
        if new_reviews:
            db.append_reviews(shop["id"], new_reviews)
            print(f"[LangChain-Replenish] Appended {len(new_reviews)} fresh reviews for {shop['card_id']}.")
    except Exception as e:
        tb_str = traceback.format_exc()
        record_error(
            endpoint=f"Background: /api/cards/{shop.get('card_id')}/replenish",
            error_type=e.__class__.__name__,
            message=f"Failed to replenish reviews for '{shop.get('shop_name')}': {str(e)}",
            tb=tb_str
        )
        print(f"[LangChain-Replenish Error] {e}")


# ── Authentication Endpoints ─────────────────────────────────

@app.post("/api/admin/login")
def admin_login(req: AdminLoginRequest):
    """Authenticates admin and returns a signed bearer token."""
    input_pass = req.password.strip()
    # Constant-time comparison against timing attacks
    if not secrets.compare_digest(input_pass, ADMIN_PASSWORD):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin password."
        )
    token = create_admin_token(SECRET_KEY, hours=72)
    return {"success": True, "token": token, "expires_in": 72 * 3600}

@app.get("/api/admin/verify")
def verify_admin_session(admin_auth: bool = Depends(get_current_admin)):
    """Verifies if the current bearer token is active."""
    return {"valid": True, "role": "admin"}


# ── Admin Protected Endpoints ────────────────────────────────

@app.get("/", include_in_schema=False)
def index_page():
    """Redirects to interactive Swagger OpenAPI documentation."""
    return RedirectResponse(url="/docs")

@app.get("/api/cards")
def list_cards(admin_auth: bool = Depends(get_current_admin)):
    """Lists all store NFC cards with scan metrics (Admin Only)."""
    return db.get_all_shops()

@app.post("/api/cards", status_code=status.HTTP_201_CREATED)
def create_card(req: CreateCardRequest, bg_tasks: BackgroundTasks, admin_auth: bool = Depends(get_current_admin)):
    """Creates a new NFC card (Admin Only)."""
    data = req.model_dump()
    review_url = data.get("google_review_url", "").strip()
    place_id = extract_place_id(review_url) or data.get("place_id", "").strip()

    if not place_id:
        raise HTTPException(
            status_code=400,
            detail="Could not detect Place ID from Google Review URL."
        )

    # Parse AI JSON if passed
    ai_json_raw = data.get("ai_json")
    if ai_json_raw:
        try:
            if isinstance(ai_json_raw, str):
                cleaned = re.sub(r"```(?:json)?", "", ai_json_raw).strip().rstrip("`").strip()
                m = re.search(r'\{.*\}', cleaned, re.DOTALL)
                parsed = json.loads(m.group()) if m else {}
            else:
                parsed = ai_json_raw

            for k in ["shop_name", "shop_type", "card_id", "description", "keywords"]:
                if parsed.get(k) and not data.get(k):
                    data[k] = parsed[k]
        except Exception as e:
            print(f"[create_card] Error parsing ai_json: {e}")

    shop_name = data.get("shop_name", "").strip() or "My Shop"

    card_id = data.get("card_id", "").strip()
    if not card_id:
        slug = re.sub(r'[^a-zA-Z0-9_-]+', '-', shop_name).strip('-')
        card_id = slug or f"shop-{int(os.urandom(2).hex(), 16)}"
    else:
        card_id = re.sub(r'[^a-zA-Z0-9_-]+', '-', card_id).strip('-')

    shop_type = data.get("shop_type", "").strip() or "Other"
    keywords = data.get("keywords") or ["excellent service", "friendly staff", "highly recommended"]
    description = data.get("description", "").strip() or f"{shop_name} offers quality service and customer satisfaction."

    ok, msg = db.create_shop(
        card_id=card_id,
        place_id=place_id,
        shop_name=shop_name,
        shop_type=shop_type,
        description=description,
        keywords=keywords,
        google_review_url=build_review_url(place_id),
    )
    if not ok:
        raise HTTPException(status_code=409, detail=msg)

    shop = db.get_shop_by_card_id(card_id)
    if shop:
        bg_tasks.add_task(_bg_pre_generate_reviews, shop)

    return {"message": msg, "card_id": card_id}

@app.put("/api/cards/{card_id}")
def update_card(card_id: str, req: UpdateCardRequest, bg_tasks: BackgroundTasks, admin_auth: bool = Depends(get_current_admin)):
    """Updates store profile (Admin Only)."""
    data = req.model_dump()
    db.update_shop(
        card_id=card_id,
        shop_name=data["shop_name"],
        shop_type=data["shop_type"],
        description=data.get("description", ""),
        keywords=data.get("keywords", []),
    )
    shop = db.get_shop_by_card_id(card_id)
    if shop:
        bg_tasks.add_task(_bg_pre_generate_reviews, shop)
    return {"message": "Updated"}

@app.delete("/api/cards/{card_id}")
def delete_card(card_id: str, admin_auth: bool = Depends(get_current_admin)):
    """Deletes store card (Admin Only)."""
    db.delete_shop(card_id)
    return {"message": "Deleted"}

@app.post("/api/cards/{card_id}/toggle-status")
def toggle_card_status(card_id: str, req: Optional[ToggleStatusRequest] = None, admin_auth: bool = Depends(get_current_admin)):
    """Toggles card between Live and Paused (Admin Only)."""
    is_active = req.is_active if req else None
    new_status = db.toggle_shop_status(card_id, is_active)
    if new_status is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"success": True, "card_id": card_id, "is_active": new_status}

@app.post("/api/cards/{card_id}/regenerate")
def regenerate_reviews(card_id: str, bg_tasks: BackgroundTasks, admin_auth: bool = Depends(get_current_admin)):
    """Forces LangChain regeneration of reviews (Admin Only)."""
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Card not found")
    bg_tasks.add_task(_bg_pre_generate_reviews, shop)
    return {"message": "Regeneration started in background via LangChain"}

@app.post("/api/smart-detect")
def smart_detect(req: SmartDetectRequest, admin_auth: bool = Depends(get_current_admin)):
    """Enriches store profile using LangChain (Admin Only)."""
    url = (req.url or "").strip()
    shop_name = (req.shop_name or "").strip()

    parsed = {"place_id": None, "review_url": None, "name": None}
    if url:
        parsed = parse_google_url(url)
        if not shop_name and parsed.get("name"):
            shop_name = parsed["name"]

    enrichment = {}
    if shop_name:
        enrichment = ai.enrich_shop(shop_name)

    return {
        "success": bool(parsed.get("place_id") or shop_name),
        "place_id": parsed.get("place_id"),
        "review_url": parsed.get("review_url"),
        "shop_name": shop_name or parsed.get("name") or "",
        "shop_type": enrichment.get("shop_type", "Other"),
        "keywords": enrichment.get("keywords", []),
        "description": enrichment.get("description", ""),
        "suggested_card_id": enrichment.get("card_id", ""),
    }

@app.post("/api/resolve-link")
def resolve_link(req: SmartDetectRequest, admin_auth: bool = Depends(get_current_admin)):
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="No URL provided")
    parsed = parse_google_url(url)
    return {
        "place_id": parsed["place_id"],
        "review_url": parsed["review_url"],
        "name": parsed["name"],
    }


# ── Admin Error Logging & Health Monitoring ──────────────────

@app.get("/api/admin/errors")
def get_system_errors(limit: int = 50, admin_auth: bool = Depends(get_current_admin)):
    """Retrieve system error logs and unread count (Admin Only)."""
    return db.get_errors(limit=limit)

@app.post("/api/admin/errors/mark-read")
def mark_system_errors_read(admin_auth: bool = Depends(get_current_admin)):
    """Mark all system error logs as read (Admin Only)."""
    success = db.mark_all_errors_read()
    return {"success": success}

@app.delete("/api/admin/errors")
def clear_system_errors(admin_auth: bool = Depends(get_current_admin)):
    """Clear all system error logs (Admin Only)."""
    success = db.clear_all_errors()
    return {"success": success}



# ── Public Customer Endpoints (NFC Card Taps) ────────────────

@app.get("/r/{card_id}")
def customer_page(card_id: str, request: Request):
    """Direct NFC tap handler: redirects to React frontend or renders standalone page."""
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Card not found")

    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown").split(",")[0].strip()
    user_agent = request.headers.get("User-Agent", "")
    db.record_scan(shop["id"], ip=client_ip, user_agent=user_agent)

    # If Vercel React frontend is configured, redirect directly to React Review page
    if FRONTEND_URL:
        return RedirectResponse(url=f"{FRONTEND_URL}/r/{card_id}")

    # Check active status
    if not shop.get("is_active", True):
        inactive_path = os.path.join("templates", "inactive.html")
        if os.path.exists(inactive_path):
            with open(inactive_path, "r", encoding="utf-8") as f:
                html = f.read().replace("{{ shop.shop_name }}", shop["shop_name"])
                return HTMLResponse(content=html)

    # Lightweight direct HTML rendering without needing Jinja2
    template_path = os.path.join("templates", "customer.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace("{{ shop.card_id | tojson }}", json.dumps(shop["card_id"]))
        html = html.replace("{{ shop.google_review_url | tojson }}", json.dumps(shop["google_review_url"]))
        html = html.replace("{{ shop.shop_name }}", shop["shop_name"])
        return HTMLResponse(content=html)

    return RedirectResponse(url=f"/api/reviews/{card_id}")

@app.get("/api/shop/{card_id}")
def get_shop_info(card_id: str):
    """Public store details for NFC customer review portal."""
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Card not found")
    return shop

@app.get("/api/card-status/{card_id}")
def card_status(card_id: str):
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Card not found")
    ready = db.has_reviews(shop["id"])
    return {"ready": ready, "card_id": card_id, "shop_name": shop["shop_name"]}

@app.get("/api/reviews/{card_id}")
@app.get("/api/fallback/{card_id}")
def get_reviews(card_id: str):
    """Public random 5 unused reviews for customer card swipe."""
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Card not found")
    reviews = db.get_random_unused_reviews(shop["id"], limit=5)
    return {
        "source": "db",
        "reviews": reviews,
        "shop": {
            "name": shop["shop_name"],
            "type": shop["shop_type"],
            "google_review_url": shop["google_review_url"],
            "is_active": shop.get("is_active", True)
        }
    }

@app.post("/api/reviews/{review_id}/use")
def mark_review_used(review_id: int, req: UseReviewRequest, bg_tasks: BackgroundTasks):
    """Marks review as used when clicked to post on Google."""
    shop = db.get_shop_by_card_id(req.card_id) if req.card_id else None
    shop_id = shop["id"] if shop else None

    result = db.mark_review_used(review_id, shop_id=shop_id)
    if result.get("should_replenish"):
        target_shop = shop or (db.get_shop_by_id(result["shop_id"]) if result.get("shop_id") else None)
        if target_shop:
            bg_tasks.add_task(_bg_replenish_reviews, target_shop)

    return {"success": True, **result}

@app.post("/api/custom-review/{card_id}")
def generate_custom_review(card_id: str, req: CustomReviewRequest, request: Request):
    """Public AI custom review generation with rate limit protection."""
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown").split(",")[0].strip()
    try:
        enforce_rate_limit(client_ip, max_requests=5, window_seconds=300)
    except HTTPException as he:
        record_error(
            endpoint=f"/api/custom-review/{card_id}",
            error_type="RateLimitExceeded",
            message=f"IP {client_ip} exceeded AI rate limit (5 attempts / 5 mins)."
        )
        raise he

    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Card not found")

    try:
        review_text = ai.generate_custom_review(
            shop_name=shop["shop_name"],
            shop_type=shop.get("shop_type", "Store"),
            user_input=req.user_input or ""
        )
        return {
            "review": review_text,
            "shop_name": shop["shop_name"],
            "google_review_url": shop["google_review_url"]
        }
    except Exception as e:
        tb_str = traceback.format_exc()
        record_error(
            endpoint=f"/api/custom-review/{card_id}",
            error_type=e.__class__.__name__,
            message=f"AI custom review generation failed for '{shop['shop_name']}': {str(e)}",
            tb=tb_str
        )
        raise HTTPException(status_code=500, detail="AI review generation temporarily unavailable. Please try again.")

@app.get("/api/stream/{card_id}")
def stream_reviews(card_id: str, aspect: str = "general"):
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Card not found")

    def event_generator():
        yield f"data: {json.dumps({'type': 'start', 'aspect': aspect})}\n\n"
        yield from ai.stream_reviews_for_aspect(
            shop_name=shop["shop_name"],
            shop_type=shop["shop_type"],
            description=shop.get("description", ""),
            keywords=shop.get("keywords", []),
            aspect=aspect,
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


# ── Run Server (Local) ────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("FastAPI & LangChain Server running at http://localhost:5000")
    print("Interactive Swagger Docs at http://localhost:5000/docs")
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
