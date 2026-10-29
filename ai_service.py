"""
ai_service.py — Modern AI Integration powered by LangChain and Groq
Handles:
  1. Shop profile enrichment via LangChain structured JSON chain.
  2. Authentic natural customer reviews batch generation via LangChain.
  3. Custom user review expansion into 5-star Google review.
  4. Aspect-based streaming via LangChain LLM stream.
"""
import os
import json
import re
from typing import List, Dict, Any
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODEL_NAME = "qwen/qwen3.8-27b"

# High-temperature LLM for creative human-sounding reviews
llm_creative = ChatGroq(
    model_name=MODEL_NAME,
    groq_api_key=GROQ_API_KEY,
    temperature=0.85,
    max_tokens=1200,
)

# Low-temperature LLM for deterministic profile extraction
llm_deterministic = ChatGroq(
    model_name=MODEL_NAME,
    groq_api_key=GROQ_API_KEY,
    temperature=0.2,
    max_tokens=300,
)

ASPECT_LABELS = {
    "general":  "Overall Experience",
    "service":  "Service & Staff",
    "ambience": "Ambience & Atmosphere",
    "quality":  "Quality of Work",
    "value":    "Value for Money",
}


# ── 1. Shop Profile Enrichment Chain ─────────────────────────

enrich_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert business profile assistant. Given a business name, infer its categorization and key details for an NFC review card. Respond ONLY with a valid JSON object."),
    ("human", """Business Name: "{shop_name}"

Return JSON matching this schema:
{{
  "shop_type": "<one of: Restaurant, Cafe, Hair Salon, Tattoo Studio, Spa & Wellness, Gym & Fitness, Clothing Store, Bakery, Medical Clinic, Dental Clinic, Hotel, Photography Studio, Electronics Shop, Other>",
  "keywords": ["keyword 1", "keyword 2", "keyword 3", "keyword 4"],
  "description": "<one crisp sentence describing the business and quality of service>",
  "card_id": "<clean lowercase slug with hyphens, e.g. dream-art-tattoo>"
}}""")
])

enrich_chain = enrich_prompt | llm_deterministic | StrOutputParser()


def enrich_shop(shop_name: str) -> Dict[str, Any]:
    """Uses LangChain chain to infer shop profile from name in < 1s."""
    if not shop_name or not shop_name.strip():
        return {}
    try:
        raw = enrich_chain.invoke({"shop_name": shop_name.strip()})
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"[LangChain-AI] Error enriching shop '{shop_name}': {e}")
    return {}


# ── 2. Natural Reviews Batch Generation Chain ─────────────────

batch_reviews_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are {count} different real customers who visited "{shop_name}" ({shop_type}).
Write exactly {count} authentic, natural, human 5-star Google reviews in English.

Crucial Realism Rules:
- Mix lengths: some short (1 quick sentence, e.g. "Great work and the owner's behaviour is very polite!"), some medium (2 sentences), some 3 sentences.
- Keep them simple, casual and natural — NOT overly specific product catalogs.
- Focus on real-life general experiences: polite & helpful behaviour of the owner and staff, great quality of work, clean and welcoming place, fair pricing, fast service.
- Sound like {count} DIFFERENT ordinary people who had a genuinely good experience. Avoid robotic AI phrasing or marketing hype.
- Occasionally include 1 natural emoji (e.g. ⭐, 👍, ✨).

Respond ONLY with a valid JSON array of {count} strings, no markdown formatting:
[
  "Review 1...",
  "Review 2..."
]"""),
    ("human", "Generate {count} genuine 5-star reviews for {shop_name} ({shop_type}).")
])

batch_reviews_chain = batch_reviews_prompt | llm_creative | StrOutputParser()


def generate_natural_reviews_batch(shop_name: str, shop_type: str, count: int = 10) -> List[str]:
    """Generates authentic, casual, human 5-star reviews via LangChain."""
    try:
        raw = batch_reviews_chain.invoke({
            "shop_name": shop_name,
            "shop_type": shop_type,
            "count": count
        })
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        match = re.search(r'\[.*\]', cleaned, re.DOTALL)
        if match:
            items = json.loads(match.group())
            if isinstance(items, list) and len(items) >= 5:
                return [str(x).strip() for x in items if str(x).strip()]
    except Exception as e:
        print(f"[LangChain-AI] Error generating natural reviews batch: {e}")

    # Fallback realistic reviews
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


# ── 3. Custom Customer Review Expansion Chain ─────────────────

custom_review_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are helping a customer write their genuine 5-star Google Review.
Business: {shop_name} ({shop_type})
Customer's words / experience: "{user_input}"

Task:
Write a short, natural, glowing 5-star Google review (2-3 sentences) in English based on what the customer experienced.
Rules:
- Keep the customer's specific point (e.g. what they purchased or experienced)
- Polish into natural, authentic English that sounds like a real person
- Add 1-2 natural emojis (e.g. ⭐, ✨, 👍)
- Respond with ONLY the review text itself, no quotes, no conversational filler, no markdown."""),
    ("human", "Transform customer's notes into a 5-star review: {user_input}")
])

custom_review_chain = custom_review_prompt | llm_creative | StrOutputParser()


def generate_custom_review(shop_name: str, shop_type: str, user_input: str) -> str:
    """Takes user notes and expands into natural 5-star Google review using LangChain."""
    if not user_input or not user_input.strip():
        return f"Had an amazing experience at {shop_name}! Top quality service and wonderful staff. Highly recommended! ⭐⭐⭐⭐⭐"

    try:
        review = custom_review_chain.invoke({
            "shop_name": shop_name,
            "shop_type": shop_type,
            "user_input": user_input.strip()
        })
        return review.strip().strip('"').strip("'")
    except Exception as e:
        print(f"[LangChain-AI] Error generating custom review: {e}")
        return f"Had a great experience at {shop_name}! {user_input.strip()}. Highly recommended! ⭐"


# ── 4. Streaming Reviews Chain ────────────────────────────────

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


def stream_reviews_for_aspect(shop_name, shop_type, description, keywords, aspect):
    """Streams tokens via LangChain ChatGroq stream."""
    try:
        prompt_text = build_prompt(shop_name, shop_type, description, keywords, aspect)
        full_text = ""
        for chunk in llm_creative.stream(prompt_text):
            token = chunk.content or ""
            if token:
                full_text += token
                yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"

        clean = re.sub(r"```(?:json)?", "", full_text).strip().rstrip("`").strip()
        match = re.search(r'\[.*\]', clean, re.DOTALL)
        if match:
            reviews = json.loads(match.group())
            yield f"data: {json.dumps({'type': 'done', 'reviews': reviews})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Could not parse JSON'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
