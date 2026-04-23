import os
import requests
from bs4 import BeautifulSoup
import psycopg2
from urllib.parse import urljoin
import time
from dotenv import load_dotenv

# .envファイルから隠しパスワードを読み込む
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

TARGET_SITES = [
    {
        "name": "福岡市",
        "url": "https://www.city.fukuoka.lg.jp/business/keiyaku-kobo/teiankyogi.html"
    },
    {
        "name": "北九州市",
        "url": "https://www.city.kitakyushu.lg.jp/business/menu03_00174.html"
    }
]

# --- Supabaseに接続 ---
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# PostgreSQL用のテーブル作成文（自動連番が SERIAL という名前に変わります）
cursor.execute('''
    CREATE TABLE IF NOT EXISTS public_offers (
        id SERIAL PRIMARY KEY,
        site_name TEXT, 
        title TEXT,
        url TEXT UNIQUE
    )
''')
conn.commit()

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

total_count = 0

for site in TARGET_SITES:
    print(f"▼ 【{site['name']}】のサイトをチェック中...")
    try:
        response = requests.get(site['url'], headers=headers)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a')
        
        site_count = 0
        for link in links:
            title = link.text.strip()
            link_url = link.get('href')
            
            if not title or not link_url:
                continue
                
            if "募集" in title or "提案競技" in title or "プロポーザル" in title or "質問と回答" in title:
                full_url = urljoin(site['url'], link_url)
                
                # PostgreSQL用のデータ挿入文（? が %s になり、重複無視の文法が変わります）
                cursor.execute('''
                    INSERT INTO public_offers (site_name, title, url)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (url) DO NOTHING
                ''', (site['name'], title, full_url))
                
                # INSERTが成功したかチェック
                if cursor.rowcount > 0:
                    site_count += 1
                    total_count += 1

        print(f"  → {site_count} 件の新着情報を保存しました。")
    except Exception as e:
        print(f"  × エラーが発生しました: {e}")
        
    time.sleep(2)

conn.commit()
print(f"\n★ 全サイトの巡回が完了しました！（合計 {total_count} 件の新規追加）")
conn.close()