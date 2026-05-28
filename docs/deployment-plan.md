# Deployment Plan: Decoupled Architecture on Railway & Vercel

This document outlines the step-by-step guide to deploying the **TasteTrail AI** application:
1. **Backend**: FastAPI API server deployed on **Railway**.
2. **Frontend**: React + Vite + TypeScript web application deployed on **Vercel**.

---

## 1. Prerequisites

Before starting, ensure that:
1. The codebase is pushed to a GitHub repository (public or private).
2. The root folder contains `requirements.txt` with backend dependencies (specifically `fastapi` and `uvicorn`).
3. The frontend codebase is located in the `frontend` subdirectory.

---

## 2. Backend Deployment on Railway

Railway is a cloud platform that makes it easy to deploy backend applications and databases.

### Step 2.1: Sign In & Link GitHub
1. Go to [railway.app](https://railway.app/) and sign in using your GitHub account.

### Step 2.2: Create a New Project
1. In the Railway dashboard, click **"New Project"**.
2. Select **"Deploy from GitHub repo"**.
3. Choose the repository for `Zomato-Top-5-Restaurant-Search-Project`.

### Step 2.3: Configure Start Command
By default, Railway will detect the Python environment. However, you need to tell it how to run the FastAPI app:
1. Go to the **Settings** tab of the service.
2. Under **Deploy**, find the **Start Command** setting.
3. Set the start command to:
   ```bash
   uvicorn app.api.main:app --host 0.0.0.0 --port $PORT
   ```

### Step 2.4: Configure Environment Variables (Variables)
Go to the **Variables** tab of the service on Railway, and add the following keys:

| Variable Name | Example Value | Description |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `groq` (or `mock` for testing) | The LLM provider to use |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | The LLM model name |
| `LLM_TEMPERATURE` | `0.3` | Controls randomness of recommendations |
| `GROQ_API_KEY` | `gsk_your_groq_api_key_here` | Your actual Groq API Key |
| `HF_DATASET_ID` | `ManikaSaini/zomato-restaurant-recommendation` | Hugging Face Dataset path |
| `HF_LOAD_RETRIES` | `3` | Retries for loading dataset |
| `HF_LOAD_RETRY_DELAY_SEC` | `2.0` | Retry delay in seconds |
| `MAX_CANDIDATES` | `30` | Number of candidate restaurants to pre-filter |
| `DEFAULT_TOP_N` | `5` | Default number of recommendations |
| `FALLBACK_RELAXATION` | `true` | Relax filters if not enough candidates match |

### Step 2.5: Generate Domain (Public URL)
1. Go to the **Settings** tab of the backend service.
2. Under **Networking**, click **"Generate Domain"** (or configure a custom domain).
3. Copy the generated URL (e.g., `https://your-backend.up.railway.app`). You will need this for the frontend configuration.

---

## 3. Frontend Deployment on Vercel

Vercel is optimized for frontend deployments, providing fast hosting and global CDN delivery.

### Step 3.1: Sign In & Import
1. Go to [vercel.com](https://vercel.com/) and sign in with your GitHub account.
2. Click **"Add New"** -> **"Project"**.
3. Import the `Zomato-Top-5-Restaurant-Search-Project` repository.

### Step 3.2: Configure Root Directory
Since the frontend code is in a monorepo subdirectory:
1. Next to **Root Directory**, click **"Edit"**.
2. Select the `frontend` folder and click **"Continue"**.

### Step 3.3: Configure Build & Development Settings
Vercel should automatically detect **Vite** as the framework. Double-check that:
- **Framework Preset**: `Vite`
- **Build Command**: `npm run build` (or `vite build`)
- **Output Directory**: `dist`

### Step 3.4: Configure Environment Variables
Expand the **Environment Variables** section and add:

- **Key**: `VITE_API_BASE`
- **Value**: `https://your-backend.up.railway.app/api` (Replace with your actual Railway domain URL copied in Step 2.5, keeping `/api` at the end).

### Step 3.5: Deploy
1. Click **"Deploy"**.
2. Vercel will install dependencies, build the static site, and deploy it to a production URL (e.g., `https://zomato-top-5.vercel.app`).

---

## 4. Post-Deployment Notes

### Dataset Initialization on Startup
The backend loads the Hugging Face dataset on startup using FastAPI's `@app.on_event("startup")` hook.
- **Boot Time**: The initial container startup might take 1–3 minutes to download the ~574 MB dataset.
- **Health Checks**: Ensure Railway's TCP health checks are configured with a generous timeout (e.g., 180 seconds) to account for the first-run dataset download.

### CORS Security
The backend in `app/api/main.py` is configured with `CORSMiddleware` allowing `allow_origins=["*"]`. This ensures the Vercel frontend can make requests to the Railway backend without issues. If you want to secure the backend, you can restrict `allow_origins` to your specific Vercel deployment URL.
