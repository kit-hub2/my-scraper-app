import os
import requests
from bs4 import BeautifulSoup
import psycopg2
from urllib.parse import urljoin
import time
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

NG_WORDS = ["入札", "落札", "一覧", "人事", "職員募集" ]

TARGET_SITES = [
    {"prefecture": "山口県", "name": "山口市", "url": "https://www.city.yamaguchi.lg.jp/life/2/18/92/"},
    {"prefecture": "山口県", "name": "岩国市", "url": "https://www.city.iwakuni.lg.jp/life/2/26/index-2.html"},
    {"prefecture": "山口県", "name": "宇部市", "url": "https://www.city.ube.yamaguchi.jp/boshu/"},
    {"prefecture": "山口県", "name": "下関市", "url": "https://www.city.shimonoseki.lg.jp/site/nyuusatu/list98-509.html"},
    {"prefecture": "山口県", "name": "周南市", "url": "https://www.city.shunan.lg.jp/life/6/28/index-2.html"},
    {"prefecture": "山口県", "name": "山口県観光サイト", "url": "https://yamaguchi-tourism.jp/business/"},
    {"prefecture": "福岡県", "name": "福岡市", "url": "https://www.city.fukuoka.lg.jp/business/keiyaku-kobo/teiankyogi.html"},
    {"prefecture": "福岡県", "name": "北九州市", "url": "https://www.city.kitakyushu.lg.jp/business/menu03_00174.html"},
    {"prefecture": "福岡県", "name": "糸島市", "url": "https://www.city.itoshima.lg.jp/li/kigyoujigyousya/100/"},
    {"prefecture": "福岡県", "name": "みやま市", "url": "https://www.city.miyama.lg.jp/li/kanko/050/040/"},
    {"prefecture": "福岡県", "name": "久留米観光サイト", "url": "https://welcome-kurume.com/news/"},
    {"prefecture": "佐賀県", "name": "唐津市", "url": "https://www.city.karatsu.lg.jp/life/7/45/221/"},
    {"prefecture": "大分県", "name": "大分県", "url": "https://www.pref.oita.jp/site/nyusatu-koubo/"},
    {"prefecture": "大分県", "name": "大分市", "url": "https://www.city.oita.oita.jp/shigotosangyo/proposal/proposal/kobogata/"},
    {"prefecture": "大分県", "name": "大分県観光サイト", "url": "https://www.visit-oita.jp/news/"},
    {"prefecture": "宮崎県", "name": "宮崎県", "url": "https://www.pref.miyazaki.lg.jp/kense/chotatsu/itaku/"},
    {"prefecture": "宮崎県", "name": "宮崎市", "url": "https://www.city.miyazaki.miyazaki.jp/business/bid/information/"}
]

# ▼ 変更：色々な日付の書き方に対応する最強の関数
def clean_date(date_str):
    if not date_str or date_str == "日付不明":
        return "1900-01-01"
    
    # 全角・半角スペースを削除
    date_str = date_str.replace(" ", "").replace("　", "")
    
    if "令和" in date_str:
        match = re.search(r'令和(\d+)年(\d+)月(\d+)日', date_str)
        if match:
            year = int(match.group(1)) + 2018
            return f"{year}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
            
    # YYYY年MM月DD日 または YYYY/MM/DD または YYYY.MM.DD
    match = re.search(r'(\d{4})[年/\.](\d{1,2})[月/\.](\d{1,2})日?', date_str)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        
    # 年がない場合（例：4月22日）
    match_no_year = re.search(r'(\d{1,2})月(\d{1,2})日', date_str)
    if match_no_year:
        current_year = datetime.now().year
        return f"{current_year}-{int(match_no_year.group(1)):02d}-{int(match_no_year.group(2)):02d}"
        
    return "1900-01-01"

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS public_offers (
        id SERIAL PRIMARY KEY,
        prefecture TEXT,
        site_name TEXT,
        title TEXT,
        url TEXT UNIQUE,
        published_date DATE
    )
