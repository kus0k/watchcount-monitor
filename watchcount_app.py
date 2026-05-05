from flask import Flask, render_template, request, jsonify
import threading
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import sys
import re
import json
import random
import os

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

class WatchCountMonitor:
    def __init__(self):
        self.is_running = False
        self.found_auctions = set()
        self.logs = []
        self.auctions = []
        self.monitor_thread = None
        self.ending_time = 1

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        if len(self.logs) > 100:
            self.logs.pop(0)

    def add_auction(self, title, price, bids, url, time_left):
        auction = {
            'title': title,
            'price': price,
            'bids': bids,
            'url': url,
            'time_left': time_left,
            'timestamp': datetime.now().strftime("%H:%M:%S")
        }
        self.auctions.insert(0, auction)
        if len(self.auctions) > 50:
            self.auctions.pop()

    def start_monitoring(self, keywords, min_price, max_price, min_bids, ending_time, interval):
        if self.is_running:
            return False

        self.is_running = True
        self.logs = []
        self.auctions = []
        self.ending_time = ending_time

        self.log("="*80)
        self.log("🚀 МОНИТОРИНГ WATCHCOUNT ЗАПУЩЕН")
        self.log("="*80)

        if keywords:
            self.log(f"🔍 Ключевые слова: {keywords}")
        else:
            self.log(f"🔍 Поиск: ВСЕ аукционы")

        self.log(f"💰 Цена: ${min_price} - ${max_price}")
        self.log(f"📊 Минимум ставок: {min_bids}")
        self.log(f"⏱️  Время завершения: {ending_time} мин")
        self.log(f"⏱️  Интервал: {interval} сек")
        self.log("="*80 + "\n")

        self.monitor_thread = threading.Thread(
            target=self.monitor_loop,
            args=(keywords, min_price, max_price, min_bids, interval),
            daemon=True
        )
        self.monitor_thread.start()
        return True

    def stop_monitoring(self):
        self.is_running = False
        self.log("\n⏹️  Мониторинг остановлен.\n")

    def monitor_loop(self, keywords, min_price, max_price, min_bids, interval):
        while self.is_running:
            try:
                if keywords:
                    for keyword in keywords.split(','):
                        if not self.is_running:
                            break
                        self.search_watchcount(keyword.strip(), min_price, max_price, min_bids)
                        time.sleep(2)
                else:
                    self.search_watchcount('', min_price, max_price, min_bids)

                self.log(f"⏳ Следующая проверка через {interval} сек...\n")
                time.sleep(interval)
            except Exception as e:
                self.log(f"❌ Ошибка: {str(e)}")
                time.sleep(5)

    def search_watchcount(self, keyword, min_price, max_price, min_bids):
        try:
            if keyword:
                self.log(f"🔍 Поиск: '{keyword}'...")
            else:
                self.log(f"🔍 Поиск: ВСЕ аукционы...")

            # WatchCount URL для поиска
            if keyword:
                url = f"https://www.watchcount.com/search.php?q={keyword}&sort=ending_soonest"
            else:
                url = "https://www.watchcount.com/search.php?sort=ending_soonest"

            headers = {
                'User-Agent': get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.watchcount.com/',
            }

            try:
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
            except Exception as e:
                self.log(f"   ⚠️ Ошибка подключения: {str(e)[:80]}")
                return

            try:
                soup = BeautifulSoup(response.content, 'html.parser')
            except Exception as e:
                self.log(f"   ⚠️ Ошибка парсинга HTML: {str(e)}")
                return

            # Ищем строки таблицы с аукционами
            items = soup.find_all('tr', {'class': 'item_row'})

            if not items:
                self.log(f"   ⚠️ Результаты не найдены")
                return

            self.log(f"   ✓ Найдено {len(items)} аукционов")
            found_count = 0

            for item in items:
                try:
                    # Название и ссылка
                    title_elem = item.find('a', {'class': 'item_title'})
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    item_url = title_elem.get('href', '')

                    # Цена
                    price_elem = item.find('td', {'class': 'price'})
                    if not price_elem:
                        continue
                    price_text = price_elem.get_text(strip=True)
                    try:
                        price = float(re.sub(r'[^\d.]', '', price_text.split()[0]))
                    except:
                        continue

                    # Ставки
                    bids_elem = item.find('td', {'class': 'bids'})
                    bids = 0
                    if bids_elem:
                        try:
                            bids_text = bids_elem.get_text(strip=True)
                            bids = int(re.sub(r'[^\d]', '', bids_text.split()[0]))
                        except:
                            bids = 0

                    # Время завершения
                    time_elem = item.find('td', {'class': 'time_left'})
                    time_left = "N/A"
                    if time_elem:
                        time_left = time_elem.get_text(strip=True)

                    # Проверяем фильтры
                    if price >= min_price and price <= max_price and bids >= min_bids:
                        # Проверяем время завершения
                        if self.check_ending_time(time_left):
                            auction_id = f"{title}_{item_url}"
                            if auction_id not in self.found_auctions:
                                self.found_auctions.add(auction_id)
                                self.log(f"✅ НАЙДЕН: {title[:60]}... | ${price} | Ставок: {bids} | {time_left}")
                                self.add_auction(title, f"${price}", bids, item_url, time_left)
                                found_count += 1

                except Exception as e:
                    continue

            if found_count == 0:
                self.log(f"   Подходящих аукционов не найдено")

        except Exception as e:
            self.log(f"❌ Ошибка: {str(e)}")

    def check_ending_time(self, time_str):
        """Проверяет, заканчивается ли аукцион в течение ending_time минут"""
        try:
            # Парсим строку времени (например: "5m", "1h 30m", "2d 3h")
            time_str = time_str.lower().strip()
            total_minutes = 0

            # Дни
            days_match = re.search(r'(\d+)\s*d', time_str)
            if days_match:
                total_minutes += int(days_match.group(1)) * 24 * 60

            # Часы
            hours_match = re.search(r'(\d+)\s*h', time_str)
            if hours_match:
                total_minutes += int(hours_match.group(1)) * 60

            # Минуты
            mins_match = re.search(r'(\d+)\s*m', time_str)
            if mins_match:
                total_minutes += int(mins_match.group(1))

            return total_minutes <= self.ending_time * 60
        except:
            return False

