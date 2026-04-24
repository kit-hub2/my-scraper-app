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

NG_WORDS = ["入札", "落札"]

TARGET_SITES = [
    {"prefecture": "山口県", "name": "山口市", "url": "https://www.city.yamaguchi.lg.jp/life/2/18/92/"},
    {"prefecture": "山口県", "name": "下関市", "url": "https://www.city.shimonoseki.lg.jp/site/nyuusatu/list98-509.html"},
    {"prefecture": "福岡県", "name": "福岡市", "url": "https://www.city.fukuoka.lg.jp/business/keiyaku-kobo/teiankyogi.html"},
    {"prefecture": "福岡県", "name": "北九州市", "url": "https://www.city.kitakyushu.lg.jp/business/menu03_00174.html"},
    {"prefecture": "佐賀県", "name": "唐津市", "url": "https://www.city.karatsu.lg.jp/life/7/45/221/"},
    {"prefecture": "大分県", "name": "大分市", "url": "https://www.city.oita.oita.jp/shigotosangyo/proposal/proposal/kobogata/"},
    {"prefecture": "宮崎県", "name": "宮崎県", "url": "https://www.pref.miyazaki.lg.jp/kense/chotatsu/itaku/"},
    {"prefecture": "宮崎県", "name": "宮崎市", "url": "https://www.city.miyazaki.miyazaki.jp/business/bid/information/"}
]

def clean_date(date_str):
    if not date_str or date_str == "日付不明":
        return "1900-01-01"
    if "令和" in date_str:
        match = re.search(r'令和(\d+)年(\d+)月(\d+)日', date_str)
        if match:
            year = int(match.group(1)) + 2018
            return f"{year}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match = re.search(r'(\d+)年(\d+)月(\d+)日', date_str)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
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
                
                # --- 日付取得ロジックの最終進化形（宮崎県などの特殊構造対応） ---
                container = link.find_parent(['li', 'tr', 'dd', 'p', 'div', 'dl'])
                parent_text = container.get_text() if container else link.parent.get_text()
                
                published_date_raw = None

                # ▼ 追加：宮崎県対策（dl/dt/dd 構造などの分離型に対応）
                # リンク自身のテキストの中に日付が含まれていない場合、
                # ページ全体（または親要素）のテキストの中で、このリンクの直前に出現した日付を探す
                if not re.search(r'\d+月\d+日', parent_text):
                    # リンクの親要素を少し広めに取る（例えばリスト全体など）
                    wrapper = link.find_parent(['ul', 'ol', 'dl', 'table', 'body'])
                    if wrapper:
                        wrapper_text = wrapper.get_text()
                        link_text_index = wrapper_text.find(link.text.strip())
                        
                        # リンクのテキストより前にある部分を切り出す
                        if link_text_index != -1:
                            text_before_link = wrapper_text[:link_text_index]
                            # 切り出したテキストの中で「最後に出現した日付」を探す
                            all_dates_before = re.findall(r'((?:(?:20\d{2}|令和\d+)年)?\d+月\d+日)', text_before_link)
                            if all_dates_before:
                                # 直近（最後）の日付を取得し、parent_text に合体させる
                                parent_text = all_dates_before[-1] + " " + parent_text

                # 2-A. 「更新日：〇月〇日」のようにキーワードが【前】にあるパターン
                update_match_before = re.search(r'(?:更新|掲載|公開|登録)(?:日)?[:：\s]*((?:(?:20\d{2}|令和\d+)年)?\d+月\d+日)', parent_text)
                
                # 2-B. 「〇月〇日更新」のようにキーワードが【後ろ】にあるパターン
                update_match_after = re.search(r'((?:(?:20\d{2}|令和\d+)年)?\d+月\d+日)[\s]*(?:更新|掲載|公開|登録)', parent_text)
                
                if update_match_before:
                    published_date_raw = update_match_before.group(1)
                elif update_match_after:
                    published_date_raw = update_match_after.group(1)
                else:
                    all_dates = re.findall(r'((?:(?:20\d{2}|令和\d+)年)?\d+月\d+日)', parent_text)
                    if all_dates:
                        # 3. 「締切」や「期限」が近くにない日付があれば、それを優先する
                        for d in all_dates:
                            start_idx = max(0, parent_text.find(d) - 10)
                            end_idx = parent_text.find(d) + len(d) + 10
                            context = parent_text[start_idx:end_idx]
                            
                            if "締切" not in context and "期限" not in context:
                                published_date_raw = d
                                break
                                
                        # 4. もしすべての日付に「締切」がついていたら
                        if not published_date_raw:
                            published_date_raw = all_dates[0]
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