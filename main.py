"""
main.py — High-Performance API Server powered by FastAPI & LangChain
Provides:
  - Automatic OpenAPI / Swagger docs at /docs & /redoc
  - Asynchronous background tasks for review generation
  - Full CORS support for Vercel and third-party frontends
  - Dual support: Standalone JSON API + Direct Template Rendering
"""
import os
import json
import re
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, parse_qs, unquote_plus
import requests as http_req

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

import database as db
import ai_service as ai

load_dotenv()

app = FastAPI(
    title="Google NFC Review System API",
    description="High-performance backend powered by FastAPI & LangChain for NFC smart review cards.",
    version="2.0.0",
)

# ── CORS Middleware (Enables seamless Vercel & local connections) ─
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB on startup
db.init_db()

# Setup Templates for fallback/direct rendering
templates = Jinja2Templates(directory="templates")


# ── Pydantic Request Models ───────────────────────────────────

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
            r = http_req.get(url, allow_redirects=True, timeout=8, headers=headers)
            expanded_url = r.url
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
    print(f"[LangChain-BG] Pre-generating 10 natural reviews for card: {shop['card_id']}")
    reviews = ai.generate_natural_reviews_batch(
        shop_name=shop["shop_name"],
        shop_type=shop.get("shop_type", "Store"),
        count=10
    )
    if reviews:
        db.save_reviews(shop["id"], reviews)
        print(f"[LangChain-BG] Saved {len(reviews)} natural reviews for {shop['card_id']}.")

def _bg_replenish_reviews(shop: dict):
    print(f"[LangChain-Replenish] Generating 10 new natural reviews for {shop['card_id']}...")
    new_reviews = ai.generate_natural_reviews_batch(
        shop_name=shop["shop_name"],
        shop_type=shop.get("shop_type", "Store"),
        count=10
    )
    if new_reviews:
        db.append_reviews(shop["id"], new_reviews)
        print(f"[LangChain-Replenish] Appended {len(new_reviews)} fresh reviews for {shop['card_id']}.")


# ── Admin & Dashboard Endpoints ──────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    """Directly serves Admin UI template if accessed directly on Render."""
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/api/cards")
def list_cards():
    """Lists all store NFC cards with scan metrics."""
    return db.get_all_shops()

@app.post("/api/cards", status_code=status.HTTP_201_CREATED)
def create_card(req: CreateCardRequest, bg_tasks: BackgroundTasks):
    """Creates a new NFC card and triggers LangChain pre-generation in background."""
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
def update_card(card_id: str, req: UpdateCardRequest, bg_tasks: BackgroundTasks):
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
def delete_card(card_id: str):
    db.delete_shop(card_id)
    return {"message": "Deleted"}

@app.post("/api/cards/{card_id}/toggle-status")
def toggle_card_status(card_id: str, req: Optional[ToggleStatusRequest] = None):
    is_active = req.is_active if req else None
    new_status = db.toggle_shop_status(card_id, is_active)
    if new_status is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"success": True, "card_id": card_id, "is_active": new_status}

@app.post("/api/cards/{card_id}/regenerate")
def regenerate_reviews(card_id: str, bg_tasks: BackgroundTasks):
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Card not found")
    bg_tasks.add_task(_bg_pre_generate_reviews, shop)
    return {"message": "Regeneration started in background via LangChain"}


# ── AI Smart Detect ──────────────────────────────────────────

@app.post("/api/smart-detect")
def smart_detect(req: SmartDetectRequest):
    """Resolves link and uses LangChain chain to enrich profile."""
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
def resolve_link(req: SmartDetectRequest):
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="No URL provided")
    parsed = parse_google_url(url)
    return {
        "place_id": parsed["place_id"],
        "review_url": parsed["review_url"],
        "name": parsed["name"],
    }


# ── Customer NFC Review Experience Endpoints ────────────────

@app.get("/r/{card_id}", response_class=HTMLResponse)
def customer_page(card_id: str, request: Request):
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Card not found")

    if not shop.get("is_active", True):
        return templates.TemplateResponse("inactive.html", {"request": request, "shop": shop})

    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
    user_agent = request.headers.get("User-Agent", "")
    db.record_scan(shop["id"], ip=client_ip, user_agent=user_agent)

    if not db.has_reviews(shop["id"]):
        return templates.TemplateResponse("processing.html", {"request": request, "shop": shop})

    return templates.TemplateResponse("customer.html", {"request": request, "shop": shop})

@app.get("/api/shop/{card_id}")
def get_shop_info(card_id: str):
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
        }
    }

@app.post("/api/reviews/{review_id}/use")
def mark_review_used(review_id: int, req: UseReviewRequest, bg_tasks: BackgroundTasks):
    shop = db.get_shop_by_card_id(req.card_id) if req.card_id else None
    shop_id = shop["id"] if shop else None

    result = db.mark_review_used(review_id, shop_id=shop_id)
    if result.get("should_replenish"):
        target_shop = shop or (db.get_shop_by_id(result["shop_id"]) if result.get("shop_id") else None)
        if target_shop:
            bg_tasks.add_task(_bg_replenish_reviews, target_shop)

    return {"success": True, **result}

@app.post("/api/custom-review/{card_id}")
def generate_custom_review(card_id: str, req: CustomReviewRequest):
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Card not found")

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
