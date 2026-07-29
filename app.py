import os
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import httpx

from nli_engine import NLIFactCheckerEngine


app = FastAPI(title="Real-Time NLI Fact-Checker Dashboard")

# 1. Resolve absolute path to the directory containing app.py
BASE_DIR = Path(__file__).resolve().parent

# 2. Mount static directory using BASE_DIR
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# 3. Load templates using BASE_DIR
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Initialize Engine
nli_engine = None

@app.on_event("startup")
def startup_event():
    global nli_engine
    nli_engine = NLIFactCheckerEngine()

class AnalyzeRequest(BaseModel):
    text: str

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/analyze")
async def analyze_claim(request: Request):
    try:
        data = await request.json()
        text = data.get("text", "")
        
        if not text or len(text.strip()) < 10:
            raise HTTPException(status_code=400, detail="Text input cannot be empty or under 10 characters.")
            
        report = nli_engine.analyze(text)
        return JSONResponse(content=report.model_dump() if hasattr(report, 'model_dump') else report.dict())
        
    except Exception as e:
        print(f"[ERROR IN /analyze]: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- Live News Endpoints ---
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "c5ffc7f1a56d42fdbe6f2cc8c10b8a96")

@app.get("/api/breaking-news")
async def get_breaking_news():
    url = f"https://newsapi.org/v2/top-headlines?language=en&pageSize=10&apiKey={NEWS_API_KEY}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        return res.json()

@app.get("/api/visual-news")
async def get_visual_news():
    url = f"https://newsapi.org/v2/top-headlines?category=technology&language=en&pageSize=6&apiKey={NEWS_API_KEY}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        return res.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)