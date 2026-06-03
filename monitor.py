import time
import re
import html
import requests
from urllib.parse import urlparse, parse_qs, urljoin

# =========================
# CONFIG
# =========================

START_URL = "https://uptolink.vip/m3c42"

TELEGRAM_BOT_TOKEN = "8617724795:AAGGeN8dX9W8PQhiFqFWzTDuuoGL-Uu7a6w"
TELEGRAM_CHAT_ID = "6109525268"

SCAN_PER_ROUND = 10
DELAY_BETWEEN_SCAN = 0.5
DELAY_BETWEEN_ROUND = 120

RETRY_DELAY = 5


# =========================
# TELEGRAM
# =========================

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        r = requests.post(url, data=data, timeout=15)

        if r.ok:
            print("[TELEGRAM_SENT]")
        else:
            print("[TELEGRAM_ERROR]", r.status_code, r.text[:300])

    except Exception as e:
        print("[TELEGRAM_EXCEPTION]", e)


# =========================
# REDIRECT DETECT
# =========================

def find_html_redirect(base_url, text):
    text = html.unescape(text or "")

    patterns = [
        r'window\.location\.href\s*=\s*[\'"]([^\'"]+)[\'"]',
        r'window\.location\s*=\s*[\'"]([^\'"]+)[\'"]',
        r'location\.href\s*=\s*[\'"]([^\'"]+)[\'"]',
        r'location\.replace\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        r'location\.assign\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]+content=["\'][^"\']*url=([^"\'>]+)["\']',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)

        if match:
            found = match.group(1).strip()
            return urljoin(base_url, found)

    return None


def resolve_url(session, url, max_depth=5):
    current = url

    for step in range(1, max_depth + 1):
        response = session.get(
            current,
            allow_redirects=True,
            timeout=20
        )

        final_url = response.url
        print(f"[STEP {step}] HTTP_FINAL:", final_url)

        html_redirect = find_html_redirect(final_url, response.text)

        if html_redirect and html_redirect != final_url:
            print("[HTML_REDIRECT]", html_redirect)
            current = html_redirect
            continue

        return final_url

    return current


# =========================
# KEY EXTRACT
# =========================

def extract_key_slug(final_url):
    """
    Ví dụ:
    https://linkhuongdan.online/216-2/?qq=complete
    => 216-2
    """

    parsed = urlparse(final_url)

    if "linkhuongdan.online" not in parsed.netloc:
        return None

    query = parse_qs(parsed.query)
    qq = query.get("qq", [None])[0]

    if qq != "complete":
        return None

    path = parsed.path.strip("/")

    if not path:
        return None

    key_slug = path.split("/")[0]

    if not key_slug:
        return None

    return key_slug


# =========================
# SESSION
# =========================

def create_session():
    session = requests.Session()

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Mobile) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Mobile Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://uptolink.vip/",
        "Connection": "close"
    })

    return session


# =========================
# CHECK ONCE
# =========================

def check_once(scan_index):
    session = create_session()

    try:
        final_url = resolve_url(session, START_URL)

        print(f"[SCAN {scan_index}] FINAL_URL:", final_url)

        key_slug = extract_key_slug(final_url)

        if not key_slug:
            print(f"[SCAN {scan_index}] NO_CODE")
            return {
                "ok": True,
                "has_code": False,
                "key": None
            }

        print(f"[SCAN {scan_index}] HAS_CODE:", key_slug)

        return {
            "ok": True,
            "has_code": True,
            "key": key_slug
        }

    except Exception as e:
        print(f"[SCAN {scan_index}] ERROR:", e)

        return {
            "ok": False,
            "has_code": False,
            "key": None
        }


# =========================
# ROUND REPORT
# =========================

def send_round_report(round_index, keys):
    # Không có mã thì chỉ log ở Termux, KHÔNG gửi Telegram
    if not keys:
        print(f"[ROUND {round_index}] NO_CODE_REPORT_SKIPPED")
        return

    key_lines = "\n".join(
        f"▫️ <code>{key}</code>"
        for key in keys
    )

    message = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>PHÁT HIỆN CÓ MÃ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 <b>Luồng:</b> #{round_index}\n"
        f"🔎 <b>Số lần quét:</b> {SCAN_PER_ROUND}\n"
        f"🔑 <b>Số key:</b> {len(keys)}\n\n"
        f"📋 <b>Danh sách key:</b>\n"
        f"{key_lines}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    send_telegram(message)


# =========================
# ROUND
# =========================

def run_round(round_index):
    print("")
    print("==============================")
    print(f"[ROUND {round_index}] START")
    print("==============================")

    valid_scan_count = 0
    found_keys = []
    seen_keys = set()

    while valid_scan_count < SCAN_PER_ROUND:
        scan_number = valid_scan_count + 1

        result = check_once(scan_number)

        if not result["ok"]:
            print("[RETRY] Lỗi request, không tính lần này.")
            time.sleep(RETRY_DELAY)
            continue

        valid_scan_count += 1

        if result["has_code"]:
            key = result["key"]

            if key not in seen_keys:
                seen_keys.add(key)
                found_keys.append(key)
                print("[ADD_KEY]", key)
            else:
                print("[DUPLICATE_KEY]", key)

        if valid_scan_count < SCAN_PER_ROUND:
            time.sleep(DELAY_BETWEEN_SCAN)

    print(f"[ROUND {round_index}] VALID_SCAN_DONE:", valid_scan_count)
    print(f"[ROUND {round_index}] KEYS:", found_keys)

    send_round_report(round_index, found_keys)

    print(f"[ROUND {round_index}] DONE")
    print(f"[WAIT] {DELAY_BETWEEN_ROUND} seconds")


# =========================
# MAIN
# =========================

def main():
    print("[BOT_STARTED] Monitoring:", START_URL)
    print("[MODE] 10 valid scans -> 1 Telegram report -> wait 5 minutes")

    round_index = 1

    while True:
        run_round(round_index)
        round_index += 1
        time.sleep(DELAY_BETWEEN_ROUND)


if __name__ == "__main__":
    main()