''')
conn.commit()

headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

total_count = 0
for site in TARGET_SITES:
    print(f"▼ 【{site['name']}】をチェック中...")
    try:
        response = requests.get(site['url'], headers=headers)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for link in soup.find_all('a'):
            title = link.text.strip()
            if any(word in title for word in NG_WORDS):
                continue

            if "募集" in title or "提案競技" in title or "プロポーザル" in title:
                full_url = urljoin(site['url'], link.get('href'))
                
                # --- 日付取得ロジックの最終進化形（空白・年なし・詳細ページ深掘り対応版） ---
                container = link.find_parent(['li', 'tr', 'dd', 'p', 'div', 'dl'])
                parent_text_raw = container.get_text() if container else link.parent.get_text()
                
                # 日本の自治体にありがちな「令和 8年 4月」のような空白を消去して検索しやすくする
                parent_text = parent_text_raw.replace(" ", "").replace("　", "")
                
                published_date_raw = None

                # 年が省略されているケース（4月22日など）やスラッシュ区切りも拾える正規表現
                date_pattern = r'((?:(?:20\d{2}|令和\d+)年)?\d{1,2}月\d{1,2}日|\d{4}[/\.]\d{1,2}[/\.]\d{1,2})'

                if not re.search(date_pattern, parent_text):
                    wrapper = link.find_parent(['ul', 'ol', 'dl', 'table', 'body'])
                    if wrapper:
                        wrapper_text_raw = wrapper.get_text()
                        link_text_index = wrapper_text_raw.find(link.text.strip())
                        
                        if link_text_index != -1:
                            text_before_link = wrapper_text_raw[:link_text_index]
                            clean_text_before = text_before_link.replace(" ", "").replace("　", "")
                            
                            all_dates_before = re.findall(date_pattern, clean_text_before)
                            if all_dates_before:
                                parent_text = all_dates_before[-1] + " " + parent_text

                # 2-A. キーワードが【前】にあるパターン
                update_match_before = re.search(r'(?:更新|掲載|公開|登録)(?:日)?[:：\s]*' + date_pattern, parent_text)
                # 2-B. キーワードが【後ろ】にあるパターン
                update_match_after = re.search(date_pattern + r'[\s]*(?:更新|掲載|公開|登録)', parent_text)
                
                if update_match_before:
                    published_date_raw = update_match_before.group(1)
                elif update_match_after:
                    published_date_raw = update_match_after.group(1)
                else:
                    all_dates = re.findall(date_pattern, parent_text)
                    if all_dates:
                        for d in all_dates:
                            start_idx = max(0, parent_text.find(d) - 10)
                            end_idx = parent_text.find(d) + len(d) + 10
                            context = parent_text[start_idx:end_idx]
                            
                            if "締切" not in context and "期限" not in context:
                                published_date_raw = d
                                break
                                
                        if not published_date_raw:
                            published_date_raw = all_dates[0]
                
                # ▼▼▼ さらなる進化（みやま市・糸島市対策）：一覧に日付がない場合はリンク先（詳細ページ）を覗き見する！ ▼▼▼
                if not published_date_raw:
                    try:
                        time.sleep(1) # サーバーへの負荷を下げるための待機
                        detail_resp = requests.get(full_url, headers=headers, timeout=10)
                        detail_resp.encoding = detail_resp.apparent_encoding
                        detail_soup = BeautifulSoup(detail_resp.text, 'html.parser')
                        
                        detail_text = detail_soup.get_text().replace(" ", "").replace("　", "")
                        
                        # 詳細ページから「更新日」や「掲載日」を探す
                        detail_update_match = re.search(r'(?:更新|掲載|公開|登録)(?:日)?[:：]*' + date_pattern, detail_text)
                        if detail_update_match:
                            published_date_raw = detail_update_match.group(1)
                        else:
                            # なければ詳細ページの一番最初にある日付を拾う
                            detail_all_dates = re.findall(date_pattern, detail_text)
                            if detail_all_dates:
                                published_date_raw = detail_all_dates[0]
                    except Exception as e:
                        pass # 詳細ページのエラーは無視して日付不明（1900-01-01）にする
                # ▲▲▲ ここまで ▲▲▲
                # ------------------------------

                formatted_date = clean_date(published_date_raw)
                
                cursor.execute('''
                    INSERT INTO public_offers (prefecture, site_name, title, url, published_date)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO NOTHING
                ''', (site['prefecture'], site['name'], title, full_url, formatted_date))
                
                if cursor.rowcount > 0:
                    total_count += 1
    except Exception as e:
        print(f"  × エラー: {e}")
    time.sleep(1)

conn.commit()
conn.close()
print(f"\n★ 完了！（{total_count} 件更新）")