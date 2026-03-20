"""Take screenshots of all frontend pages using Playwright."""
from playwright.sync_api import sync_playwright
import time
import os

BASE_URL = os.environ.get('SCREENSHOT_BASE_URL', 'http://localhost:3001')
OUT = os.path.join(os.path.dirname(__file__), '..', 'docs', 'screenshots')
os.makedirs(OUT, exist_ok=True)

PAGES = [
    ('/', 'dashboard.png'),
    ('/finetuning', 'finetuning.png'),
    ('/observability', 'observability.png'),
    ('/streaming', 'streaming.png'),
    ('/search', 'search.png'),
    ('/observatory', 'observatory.png'),
    ('/upload', 'upload.png'),
    ('/local', 'local_pipeline.png'),
    ('/intelligence', 'intelligence.png'),
]

with sync_playwright() as p:
    browser = p.chromium.launch(args=['--no-sandbox'])

    for path, fname in PAGES:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        try:
            page.goto(f'{BASE_URL}{path}', timeout=15000)
            page.wait_for_timeout(3000)
            body_size = len(page.inner_html('body'))
            out_path = os.path.join(OUT, fname)
            page.screenshot(path=out_path)
            disk_size = os.path.getsize(out_path)
            print(f'OK {fname}: DOM={body_size}b, disk={disk_size // 1024}KB')
        except Exception as e:
            print(f'ERR {fname}: {e}')
        finally:
            page.close()

    browser.close()

print('Screenshots done!')
