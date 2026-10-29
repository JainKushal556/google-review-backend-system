"""
scraper.py — Auto-detect shop info from Google Maps
Uses requests + BeautifulSoup to fetch basic shop data
without requiring a Google API key.
"""
import re
import json
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Map Google place types → readable business type
CATEGORY_MAP = {
    "restaurant": "Restaurant",
    "food": "Restaurant",
    "cafe": "Cafe",
    "bar": "Bar & Lounge",
    "bakery": "Bakery",
    "beauty_salon": "Beauty Salon",
    "hair_care": "Hair Salon",
    "spa": "Spa & Wellness",
    "gym": "Gym & Fitness",
    "clothing_store": "Clothing Store",
    "shoe_store": "Shoe Store",
    "electronics_store": "Electronics Shop",
    "jewelry_store": "Jewelry Store",
    "pharmacy": "Pharmacy",
    "hospital": "Medical Clinic",
    "doctor": "Medical Clinic",
    "dentist": "Dental Clinic",
    "lodging": "Hotel",
    "hotel": "Hotel",
    "car_repair": "Auto Service",
    "tattoo_parlor": "Tattoo Studio",
    "photographer": "Photography Studio",
    "florist": "Flower Shop",
    "pet_store": "Pet Store",
    "book_store": "Book Store",
    "supermarket": "Supermarket",
    "laundry": "Laundry Service",
    "travel_agency": "Travel Agency",
}


def auto_detect_shop(place_id: str) -> dict:
    """
    Try to fetch shop details from Google Maps using Place ID.
    Returns dict with: name, shop_type, description, keywords, success
    Falls back gracefully if scraping fails.
    """
    result = {
        "success": False,
        "name": "",
        "shop_type": "",
        "description": "",
        "keywords": [],
    }

    # ── Method 1: Google Maps place page ──
    try:
        url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
        r = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True)

        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")

            # Try og:title meta tag → usually has "Shop Name - Google Maps"
            og_title = soup.find("meta", {"property": "og:title"})
            if og_title and og_title.get("content"):
                raw = og_title["content"]
                # Strip "- Google Maps" suffix
                name = re.sub(r"\s*[-–]\s*Google Maps.*$", "", raw, flags=re.IGNORECASE).strip()
                if name and len(name) > 2:
                    result["name"] = name
                    result["success"] = True

            # Try page title as fallback
            if not result["name"]:
                title = soup.find("title")
                if title:
                    raw = title.get_text()
                    name = re.sub(r"\s*[-–]\s*Google Maps.*$", "", raw, flags=re.IGNORECASE).strip()
                    if name and len(name) > 2:
                        result["name"] = name
                        result["success"] = True

            # Try JSON-LD structured data for category
            for script in soup.find_all("script", {"type": "application/ld+json"}):
                try:
                    data = json.loads(script.string or "")
                    if isinstance(data, dict):
                        t = data.get("@type", "")
                        if not result["name"]:
                            n = data.get("name", "")
                            if n:
                                result["name"] = n
                                result["success"] = True
                        result["description"] = data.get("description", "")
                        # Map schema type to shop type
                        for key, val in CATEGORY_MAP.items():
                            if key.lower() in t.lower():
                                result["shop_type"] = val
                                break
                except Exception:
                    continue

    except Exception as e:
        print(f"[Scraper] Error fetching Google Maps page: {e}")

    # ── Method 2: Google Search snippet ──
    if not result["success"]:
        try:
            q = f"site:google.com/maps place_id:{place_id}"
            url = f"https://www.google.com/search?q={requests.utils.quote(q)}"
            r = requests.get(url, headers=HEADERS, timeout=6)
            soup = BeautifulSoup(r.text, "html.parser")
            h3 = soup.find("h3")
            if h3:
                result["name"] = h3.get_text().strip()
                result["success"] = True
        except Exception:
            pass

    return result
