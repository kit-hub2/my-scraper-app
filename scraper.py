import requests
from bs4 import BeautifulSoup
import sqlite3
from urllib.parse import urljoin
import time # 追加：連続アクセスを避けて待機するためのツール

# --- 1. 巡回するサイトのリスト（ここにどんどん追加できます） ---
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

# --- 2. データベースの準備（site_name を追加） ---
conn = sqlite3.connect('data.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS public_offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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

# --- 3. リストの順番にサイトを巡回してスクレイピング ---
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
                
            # キーワードで絞り込み
            if "募集" in title or "提案競技" in title or "プロポーザル" in title or "質問と回答" in title:
                full_url = urljoin(site['url'], link_url)
                
                # DBに保存（site_nameも一緒に保存する）
                cursor.execute('''
                    INSERT OR IGNORE INTO public_offers (site_name, title, url)
                    VALUES (?, ?, ?)
                ''', (site['name'], title, full_url))
                
                if cursor.rowcount > 0:
                    site_count += 1
                    total_count += 1

        print(f"  → {site_count} 件の新着情報を保存しました。")
        
    except Exception as e:
        print(f"  × エラーが発生しました: {e}")
        
    # 相手のサーバーに負荷をかけないよう、次のサイトに行く前に2秒待つ（マナー）
    time.sleep(2)

conn.commit()
print(f"\n★ 全サイトの巡回が完了しました！（合計 {total_count} 件の新規追加）")
conn.close()