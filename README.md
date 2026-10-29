# Google NFC Smart Review System

An end-to-end smart Google Review automation system designed for physical NFC smart cards and QR codes. When customers tap an NFC card or scan a QR code at a store or clinic, they get a frictionless, AI-assisted review experience with carousel review selection, keyword customization, and instant Google Review posting.

---

## 🌟 Key Features

### 1. 📲 Customer Experience (`/r/<card_id>`)
* **Touch-Optimized Carousel**: Smooth touch and swipe cards (both mobile swipe and arrow buttons).
* **AI Smart Review Suggestions**: Pre-generated natural, casual, and authentic customer reviews stored in the database.
* **Instant Keyword Customization**: Visitors can add their own personalized comments/products and click "Generate" to generate a tailored 5-star review.
* **One-Click Google Review**: Copies the selected review to clipboard and opens the store's official Google review dialog with 5 stars pre-selected.
* **Smart Review Pool & Auto-Refill**: Rotates 5 reviews per scan from an initial pool of 10. Automatically clears exhausted reviews and refills with 10 fresh authentic variations.

### 2. ⚡ Executive Admin Dashboard (`/`)
* **Modern Executive White Theme**: High-contrast, clean SaaS UI inspired by Stripe and Google Cloud design systems.
* **Store Directory & Instant Search**: Filter cards by ID, store name, or live/paused status.
* **Dedicated Card Analytics**:
  * Real-time scan metrics: Today, This Month, This Year, and Lifetime scans.
  * Master Service Status Switch: Instantly activate or pause review services for any physical card.
* **Mobile-First UX with Swipe-Back Navigation**:
  * Edge swipe-right touch gesture to return from detail views to the overview list.
  * Browser history integration (`popstate` + `#card=ID`) preventing accidental app exits.
* **Automated Store Profile Detection**: Paste any Google Maps share link to auto-extract Place ID, store name, business category, and keywords.

### 3. 🗄️ Database & Cloud Architecture
* **Supabase PostgreSQL & SQLite Hybrid**: Native support for Supabase PostgreSQL (via `DATABASE_URL`) with automatic local SQLite fallback.
* **Async Groq AI Integration**: Generates contextual, natural-sounding reviews via Groq's high-speed inference engine (`llama-3.3-70b-versatile`).

---

## 🚀 Quick Start

### 1. Prerequisites
* Python 3.10+
* Groq API Key ([Get Groq API Key](https://console.groq.com))
* (Optional) Supabase PostgreSQL database

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/JainKushal556/google-review-backend-system.git
cd google-review-backend-system

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

```ini
GROQ_API_KEY=your_groq_api_key_here
SECRET_KEY=your_random_secret_key
# Optional: Supabase PostgreSQL (if omitted, local reviews.db SQLite is used)
DATABASE_URL=postgresql://postgres.xxxx:your_password@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require
```

### 4. Running the Server
```bash
python main.py
```
Open your browser at:
* **Admin Dashboard**: `http://localhost:5000`
* **NFC Customer Link**: `http://localhost:5000/r/<card_id>`

---

## 📁 Project Structure

```
├── main.py              # Flask server, routing, and REST API endpoints
├── database.py          # Unified database layer (Supabase PostgreSQL / SQLite)
├── ai_service.py        # Groq AI review generation and natural language prompt logic
├── templates/
│   ├── admin.html       # Executive White Theme admin dashboard
│   ├── customer.html    # Touch-optimized customer review carousel landing page
│   ├── processing.html  # Dynamic setup loading screen
│   └── inactive.html    # Maintenance / service paused notice
├── requirements.txt     # Python package requirements
├── .env.example         # Example configuration file
└── .gitignore           # Protects credentials and local database
```

---

## 🔒 Security
* Sensitive environment variables (`.env`, `pass.txt`) and local database files are excluded via `.gitignore`.
* Database connections enforce SSL mode when connecting to PostgreSQL.