monitor = WatchCountMonitor()

@app.route('/')
def index():
    response = render_template('watchcount.html')
    response = app.make_response(response)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

@app.route('/api/start', methods=['POST'])
def start():
    try:
        data = request.json
        keywords = data.get('keywords', '')
        min_price = float(data.get('min_price', 0))
        max_price = float(data.get('max_price', 999999))
        min_bids = int(data.get('min_bids', 1))
        ending_time = int(data.get('ending_time', 1))
        interval = int(data.get('interval', 60))

        print(f"DEBUG: Starting WatchCount monitoring with: keywords={keywords}, min_price={min_price}, max_price={max_price}, min_bids={min_bids}, ending_time={ending_time}, interval={interval}")
        success = monitor.start_monitoring(keywords, min_price, max_price, min_bids, ending_time, interval)
        return json.dumps({'success': success}, ensure_ascii=False)
    except Exception as e:
        print(f"DEBUG: Error in start(): {str(e)}")
        return json.dumps({'success': False, 'error': str(e)}, ensure_ascii=False)

@app.route('/api/stop', methods=['POST'])
def stop():
    try:
        monitor.stop_monitoring()
        return json.dumps({'success': True}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({'success': False, 'error': str(e)}, ensure_ascii=False)

@app.route('/api/status')
def status():
    try:
        return json.dumps({
            'running': monitor.is_running,
            'logs': monitor.logs[-20:],
            'auctions': monitor.auctions[:10]
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({'error': str(e)}, ensure_ascii=False)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
