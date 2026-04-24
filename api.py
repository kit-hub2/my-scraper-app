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
    
    # ▼ 変更：現在の日付から12日前以降のデータ、または日付不明（1900-01-01）のデータだけを取得する
    cursor.execute('''
        SELECT id, prefecture, site_name, title, url, published_date 
        FROM public_offers 
        WHERE published_date >= CURRENT_DATE - INTERVAL '12 days' 
           OR published_date = '1900-01-01'
        ORDER BY published_date DESC, id DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "prefecture": row[1],
            "site_name": row[2],
            "title": row[3],
            "url": row[4],
            "published_date": row[5].strftime('%Y-%m-%d') if row[5] else "日付不明"
        })
    return results

@app.get("/")
def read_index():
    return FileResponse('index.html')