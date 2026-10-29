import json
import os
import re
import threading
from urllib.parse import parse_qs, unquote_plus, urlparse

from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, render_template, request
from flask_cors import CORS
import requests as http_req

import ai_service as ai
import database as db

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
CORS(app)

# ── Init DB on startup ───────────────────────────────────────
db.init_db()


# ── Helpers ──────────────────────────────────────────────────

def parse_google_url(url: str) -> dict:
    """
    Extracts Place ID, full expanded URL, and Shop Name from any Google URL.
    Handles:
      - Short links: maps.app.goo.gl/xxx, g.co/maps/xxx
      - Maps places: google.com/maps/place/Name/@...
      - Review links: search.google.com/local/writereview?placeid=...
    """
    url = url.strip()
    if not url:
        return {"place_id": None, "review_url": None, "name": None, "expanded_url": url}

    expanded_url = url
    name = None
    place_id = None

    # Follow redirect for short links
    if "goo.gl" in url or "g.co" in url or "maps.app" in url:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            r = http_req.get(url, allow_redirects=True, timeout=8, headers=headers)
            expanded_url = r.url
        except Exception as e:
            print(f"[LinkResolver] Error following redirect: {e}")

    # Extract Place ID from placeid query param
    if "placeid=" in expanded_url:
        try:
            parsed = urlparse(expanded_url)
            params = parse_qs(parsed.query)
            pid = params.get("placeid", [None])[0]
            if pid:
                place_id = pid
        except Exception:
            pass

    # Extract Place ID from !1s (ChIJ...)
    if not place_id:
        m_chij = re.search(r'!1s(ChIJ[\w-]+)', expanded_url)
        if m_chij:
            place_id = m_chij.group(1)

    # Extract shop name from /maps/place/<Name>/
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


def extract_place_id(url: str) -> str | None:
    return parse_google_url(url).get("place_id")


def build_review_url(place_id: str) -> str:
    return f"https://search.google.com/local/writereview?placeid={place_id}"


# ── Admin Routes ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("admin.html")


@app.route("/api/cards", methods=["GET"])
def list_cards():
    shops = db.get_all_shops()
    return jsonify(shops)


@app.route("/api/resolve-link", methods=["POST"])
def resolve_link():
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    parsed = parse_google_url(url)
    return jsonify({
        "place_id": parsed["place_id"],
        "review_url": parsed["review_url"],
        "name": parsed["name"],
    })


@app.route("/api/smart-detect", methods=["POST"])
def smart_detect():
    """
    Single unified smart detection endpoint:
    Accepts: { url: "...", shop_name: "..." }
    1. Resolves Google link -> Place ID & Review URL
    2. If shop_name found in URL or provided by user -> AI enriches:
       - shop_type
       - keywords
       - description
       - card_id slug
    Returns everything needed to save the card with zero manual typing!
    """
    data = request.json or {}
    url = data.get("url", "").strip()
    shop_name = data.get("shop_name", "").strip()

    parsed = {"place_id": None, "review_url": None, "name": None}
    if url:
        parsed = parse_google_url(url)
        if not shop_name and parsed.get("name"):
            shop_name = parsed["name"]

    # AI auto-enrichment if we have shop_name
    enrichment = {}
    if shop_name:
        enrichment = ai.enrich_shop(shop_name)

    return jsonify({
        "success": bool(parsed.get("place_id") or shop_name),
        "place_id": parsed.get("place_id"),
        "review_url": parsed.get("review_url"),
        "shop_name": shop_name or parsed.get("name") or "",
        "shop_type": enrichment.get("shop_type", "Other"),
        "keywords": enrichment.get("keywords", []),
        "description": enrichment.get("description", ""),
        "suggested_card_id": enrichment.get("card_id", ""),
    })


