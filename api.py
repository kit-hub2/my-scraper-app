from fastapi import FastAPI
import sqlite3
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/offers")
def get_offers():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    # 最新のものが上に来るように ORDER BY id DESC を追加
    cursor.execute('SELECT * FROM public_offers ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "site_name": row[1], # ←ここを追加！
            "title": row[2],     # インデックス番号を1つずつズラす
            "url": row[3]        # インデックス番号を1つずつズラす
        })
        
    return results

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# HTMLファイルをブラウザに表示するための設定
@app.get("/")
def read_index():
    return FileResponse('index.html')