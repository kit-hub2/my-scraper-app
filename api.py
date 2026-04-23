import os
from fastapi import FastAPI
import psycopg2
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/offers")
def get_offers():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM public_offers ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "site_name": row[1],
            "title": row[2],
            "url": row[3]
        })
    return results

# 今回追加した「1つのURLでHTMLも表示する」ための設定
@app.get("/")
def read_index():
    return FileResponse('index.html')