@app.route("/api/auto-detect", methods=["POST"])
def auto_detect():
    """Legacy compatibility wrapper around smart-detect."""
    data = request.json or {}
    place_id = data.get("place_id", "").strip()
    if not place_id:
        return jsonify({"error": "No Place ID"}), 400
    data["url"] = build_review_url(place_id)
    return smart_detect()


@app.route("/api/cards", methods=["POST"])
def create_card():
    data = request.json or {}
    review_url = data.get("google_review_url", "").strip()
    place_id = extract_place_id(review_url) or data.get("place_id", "").strip()

    if not place_id:
        return jsonify({"error": "Google link থেকে Place ID পাওয়া যায়নি। দয়া করে সঠিক লিঙ্ক দাও।"}), 400

    # Parse AI JSON if provided as string or dict
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

    shop_name = data.get("shop_name", "").strip()
    if not shop_name:
        shop_name = "My Shop"

    # Auto-generate or sanitize card_id
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
        return jsonify({"error": msg}), 409

    # Pre-generate reviews in background thread (non-blocking)
    shop = db.get_shop_by_card_id(card_id)
    if shop:
        threading.Thread(
            target=_pre_generate_reviews,
            args=(shop,),
            daemon=True
        ).start()

    return jsonify({"message": msg, "card_id": card_id}), 201


@app.route("/api/cards/<card_id>", methods=["PUT"])
def update_card(card_id):
    data = request.json
    db.update_shop(
        card_id=card_id,
        shop_name=data["shop_name"],
        shop_type=data["shop_type"],
        description=data.get("description", ""),
        keywords=data.get("keywords", []),
    )
    # Re-generate reviews
    shop = db.get_shop_by_card_id(card_id)
    if shop:
        threading.Thread(target=_pre_generate_reviews, args=(shop,), daemon=True).start()
    return jsonify({"message": "Updated"})


@app.route("/api/cards/<card_id>/toggle-status", methods=["POST"])
def toggle_card_status(card_id):
    """Toggles card between Active and Service Off."""
    data = request.get_json(silent=True) or {}
    is_active = data.get("is_active")
    new_status = db.toggle_shop_status(card_id, is_active)
    if new_status is None:
        return jsonify({"error": "Card not found"}), 404
    return jsonify({"success": True, "card_id": card_id, "is_active": new_status})


@app.route("/api/cards/<card_id>", methods=["DELETE"])
def delete_card(card_id):
    db.delete_shop(card_id)
    return jsonify({"message": "Deleted"})


@app.route("/api/cards/<card_id>/regenerate", methods=["POST"])
def regenerate_reviews(card_id):
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        return jsonify({"error": "Card not found"}), 404
    threading.Thread(target=_pre_generate_reviews, args=(shop,), daemon=True).start()
    return jsonify({"message": "Regeneration started in background"})


def _pre_generate_reviews(shop):
    """Background task: generate initial 10 natural, casual reviews and store in DB."""
    print(f"[BG] Pre-generating 10 natural reviews for card: {shop['card_id']}")
    reviews = ai.generate_natural_reviews_batch(
        shop_name=shop["shop_name"],
        shop_type=shop.get("shop_type", "Store"),
        count=10
    )
    if reviews:
        db.save_reviews(shop["id"], reviews)
        print(f"[BG] Saved {len(reviews)} natural reviews for {shop['card_id']}. Card is now LIVE!")


def _replenish_reviews(shop):
    """Background task: when 10 reviews are used, generate & append 10 new natural reviews."""
    print(f"[BG-Replenish] Generating 10 new natural reviews for {shop['card_id']}...")
    new_reviews = ai.generate_natural_reviews_batch(
        shop_name=shop["shop_name"],
        shop_type=shop.get("shop_type", "Store"),
        count=10
    )
    if new_reviews:
        db.append_reviews(shop["id"], new_reviews)
        print(f"[BG-Replenish] Added {len(new_reviews)} fresh reviews for {shop['card_id']}")


# ── Customer Routes ───────────────────────────────────────────

