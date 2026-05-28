# Deployment Plan: TasteTrail AI on Streamlit Community Cloud

This document provides a step-by-step guide to deploying the Streamlit version of the restaurant recommendation system (`streamlit_app.py`) on **Streamlit Community Cloud**.

---

## 1. Prerequisites

Before starting, ensure that:
1. The codebase is pushed to a public (or private) GitHub repository.
2. The root folder contains `requirements.txt` with all required dependencies:
   - `streamlit`
   - `datasets`
   - `pandas`
   - `pydantic`
   - `python-dotenv`
   - `groq`
3. The entry point of the Streamlit application is located at `streamlit_app.py` in the root (which delegates to `app/presentation/ui.py`). The application has built-in path bootstrapping to prevent import errors (`ModuleNotFoundError: app`) when deployed.

---

## 2. Step-by-Step Deployment on Streamlit Community Cloud

Streamlit Community Cloud is a free hosting service provided by Streamlit.

### Step 2.1: Sign In
1. Go to [share.streamlit.io](https://share.streamlit.io/).
2. Sign in using your GitHub account associated with the project repository.

### Step 2.2: Set Up the App
1. Click the **"New app"** or **"Deploy an app"** button.
2. Fill in the deployment details:
   - **Repository**: Choose the GitHub repository containing the project.
   - **Branch**: Select the deployment branch (typically `main` or `master`).
   - **Main file path**: Enter `streamlit_app.py`.

### Step 2.3: Configure Secrets (Environment Variables)
Since the recommendation engine relies on environment variables (such as the Hugging Face dataset ID and the Groq API key), you must set these up in Streamlit Cloud:

1. Click on **"Advanced settings"** before deploying.
2. In the **"Secrets"** text area, define your variables in TOML format:
   ```toml
   # LLM Integration
   LLM_PROVIDER = "groq"
   LLM_MODEL = "llama-3.3-70b-versatile"
   LLM_TEMPERATURE = 0.3
   GROQ_API_KEY = "your-groq-api-key-here"

   # Ingestion
   HF_DATASET_ID = "ManikaSaini/zomato-restaurant-recommendation"
   HF_LOAD_RETRIES = 3
   HF_LOAD_RETRY_DELAY_SEC = 2.0

   # Pipeline Settings
   MAX_CANDIDATES = 30
   DEFAULT_TOP_N = 5
   FALLBACK_RELAXATION = true
   ```
3. Click **"Save"**.

### Step 2.4: Deploy
1. Click **"Deploy!"**.
2. Streamlit Cloud will spin up a container, install the dependencies listed in `requirements.txt`, and launch the app.

---

## 3. Post-Deployment Notes

### Initial Load Latency
On the very first user interaction (or when the app starts), the backend will download the Zomato Hugging Face dataset (~574 MB).
- **Execution Time**: The dataset download might take 1–3 minutes depending on Hugging Face Hub speeds.
- **Caching**: The dataset load uses Streamlit's session state and Python caching libraries, meaning subsequent requests within the active container session will be instantaneous.

### Secrets Security
Streamlit Community Cloud encrypts all secrets configured in the console. Never commit raw API keys or `.env` files directly to GitHub.
