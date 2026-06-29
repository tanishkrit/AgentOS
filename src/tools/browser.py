"""
Browser Tool — Lightweight Web Scraping via requests + BeautifulSoup

Provides web search and content extraction WITHOUT launching a browser.
Uses HTTP requests with proper User-Agent headers and BeautifulSoup
for HTML parsing. No Playwright, no browser binaries needed.

For actual browser control (opening Brave, Chrome, etc.), see the
DesktopTool which uses PyAutoGUI + subprocess.
"""

import logging
import re
import time
from urllib.parse import urlparse, parse_qs, quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

# Rotating User-Agent pool — reduces fingerprinting and CAPTCHA triggers
import random as _random

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 OPR/108.0.0.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

def _random_ua() -> str:
    return _random.choice(_USER_AGENTS)

REQUEST_TIMEOUT = 15  # seconds
MAX_RETRIES = 2

# Phrases that indicate a CAPTCHA / bot-block page
_CAPTCHA_SIGNATURES = [
    "captcha", "i'm not a robot", "unusual traffic",
    "automated queries", "not a robot", "verify you are human",
    "hcaptcha", "recaptcha", "cf-challenge", "challenge-platform",
    "checking your browser", "access denied", "bot detection",
    "please verify", "human verification",
]


class BrowserTool:
    """
    Lightweight web scraping tool using requests + BeautifulSoup.

    No browser binaries required. Works out of the box.
    """

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": _random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        })

    # ── CAPTCHA Detection & Solving ───────────────────────────

    @staticmethod
    def _is_captcha_page(html_text: str) -> bool:
        """Return True if the HTML looks like a CAPTCHA / bot-block page."""
        lower = html_text.lower()
        score = sum(1 for sig in _CAPTCHA_SIGNATURES if sig in lower)
        # 2+ matches is a strong indicator
        return score >= 2

    def _try_solve_captcha_checkbox(self, timeout: float = 12.0) -> bool:
        """
        Attempt to solve a simple reCAPTCHA v2 checkbox ("I'm not a robot")
        by using vision (OCR) to locate the checkbox text and clicking it.

        Returns True if the click was performed, False otherwise.
        This does NOT guarantee the CAPTCHA is solved (image challenges
        may follow), but handles the simple checkbox case.
        """
        try:
            import pyautogui
            from src.vision.ocr import OCR

            ocr = OCR()
            start = time.time()
            logger.info("Attempting to solve CAPTCHA checkbox via vision...")

            while time.time() - start < timeout:
                # Look for the checkbox text
                for target in ["not a robot", "I'm not", "robot"]:
                    coords = ocr.find_text_on_screen(target)
                    if coords:
                        x, y = coords
                        # Click slightly to the left of the text (the checkbox)
                        click_x = max(x - 30, 10)
                        click_y = y
                        logger.info(
                            f"CAPTCHA checkbox found at ({x}, {y}), "
                            f"clicking at ({click_x}, {click_y})"
                        )
                        pyautogui.click(click_x, click_y)
                        time.sleep(3)  # Wait for reCAPTCHA validation

                        # Check if the page changed (CAPTCHA may be gone)
                        screen_text = ocr.extract_from_screen()
                        if "not a robot" not in screen_text.lower():
                            logger.info("CAPTCHA appears to be solved!")
                            return True
                        else:
                            logger.warning(
                                "CAPTCHA checkbox clicked but challenge may still be present."
                            )
                            return True  # We clicked it, further challenges are complex
                time.sleep(1)

            logger.warning("Could not locate CAPTCHA checkbox on screen.")
            return False

        except Exception as e:
            logger.warning(f"CAPTCHA solve attempt failed: {e}")
            return False

    def _rotate_user_agent(self) -> None:
        """Switch to a new random User-Agent for the session."""
        ua = _random_ua()
        self._session.headers["User-Agent"] = ua
        logger.debug(f"Rotated User-Agent to: {ua[:50]}...")

    def _find_browser_path(self) -> tuple[str, str]:
        """
        Locate the browser executable and return (path, window_title_keyword).
        """
        import os
        from pathlib import Path
        
        possible_browsers = [
            (r"C:\Program Files\Google\Chrome\Application\chrome.exe", "Chrome"),
            (r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe", "Chrome"),
            (r"C:\Users\kritg\AppData\Local\Google\Chrome\Application\chrome.exe", "Chrome"),
            (r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe", "Brave"),
            (r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe", "Brave"),
            (r"C:\Users\kritg\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe", "Brave"),
            (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "Edge"),
            (r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", "Edge"),
        ]
        for path, title in possible_browsers:
            if Path(path).exists():
                return path, title
        return "chrome.exe", "Chrome"

    def _focus_window_by_title(self, target_name: str) -> bool:
        import ctypes
        import time
        try:
            EnumWindows = ctypes.windll.user32.EnumWindows
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            GetWindowText = ctypes.windll.user32.GetWindowTextW
            GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
            IsWindowVisible = ctypes.windll.user32.IsWindowVisible
            SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow
            ShowWindow = ctypes.windll.user32.ShowWindow

            found_hwnd = []
            
            def foreach_window(hwnd, lParam):
                if IsWindowVisible(hwnd):
                    length = GetWindowTextLength(hwnd)
                    buff = ctypes.create_unicode_buffer(length + 1)
                    GetWindowText(hwnd, buff, length + 1)
                    title = buff.value
                    if target_name.lower() in title.lower():
                        found_hwnd.append(hwnd)
                        return False  # Stop enumeration
                return True

            EnumWindows(EnumWindowsProc(foreach_window), 0)
            
            if found_hwnd:
                hwnd = found_hwnd[0]
                ShowWindow(hwnd, 9)  # SW_RESTORE
                time.sleep(0.5)
                SetForegroundWindow(hwnd)
                time.sleep(0.5)
                return True
        except Exception as e:
            logger.warning(f"Error focusing window: {e}")
        return False

    def _safe_copy_text(self, text: str, retries: int = 5, delay: float = 0.1) -> bool:
        import time
        import pyperclip
        for i in range(retries):
            try:
                pyperclip.copy(text)
                return True
            except Exception:
                time.sleep(delay)
        return False

    def _safe_paste_text(self, retries: int = 5, delay: float = 0.1) -> str:
        import time
        import pyperclip
        for i in range(retries):
            try:
                return pyperclip.paste()
            except Exception:
                time.sleep(delay)
        return ""

    def _get_page_content_gui(self, url: str) -> str:
        """
        GUI-based web scraping fallback.
        Launches Chrome visibly, copies page source to clipboard, and parses the content.
        """
        import subprocess
        import time
        import pyautogui
        from bs4 import BeautifulSoup
        
        logger.info(f"Using visible Chrome fallback to scrape URL: {url}")
        
        browser_path, browser_title = self._find_browser_path()
        
        old_failsafe = True
        try:
            old_failsafe = pyautogui.FAILSAFE
            pyautogui.FAILSAFE = False
        except Exception:
            pass
            
        try:
            self._safe_copy_text("")
            
            # Launch Chrome visibly via webbrowser
            import webbrowser
            webbrowser.open(url)
            time.sleep(7)
            
            try:
                width, height = pyautogui.size()
                pyautogui.click(width // 2, height // 2)
                time.sleep(0.5)
            except Exception:
                pass
                
            self._focus_window_by_title(browser_title)
            time.sleep(0.5)
            
            # Open source (Ctrl+U)
            pyautogui.hotkey("ctrl", "u")
            time.sleep(4)
            
            # Copy all (Ctrl+A -> Ctrl+C)
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.5)
            pyautogui.hotkey("ctrl", "c")
            time.sleep(0.5)
            
            # Close tabs
            pyautogui.hotkey("ctrl", "w")
            time.sleep(0.8)
            pyautogui.hotkey("ctrl", "w")
            time.sleep(0.8)
            
            text_content = self._safe_paste_text()

            # ── Detect CAPTCHA in GUI-scraped content ──────────────
            if text_content and self._is_captcha_page(text_content):
                logger.warning("CAPTCHA detected in GUI page scrape. Attempting to solve...")
                pyautogui.hotkey("ctrl", "w")  # Close source tab
                time.sleep(1)
                solved = self._try_solve_captcha_checkbox(timeout=15)
                if solved:
                    time.sleep(5)
                    # Re-open source and copy
                    pyautogui.hotkey("ctrl", "u")
                    time.sleep(4)
                    pyautogui.hotkey("ctrl", "a")
                    time.sleep(0.5)
                    pyautogui.hotkey("ctrl", "c")
                    time.sleep(0.5)
                    pyautogui.hotkey("ctrl", "w")
                    time.sleep(0.8)
                    pyautogui.hotkey("ctrl", "w")
                    time.sleep(0.8)
                    text_content = self._safe_paste_text()

            if text_content:
                soup = BeautifulSoup(text_content, "lxml")
                for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                cleaned = "\n".join(lines)
                return cleaned
                
        except Exception as e:
            logger.error(f"Visible Chrome scraping failed: {e}")
        finally:
            try:
                pyautogui.FAILSAFE = old_failsafe
            except Exception:
                pass
                
        return ""

    def _google_search_gui(self, query: str, num_results: int = 100) -> list[dict]:
        """
        GUI-based Google search fallback using visible Chrome and clipboard copy.
        """
        import subprocess
        import time
        import pyautogui
        from pathlib import Path
        from bs4 import BeautifulSoup
        
        logger.info(f"Using visible Chrome to search Google: {query}")
        
        browser_path, browser_title = self._find_browser_path()
        workspace = Path(r"c:\Users\kritg\OneDrive\Desktop\Tanish\Promgrams\AI Agents\workspace")
        workspace.mkdir(parents=True, exist_ok=True)
        
        query_url = f"https://www.google.com/search?q={quote_plus(query)}&num={num_results}&hl=en"
        
        old_failsafe = True
        try:
            old_failsafe = pyautogui.FAILSAFE
            pyautogui.FAILSAFE = False
        except Exception:
            pass
            
        results = []
        try:
            self._safe_copy_text("")
            
            # Launch Chrome visibly via webbrowser
            import webbrowser
            webbrowser.open(query_url)
            time.sleep(8)
            
            try:
                width, height = pyautogui.size()
                pyautogui.click(width // 2, height // 2)
                time.sleep(0.5)
            except Exception:
                pass
                
            self._focus_window_by_title(browser_title)
            time.sleep(0.5)
            
            # Open source (Ctrl+U)
            pyautogui.hotkey("ctrl", "u")
            time.sleep(4)
            
            # Copy all (Ctrl+A -> Ctrl+C)
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.5)
            pyautogui.hotkey("ctrl", "c")
            time.sleep(0.5)
            
            # Close tabs
            pyautogui.hotkey("ctrl", "w")
            time.sleep(0.8)
            pyautogui.hotkey("ctrl", "w")
            time.sleep(0.8)
            
            text_content = self._safe_paste_text()

            # ── Detect CAPTCHA in the GUI-scraped content ──────────
            if text_content and self._is_captcha_page(text_content):
                logger.warning("CAPTCHA detected in visible browser Google search. Attempting to solve...")
                # Close the source view tab first — go back to actual page
                pyautogui.hotkey("ctrl", "w")
                time.sleep(1)

                # Try to click the "I'm not a robot" checkbox
                solved = self._try_solve_captcha_checkbox(timeout=15)
                if solved:
                    logger.info("CAPTCHA checkbox clicked. Waiting for page reload...")
                    time.sleep(5)  # Wait for Google to validate and reload

                    # Re-open source and copy
                    pyautogui.hotkey("ctrl", "u")
                    time.sleep(4)
                    pyautogui.hotkey("ctrl", "a")
                    time.sleep(0.5)
                    pyautogui.hotkey("ctrl", "c")
                    time.sleep(0.5)
                    pyautogui.hotkey("ctrl", "w")
                    time.sleep(0.8)
                    pyautogui.hotkey("ctrl", "w")
                    time.sleep(0.8)
                    text_content = self._safe_paste_text()
                else:
                    logger.warning("Could not solve CAPTCHA in visible browser. Closing tabs.")
                    pyautogui.hotkey("ctrl", "w")
                    time.sleep(0.5)
                    return results

            if text_content:
                try:
                    search_test_file = workspace / "search_test.html"
                    search_test_file.write_text(text_content, encoding="utf-8", errors="ignore")
                except Exception as save_err:
                    logger.warning(f"Failed to copy search results to search_test.html: {save_err}")
                
                soup = BeautifulSoup(text_content, "lxml")
                h3_elements = soup.find_all("h3")
                for h3 in h3_elements:
                    parent_a = h3.find_parent("a")
                    if not parent_a:
                        continue
                    href = parent_a.get("href", "")
                    
                    if href.startswith("/url?"):
                        try:
                            parsed = urlparse(href)
                            qs = parse_qs(parsed.query)
                            if "q" in qs:
                                href = qs["q"][0]
                        except Exception:
                            pass
                            
                    if not href.startswith("http") or "google.com" in href:
                        continue
                        
                    title = h3.get_text(strip=True)
                    if not title:
                        continue
                        
                    snippet = ""
                    container = h3.find_parent(class_="g")
                    if container:
                        desc_div = container.find(class_=lambda c: c and any(cls in c for cls in ['VwiC3b', 'yDqR2', 'IsZvec', 's3xxgc']))
                        if desc_div:
                            snippet = desc_div.get_text(strip=True)
                            
                    if any(r["url"] == href for r in results):
                        continue
                        
                    results.append({
                        "title": title,
                        "url": href,
                        "snippet": snippet,
                        "type": "search_result",
                    })
                    
                logger.info(f"Visible Chrome search returned {len(results)} results.")
                
        except Exception as e:
            logger.error(f"Visible Chrome search failed: {e}")
        finally:
            try:
                pyautogui.FAILSAFE = old_failsafe
            except Exception:
                pass
                
        return results

    def get_page_content(self, url: str) -> str:
        """
        Fetch a URL and return the visible text content.

        Retries on failure with User-Agent rotation.
        Detects CAPTCHA pages and falls back to GUI scraping.
        """
        for attempt in range(MAX_RETRIES + 1):
            try:
                # Rotate UA on retries to avoid fingerprint blocks
                if attempt > 0:
                    self._rotate_user_agent()
                    time.sleep(_random.uniform(1.0, 3.0))  # Random delay

                logger.info(f"Fetching URL (attempt {attempt + 1}): {url}")
                resp = self._session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
                resp.raise_for_status()

                # ── CAPTCHA detection ────────────────────────────────
                if self._is_captcha_page(resp.text):
                    logger.warning(
                        f"CAPTCHA detected on {url} (attempt {attempt + 1}). "
                        f"Rotating UA and retrying..."
                    )
                    self._rotate_user_agent()
                    if attempt < MAX_RETRIES:
                        time.sleep(_random.uniform(2.0, 5.0))
                        continue
                    # Last attempt: try GUI fallback
                    logger.info("Falling back to GUI scraping after CAPTCHA.")
                    gui_content = self._get_page_content_gui(url)
                    if gui_content:
                        return gui_content
                    return "[CAPTCHA blocked - could not retrieve content]"

                soup = BeautifulSoup(resp.text, "lxml")

                # Remove script, style, nav, footer elements
                for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                    tag.decompose()

                text = soup.get_text(separator="\n", strip=True)

                # Clean up excessive whitespace
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                cleaned = "\n".join(lines)

                # Check if page is blank or blocked (e.g. cloudflare)
                if len(cleaned) < 500 or any(kw in cleaned.lower() for kw in ["cloudflare", "captcha", "access denied", "enable javascript"]):
                    logger.warning(f"Content from {url} seems blocked/short ({len(cleaned)} chars). Trying GUI scraping fallback.")
                    gui_cleaned = self._get_page_content_gui(url)
                    if gui_cleaned and len(gui_cleaned) > len(cleaned):
                        return gui_cleaned

                logger.info(f"Extracted {len(cleaned)} chars from {url}")
                return cleaned

            except requests.RequestException as e:
                logger.warning(f"Request failed for {url} (attempt {attempt + 1}): {e}")
                if attempt < MAX_RETRIES:
                    self._rotate_user_agent()
                    time.sleep(_random.uniform(1.0, 3.0))
                else:
                    # Try GUI scraping fallback on failure
                    gui_cleaned = self._get_page_content_gui(url)
                    if gui_cleaned:
                        return gui_cleaned
                    return f"[Error fetching {url}: {e}]"

        return ""

    def google_search(self, query: str, num_results: int = 100) -> list[dict]:
        """
        Perform a web search via Google Search and return structured results.

        Includes CAPTCHA detection — if a CAPTCHA is encountered, immediately
        aborts and returns empty so the caller can fall back to other engines.
        """
        results = []
        encoded_query = quote_plus(query)
        search_url = f"https://www.google.com/search?q={encoded_query}&num={num_results}&hl=en"

        # Rotate UA before each Google attempt
        self._rotate_user_agent()
        # Add a small random delay to appear more human
        time.sleep(_random.uniform(0.5, 2.0))

        try:
            logger.info(f"Searching Google: {query} (requesting {num_results} results)")
            resp = self._session.get(search_url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()

            # ── CAPTCHA detection: abort early ──────────────────
            if self._is_captcha_page(resp.text):
                logger.warning(
                    "Google CAPTCHA detected in HTTP response. "
                    "Skipping Google and falling back to other engines."
                )
                return []  # Return empty — caller will try DDG/Yahoo

            soup = BeautifulSoup(resp.text, "lxml")

            # Google Search titles are in <h3> tags inside parent <a> tags
            h3_elements = soup.find_all("h3")
            for h3 in h3_elements:
                parent_a = h3.find_parent("a")
                if not parent_a:
                    continue

                href = parent_a.get("href", "")

                # Resolve Google search redirect links
                if href.startswith("/url?"):
                    try:
                        parsed = urlparse(href)
                        qs = parse_qs(parsed.query)
                        if "q" in qs:
                            href = qs["q"][0]
                    except Exception:
                        pass

                # Skip non-http or google-specific links
                if not href.startswith("http") or "google.com" in href:
                    continue

                title = h3.get_text(strip=True)
                if not title:
                    continue

                # Try to extract a snippet by looking for description containers
                snippet = ""
                container = h3.find_parent(class_="g")
                if container:
                    desc_div = container.find(class_=lambda c: c and any(cls in c for cls in ['VwiC3b', 'yDqR2', 'IsZvec', 's3xxgc']))
                    if desc_div:
                        snippet = desc_div.get_text(strip=True)
                    else:
                        # Fallback description extraction
                        sibling_texts = []
                        for sibling in h3.find_parent().next_siblings:
                            if sibling and hasattr(sibling, 'get_text'):
                                text = sibling.get_text(strip=True)
                                if text:
                                    sibling_texts.append(text)
                        if sibling_texts:
                            snippet = " ".join(sibling_texts)[:200]

                # Deduplicate links
                if any(r["url"] == href for r in results):
                    continue

                results.append({
                    "url": href,
                    "title": title,
                    "snippet": snippet,
                    "type": "search_result",
                })

            logger.info(f"Found {len(results)} search results on Google for: {query}")

        except Exception as e:
            logger.warning(f"Google search failed: {e}")

        # Try GUI fallback only if we got very few results AND no CAPTCHA was detected via HTTP
        if len(results) < 3:
            logger.warning("HTTP Google search returned fewer than 3 results. Trying GUI Google search fallback.")
            gui_results = self._google_search_gui(query, num_results)
            if gui_results:
                return gui_results

        return results

    def ddg_search(self, query: str) -> list[dict]:
        """
        Perform a web search via DuckDuckGo HTML and return structured results.

        No API key needed. Returns list of {title, url, snippet, type} dicts.
        """
        results = []
        encoded_query = quote_plus(query)
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        try:
            logger.info(f"Searching DuckDuckGo: {query}")
            resp = self._session.get(search_url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")

            # DuckDuckGo HTML version result structure
            result_links = soup.select(".result__a")
            result_snippets = soup.select(".result__snippet")

            for i, link in enumerate(result_links[:15]):  # Top 15 results
                title = link.get_text(strip=True)
                href = link.get("href", "")

                # Resolve DuckDuckGo redirect URLs
                if href.startswith("/l/?") or "uddg=" in href:
                    try:
                        parsed = urlparse(href)
                        qs = parse_qs(parsed.query)
                        if "uddg" in qs:
                            href = qs["uddg"][0]
                    except Exception:
                        pass

                # Skip non-http links
                if not href.startswith("http"):
                    continue

                snippet = ""
                if i < len(result_snippets):
                    snippet = result_snippets[i].get_text(strip=True)

                results.append({
                    "title": title,
                    "url": href,
                    "snippet": snippet,
                    "type": "search_result",
                })

            logger.info(f"Found {len(results)} search results for DuckDuckGo: {query}")

        except requests.RequestException as e:
            logger.error(f"DuckDuckGo search failed: {e}")

        return results

    def yahoo_search(self, query: str, num_results: int = 100) -> list[dict]:
        """
        Perform a web search via Yahoo Search and return structured results.
        Uses HTTP requests and extracts target URLs from Yahoo redirects.
        """
        from urllib.parse import unquote
        results = []
        encoded_query = quote_plus(query)
        
        # Yahoo has 10 results per page, b=1, 11, 21, etc.
        pages = (num_results + 9) // 10
        for page in range(pages):
            offset = page * 10 + 1
            search_url = f"https://search.yahoo.com/search?q={encoded_query}&b={offset}"
            try:
                logger.info(f"Searching Yahoo: {query} (page {page + 1}, offset {offset})")
                resp = self._session.get(search_url, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                
                soup = BeautifulSoup(resp.text, "lxml")
                
                # Yahoo search results are inside <a> tags containing r.search.yahoo.com
                for a in soup.find_all("a"):
                    href = a.get("href", "")
                    text = a.get_text(strip=True)
                    if "r.search.yahoo.com" in href:
                        # Extract target destination
                        match = re.search(r'/RU=([^/]+)', href)
                        if match:
                            decoded_url = unquote(match.group(1))
                            # Filter out Yahoo-internal links
                            if decoded_url and "yahoo.com" not in decoded_url and "yimg.com" not in decoded_url and "uservoice.com" not in decoded_url:
                                if any(r["url"] == decoded_url for r in results):
                                    continue
                                results.append({
                                    "title": text if text else "Yahoo Result",
                                    "url": decoded_url,
                                    "snippet": "",
                                    "type": "search_result",
                                })
            except Exception as e:
                logger.warning(f"Yahoo search page {page+1} failed: {e}")
                break
                
        logger.info(f"Yahoo search returned {len(results)} results for: {query}")
        return results

    def search(self, query: str) -> list[dict]:
        """
        Perform a web search using multiple engines.
        Priority order: DuckDuckGo first (no CAPTCHAs), then Yahoo, then Google.
        Deduplicates results by URL.
        """
        results = []
        urls_seen = set()

        # 1. DuckDuckGo FIRST — no CAPTCHAs, always works
        try:
            ddg_res = self.ddg_search(query)
            for r in ddg_res:
                url = r["url"]
                if url not in urls_seen:
                    urls_seen.add(url)
                    results.append(r)
            logger.info(f"DuckDuckGo returned {len(ddg_res)} results.")
        except Exception as e:
            logger.warning(f"DuckDuckGo search error: {e}")

        # 2. Yahoo Search (no CAPTCHAs for normal queries)
        try:
            yahoo_res = self.yahoo_search(query, num_results=100)
            for r in yahoo_res:
                url = r["url"]
                if url not in urls_seen:
                    urls_seen.add(url)
                    results.append(r)
            logger.info(f"Yahoo returned {len(yahoo_res)} results.")
        except Exception as e:
            logger.warning(f"Yahoo search error: {e}")

        # 3. Google Search LAST — most likely to CAPTCHA-block
        #    Only try if we still have fewer than 10 unique results
        if len(results) < 10:
            time.sleep(_random.uniform(1.0, 3.0))  # Delay before hitting Google
            try:
                google_res = self.google_search(query, num_results=100)
                for r in google_res:
                    url = r["url"]
                    if url not in urls_seen:
                        urls_seen.add(url)
                        results.append(r)
                logger.info(f"Google returned {len(google_res)} results.")
            except Exception as e:
                logger.warning(f"Google search error: {e}")

        logger.info(f"Merged search returned {len(results)} total unique results.")
        return results

    def search_and_scrape(self, query: str, max_pages: int = 3) -> dict:
        """
        Search Google, Yahoo & DuckDuckGo, then visit and scrape the top results.

        Returns a dict with search results and scraped page contents.
        """
        search_results = self.search(query)

        scraped_pages = []
        visited = 0

        for result in search_results:
            if visited >= max_pages:
                break

            url = result.get("url", "")
            if not url or not url.startswith("http"):
                continue

            logger.info(f"Scraping search result: {url}")
            try:
                content = self.get_page_content(url)
                if content and not content.startswith("[Error"):
                    scraped_pages.append({
                        "source": url,
                        "title": result.get("title", ""),
                        "content": content[:5000],  # First 5000 chars
                        "type": "url_extract",
                    })
                    visited += 1
            except Exception as e:
                logger.warning(f"Failed to scrape {url}: {e}")

        return {
            "search_results": search_results,
            "scraped_pages": scraped_pages,
        }

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()
        logger.info("Browser tool session closed.")
