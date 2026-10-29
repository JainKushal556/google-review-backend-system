# Google NFC Smart Review System (FastAPI + LangChain + React)

A modern, high-performance Google Review automation platform designed for physical NFC smart cards and QR codes.

* **Backend Engine:** **FastAPI** (Python 3.11+, Uvicorn, Pydantic, BackgroundTasks)
* **AI Orchestration:** **LangChain** + **ChatGroq** (`qwen/qwen3.8-27b`)
* **Frontend App:** **React** + **Vite** (Executive White UI, Mobile Touch Gestures)
* **Cloud Infrastructure:** **Render** (Backend API) & **Vercel** (Global Frontend CDN)
* **Database:** **Supabase PostgreSQL** with local SQLite fallback

---

## 🌟 Key Architecture & Features

### 1. ⚡ FastAPI Backend (`Render`)
* **Asynchronous High Concurrency:** Fast endpoints with sub-second response times.
* **OpenAPI / Swagger Documentation:** Interactive API explorer at `/docs` and `/redoc`.
* **LangChain Integration:** 
  * Structured business profile extraction chain.
  * Batch human-sounding 5-star review generation chain.
  * Customer notes-to-review expansion chain.
* **Background Tasks:** Asynchronously pre-generates 10 authentic reviews per store card without blocking HTTP response.

### 2. ⚛️ React Frontend (`Vercel`)
* **Executive White Theme:** Sleek, high-contrast dashboard with Google color accents and tactile NFC card layouts.
* **Mobile-First Touch Gestures:** Native edge swipe-right to return from card details view; browser history integration (`popstate`).
* **Customer Review Carousel:** 5-star cards carousel, 1-click clipboard copy + direct official Google Review write popup, and AI custom review tab.

---

## 🚀 Deployment Guide

### A. Deploy Backend to Render (FastAPI)
1. In Render, create a new **Web Service** from this GitHub repository.
2. Configuration:
   * **Runtime:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Environment Variables:
   * `GROQ_API_KEY`: Your Groq API key
   * `SECRET_KEY`: Random secret string
   * `DATABASE_URL`: Supabase PostgreSQL connection string

### B. Deploy Frontend to Vercel (React)
1. Import this GitHub repo in **Vercel**.
2. Vercel automatically detects the included `vercel.json`:
   * **Framework Preset:** Vite
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
* Swagger Docs: `http://localhost:5000/docs`

### 2. Start React Frontend
```bash
cd frontend
npm install
npm run dev
```
* App: `http://localhost:5173`
