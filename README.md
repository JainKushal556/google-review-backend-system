# Google NFC Smart Review System (FastAPI + LangChain + React)

A modern, enterprise-grade Google Review automation platform designed for physical NFC smart cards and QR codes.

* **Backend Engine:** **FastAPI** (Python 3.11+, Uvicorn, Pydantic, BackgroundTasks)
* **AI Orchestration:** **LangChain** + **ChatGroq** (`qwen/qwen3.8-27b`)
* **Frontend App:** **React 19** + **Vite** (Executive White UI, Mobile Touch Gestures)
* **Cloud Infrastructure:** **Render** (Backend API) & **Vercel** (Global Frontend CDN)
* **Database:** **Supabase PostgreSQL** with local SQLite fallback

---

## 📁 Repository Structure

```
google-review-backend-system/
│
├── frontend/                     # ⚛️ React + Vite Frontend (Deploy to Vercel)
│   ├── src/
│   │   ├── components/
│   │   │   ├── AdminDashboard.jsx  # Executive White Theme Admin Dashboard
│   │   │   └── CustomerReview.jsx  # 5★ Carousel & Custom AI Review Generator
│   │   ├── App.jsx               # Universal Route Manager with Popstate Support
│   │   ├── config.js             # Dynamic API URL Config (Render / Local)
│   │   ├── index.css             # Google Colors Design Tokens & CSS
│   │   └── main.jsx              # React 19 Entry Point
│   ├── public/                   # Web icons and SVG assets
│   ├── index.html                # HTML5 template with modern fonts
│   ├── package.json              # React, Lucide Icons, Vite
│   ├── vite.config.js            # Vite build configuration
│   └── vercel.json               # Vercel SPA rewrites configuration
│
├── main.py                       # ⚡ FastAPI Application Server (Render Entry)
├── database.py                   # 🗄️ Database Layer (Supabase PostgreSQL / SQLite)
├── ai_service.py                 # 🦜 LangChain Orchestration & Groq LLM Chains
├── templates/                    # 📄 Server-side Jinja Templates (Direct Preview)
│   ├── admin.html
│   ├── customer.html
│   ├── inactive.html
│   └── processing.html
├── requirements.txt              # Python requirements (FastAPI, LangChain, Uvicorn)
├── vercel.json                   # Root Vercel Monorepo build orchestrator
├── .python-version               # Python 3.11.9 for Render stability
├── .env.example                  # Environment configuration template
├── .gitignore                    # Protects credentials, databases and node_modules
└── README.md                     # Documentation
```

---

## 🚀 Deployment Guide

### A. Deploy Backend to Render (FastAPI)
1. In Render, select **Web Service** for this repo.
2. Configuration:
   * **Runtime:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Environment Variables:
   * `GROQ_API_KEY`: Your Groq API key
   * `SECRET_KEY`: Random secret string
   * `DATABASE_URL`: Supabase PostgreSQL connection string
4. Interactive Swagger Docs available at `/docs`!

### B. Deploy Frontend to Vercel (React)
1. Import this repository in **Vercel**.
2. Vercel automatically detects `vercel.json`:
   * **Framework:** Vite
   * **Build Command:** `cd frontend && npm install && npm run build`
   * **Output Directory:** `frontend/dist`
3. (Optional) Set Environment Variable in Vercel:
   * `VITE_API_BASE`: `https://google-review-backend-system.onrender.com`
4. Click **Deploy**!

---

## 💻 Local Development

### 1. Start FastAPI Backend
```bash
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```
* API: `http://localhost:5000`
* Swagger UI: `http://localhost:5000/docs`

### 2. Start React Frontend
```bash
cd frontend
npm install
npm run dev
```
* App: `http://localhost:5173`
