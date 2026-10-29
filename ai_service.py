import os
import json
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))

# Best fast & reliable model on Groq
MODEL = "qwen/qwen3.8-27b"

ASPECTS = ["general", "service", "ambience", "quality", "value"]

ASPECT_LABELS = {
    "general":  "Overall Experience",
    "service":  "Service & Staff",
    "ambience": "Ambience & Atmosphere",
    "quality":  "Quality of Work",
    "value":    "Value for Money",
}


def enrich_shop(shop_name: str) -> dict:
    """
    Given a shop name, uses AI to infer shop type, positive keywords,
    a one-line description, and a clean URL card_id in < 1 second.
    """
    if not shop_name or not shop_name.strip():
        return {}
    
    prompt = f"""You are a business profile assistant. Given a business name, infer its details for an NFC review card.
Business Name: "{shop_name.strip()}"

Respond with ONLY a valid JSON object (no markdown, no other text):
{{
  "shop_type": "<one of: Restaurant, Cafe, Hair Salon, Tattoo Studio, Spa & Wellness, Gym & Fitness, Clothing Store, Bakery, Medical Clinic, Dental Clinic, Hotel, Photography Studio, Electronics Shop, Other>",
  "keywords": ["keyword 1", "keyword 2", "keyword 3", "keyword 4"],
  "description": "<one crisp sentence describing the business and quality of service>",
  "card_id": "<clean lowercase slug with hyphens, e.g. dream-art-tattoo>"
}}"""

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=250,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`")
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"[AI] Error enriching shop '{shop_name}': {e}")
    return {}


def build_prompt(shop_name: str, shop_type: str, description: str, keywords: list, aspect: str) -> str:
    kw_str = ", ".join(keywords) if keywords else "great experience, professional staff"
    aspect_label = ASPECT_LABELS.get(aspect, "overall experience")

    return f"""You are a real satisfied customer writing genuine Google reviews.

Shop: {shop_name}
Type: {shop_type}
About: {description}
Keywords: {kw_str}
Focus: {aspect_label}

Write exactly 4 short, genuine-sounding Google reviews (2-4 sentences each) about "{aspect_label}".

Rules:
- Sound like REAL people (vary tone: casual, enthusiastic, professional, simple)
- Mention specific positive details naturally  
- NEVER sound templated, corporate, or fake
- Include 1-2 relevant emojis naturally
- English only

Respond ONLY with a valid JSON array, no markdown, no extra text:
[
  {{"content": "review text", "aspect": "{aspect}"}},
  {{"content": "review text", "aspect": "{aspect}"}},
  {{"content": "review text", "aspect": "{aspect}"}},
  {{"content": "review text", "aspect": "{aspect}"}}
]"""


def generate_reviews_for_aspect(shop_name, shop_type, description, keywords, aspect):
    """Blocking call — generate 4 reviews for one aspect. Returns list of dicts."""
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": build_prompt(shop_name, shop_type, description, keywords, aspect)}],
            temperature=0.85,
            max_tokens=800,
        )
        text = completion.choices[0].message.content.strip()

        # Strip markdown code fences if present
        text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()

        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"[AI] Error on aspect '{aspect}': {e}")
    return []


def generate_natural_reviews_batch(shop_name: str, shop_type: str, count: int = 10) -> list:
    """
    Generates authentic, casual, human 5-star Google reviews.
    Varies length (1-sentence, 2-sentence, 3-sentence).
    Focuses on natural experiences: owner/staff behavior, good work, clean place, fair price.
    """
    prompt = f"""You are {count} different real customers who visited "{shop_name}" ({shop_type}).
Write exactly {count} authentic, natural, human 5-star Google reviews in English.

Crucial Realism Rules:
- Mix lengths: some short (1 quick sentence, e.g. "Great work and the owner's behaviour is very polite!"), some medium (2 sentences), some 3 sentences.
- Keep them simple, casual and natural — NOT overly specific product catalogs.
- Focus on real-life general experiences: polite & helpful behaviour of the owner and staff, great quality of work, clean and welcoming place, fair pricing, fast service.
- Sound like 10 DIFFERENT ordinary people who had a genuinely good experience. Avoid robotic AI phrasing or marketing hype.
- Occasionally include 1 natural emoji (e.g. ⭐, 👍, ✨).

Respond ONLY with a valid JSON array of {count} strings, no markdown formatting:
[
  "Review 1...",
  "Review 2..."
]"""

    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.85,
            max_tokens=1200,
        )
        raw = completion.choices[0].message.content.strip()
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            items = json.loads(match.group())
            if isinstance(items, list) and len(items) >= 5:
                # Return list of clean strings
                return [str(x).strip() for x in items if str(x).strip()]
    except Exception as e:
        print(f"[AI] Error generating natural reviews batch: {e}")

    # Fallback realistic natural reviews if AI call is interrupted
    return [
        f"Really good work! The behaviour of the owner is very polite and humble. 👍",
        f"Visited {shop_name} today. Very clean place, quick service, and reasonable rates. Will definitely come back!",
        f"Top notch service! Loved how professional and friendly everyone was. Highly recommended. ⭐⭐⭐⭐⭐",
        f"Great experience overall. Owner is very cooperative and listens carefully to what you need.",
        f"Very satisfied with the quality of work. Fair pricing and friendly environment.",
        f"Excellent work and great staff behavior. One of the best in the area! ✨",
        f"Had a smooth and hassle-free experience here. 100% recommended!",
        f"Good people, great service! The work was done on time without any delay.",
        f"Honest pricing and very helpful attitude. Keep up the good work! 👍",
        f"Super happy with the outcome! Friendly behaviour and top-quality work."
    ]


def generate_all_reviews(shop_name, shop_type, description, keywords):
    """Generate reviews for ALL aspects — used during admin card setup (background)."""
    return generate_natural_reviews_batch(shop_name, shop_type, count=10)


def stream_reviews_for_aspect(shop_name, shop_type, description, keywords, aspect):
    """
    SSE generator — streams Groq tokens, then sends parsed reviews on completion.
    Groq is so fast (~200-500ms) the 2-sec fallback almost never triggers.
    Yields SSE-formatted strings.
    """
    try:
        stream = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": build_prompt(shop_name, shop_type, description, keywords, aspect)}],
            temperature=0.85,
            max_tokens=800,
            stream=True,
        )

        full_text = ""
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                full_text += token
                yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"

        # Clean and parse final JSON
        clean = re.sub(r"```(?:json)?", "", full_text).strip().rstrip("`").strip()
        match = re.search(r'\[.*\]', clean, re.DOTALL)
        if match:
            reviews = json.loads(match.group())
            yield f"data: {json.dumps({'type': 'done', 'reviews': reviews})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Could not parse JSON'})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


def generate_custom_review(shop_name: str, shop_type: str, user_input: str) -> str:
    """
    Takes a customer's raw/rough input (in English, Bengali, or Banglish)
    and expands it into an authentic, natural, 5-star Google review.
    """
    if not user_input or not user_input.strip():
        return f"Had an amazing experience at {shop_name}! Top quality service and wonderful staff. Highly recommended! ⭐⭐⭐⭐⭐"

    prompt = f"""You are helping a customer write their genuine 5-star Google Review.
Business: {shop_name} ({shop_type})
Customer's words / experience: "{user_input.strip()}"

Task:
Write a short, natural, glowing 5-star Google review (2-3 sentences) in English based on what the customer experienced.
Rules:
- Keep the customer's specific point (e.g. what they purchased or experienced)
- Polish into natural, authentic English that sounds like a real person
- Add 1-2 natural emojis (e.g. ⭐, ✨, 👍)
- Respond with ONLY the review text itself, no quotes, no conversational filler, no markdown."""

    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=250,
        )
        review = completion.choices[0].message.content.strip().strip('"').strip("'")
        return review
    except Exception as e:
        print(f"[AI] Error generating custom review: {e}")
        return f"Had a great experience at {shop_name}! {user_input.strip()}. Highly recommended!"