@app.route("/r/<card_id>")
def customer_page(card_id):
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        abort(404)

    # Check if card service is turned off (inactive)
    if not shop.get("is_active", True):
        return render_template("inactive.html", shop=shop)

    # Record scan visit
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    user_agent = request.user_agent.string if request.user_agent else ""
    db.record_scan(shop["id"], ip=client_ip, user_agent=user_agent)

    # If reviews are still generating in background, show processing screen
    if not db.has_reviews(shop["id"]):
        return render_template("processing.html", shop=shop)

    return render_template("customer.html", shop=shop)


@app.route("/api/card-status/<card_id>")
def card_status(card_id):
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        return jsonify({"ready": False, "error": "Not found"}), 404

    ready = db.has_reviews(shop["id"])
    return jsonify({
        "ready": ready,
        "card_id": card_id,
        "shop_name": shop["shop_name"]
    })


@app.route("/api/shop/<card_id>")
def get_shop_info(card_id):
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        return jsonify({"error": "Not found"}), 404
    return jsonify(shop)


@app.route("/api/fallback/<card_id>")
@app.route("/api/reviews/<card_id>")
def get_fallback(card_id):
    """
    On NFC scan: returns random 5 unused reviews directly from DB.
    Zero AI latency — ultra fast scan-to-screen time!
    """
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        return jsonify({"error": "Not found"}), 404

    reviews = db.get_random_unused_reviews(shop["id"], limit=5)
    return jsonify({
        "source": "db",
        "reviews": reviews,
        "shop": {
            "name": shop["shop_name"],
            "type": shop["shop_type"],
            "google_review_url": shop["google_review_url"],
        }
    })


@app.route("/api/reviews/<int:review_id>/use", methods=["POST"])
def mark_review_as_used(review_id):
    """
    Called when a customer selects/posts a review to Google.
    Marks review as used in DB.
    When 10 reviews have been used, auto-purges them and triggers replenishment of 10 new reviews.
    """
    data = request.json or {}
    card_id = data.get("card_id")
    shop = db.get_shop_by_card_id(card_id) if card_id else None
    shop_id = shop["id"] if shop else None

    result = db.mark_review_used(review_id, shop_id=shop_id)

    if result.get("should_replenish"):
        target_shop = shop
        if not target_shop and result.get("shop_id"):
            target_shop = db.get_shop_by_id(result["shop_id"])

        if target_shop:
            threading.Thread(
                target=_replenish_reviews,
                args=(target_shop,),
                daemon=True
            ).start()

    return jsonify({"success": True, **result})


@app.route("/api/custom-review/<card_id>", methods=["POST"])
def generate_user_custom_review(card_id):
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        return jsonify({"error": "Shop not found"}), 404

    data = request.json or {}
    user_input = data.get("user_input", "").strip()

    review_text = ai.generate_custom_review(
        shop_name=shop["shop_name"],
        shop_type=shop.get("shop_type", "Store"),
        user_input=user_input
    )
    return jsonify({
        "review": review_text,
        "shop_name": shop["shop_name"],
        "google_review_url": shop["google_review_url"]
    })


@app.route("/api/stream/<card_id>")
def stream_reviews(card_id):
    """
    SSE endpoint — streams AI-generated reviews.
    Client starts a 2-sec timer; if this responds fast enough,
    AI reviews are shown. Otherwise fallback kicks in from /api/fallback.
    """
    shop = db.get_shop_by_card_id(card_id)
    if not shop:
        return jsonify({"error": "Not found"}), 404

    aspect = request.args.get("aspect", "general")

    def generate():
        yield f"data: {json.dumps({'type': 'start', 'aspect': aspect})}\n\n"
        yield from ai.stream_reviews_for_aspect(
            shop_name=shop["shop_name"],
            shop_type=shop["shop_type"],
            description=shop.get("description", ""),
            keywords=shop.get("keywords", []),
            aspect=aspect,
        )

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Connection": "keep-alive",
        }
    )


# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Google Review Card System running at http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
