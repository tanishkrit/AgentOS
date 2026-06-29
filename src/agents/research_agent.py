"""
Research Agent — Information Retrieval and Data Synthesis

Uses web scraping (requests + BeautifulSoup) and DuckDuckGo search
to gather information relevant to a task.
Does NOT use LLM API — works with deterministic HTTP requests,
HTML parsing, and structured data extraction.
"""

import logging
import re
from src.agents.base_agent import BaseAgent
from src.tools.browser import BrowserTool
from src.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    """
    Gathers information from the web and local files.

    Capabilities:
    - Open URLs and extract page content (via HTTP, no browser needed)
    - Search for information using DuckDuckGo
    - Parse and structure raw data
    - Extract emails and phone numbers via regex
    - Save findings to the blackboard for other agents
    """

    def execute(
        self,
        task_description: str,
        parameters: dict,
        dependency_data: dict,
    ) -> dict:
        """
        Execute a research task.

        Expected parameters:
            - urls (list[str]): URLs to visit and extract content from
            - search_query (str): A search query to perform
            - output_file (str): Optional path to save results
        """
        self.logger.info(f"Starting research: {task_description}")
        self._emit_log(f"🔍 Starting research: {task_description}")

        # Robustly extract URLs
        urls = parameters.get("urls", [])
        if not urls and "url" in parameters:
            urls = [parameters["url"]]
        elif isinstance(urls, str):
            urls = [urls]

        # Robustly extract search query
        search_query = parameters.get("search_query", "")
        if not search_query:
            search_query = parameters.get("query", parameters.get("search", parameters.get("q", "")))

        # Fallback: if both are empty, use raw_goal or task description
        if not urls and not search_query:
            search_query = parameters.get("raw_goal", task_description)

        results = []
        browser_tool = BrowserTool()

        try:
            # ── Visit specific URLs and extract content ──────────────
            for url in urls:
                if not url:
                    continue
                self.logger.info(f"Visiting: {url}")
                self._emit_log(f"🌐 Fetching URL: {url}")
                try:
                    page_content = browser_tool.get_page_content(url)
                    results.append({
                        "source": url,
                        "content": page_content[:5000],
                        "type": "url_extract",
                    })
                except Exception as visit_err:
                    self.logger.warning(f"Failed to visit URL {url}: {visit_err}")
                    self._emit_log(f"⚠️ Failed to fetch: {url}")

            # ── Perform web search if a query is provided ────────────
            if search_query:
                self.logger.info(f"Searching: {search_query}")
                self._emit_log(f"🔍 Searching Google & DuckDuckGo: {search_query}")

                # Dynamically set max_pages based on how many items are requested
                raw_goal = parameters.get("raw_goal", task_description).lower()
                max_pages = 5
                if "100" in raw_goal or "hundred" in raw_goal:
                    max_pages = 15
                elif "50" in raw_goal:
                    max_pages = 10

                search_data = browser_tool.search_and_scrape(
                    search_query, max_pages=max_pages
                )

                # Add search results metadata
                for sr in search_data.get("search_results", []):
                    results.append(sr)

                # Add scraped page contents
                for page in search_data.get("scraped_pages", []):
                    results.append(page)

                self._emit_log(
                    f"📄 Found {len(search_data.get('search_results', []))} results, "
                    f"scraped {len(search_data.get('scraped_pages', []))} pages"
                )

            # ── Extract emails and phone numbers via regex ───────────
            email_pattern = re.compile(
                r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            )
            # Standard phone formats: international, parentheses, dashes
            phone_pattern = re.compile(
                r'(?:\+?\d{1,3}[-.\s]?)?'
                r'\(?\d{2,4}\)?'
                r'[-.\s]?\d{3,4}'
                r'[-.\s]?\d{3,4}'
            )

            all_emails = set()
            all_phones = set()

            for res in results:
                content = res.get("content", "") or res.get("snippet", "")

                # Scan for emails
                for email in email_pattern.findall(content):
                    # Filter out image file extensions
                    if not email.lower().endswith(
                        ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.css', '.js')
                    ):
                        all_emails.add(email.lower())

                # Scan for phone numbers
                for phone in phone_pattern.findall(content):
                    cleaned_phone = phone.strip()
                    digit_count = sum(c.isdigit() for c in cleaned_phone)
                    # Keep numbers between 7 and 15 digits
                    if 7 <= digit_count <= 15:
                        all_phones.add(cleaned_phone)

            extracted = {
                "emails": sorted(list(all_emails)),
                "phones": sorted(list(all_phones)),
            }

            self._emit_log(
                f"📧 Extracted {len(all_emails)} emails, "
                f"📞 {len(all_phones)} phone numbers"
            )

            # Publish findings to the blackboard
            findings = {
                "success": True,
                "summary": (
                    f"Scraped {len(results)} sources. "
                    f"Extracted {len(all_emails)} emails and {len(all_phones)} phones."
                ),
                "data": results,
                "extracted": extracted,
            }

            # ── LLM-powered structured extraction ────────────────────
            llm = LLMClient.get_instance()
            if llm.available and results:
                self._emit_log("🤖 Using LLM to extract structured data...")
                structured_items = []

                # Determine fields to extract based on goal context
                raw_goal = parameters.get("raw_goal", task_description).lower()

                # Dynamic field detection based on user query
                fields = ["name"]
                if "phone" in raw_goal or "number" in raw_goal or "contact" in raw_goal or "mobile" in raw_goal:
                    fields.append("phone")
                if "email" in raw_goal or "e-mail" in raw_goal or "mail" in raw_goal:
                    fields.append("email")
                if "address" in raw_goal or "location" in raw_goal or "where" in raw_goal:
                    fields.append("address")

                # Fallback to standard fields if not specified
                if len(fields) <= 1:
                    if any(kw in raw_goal for kw in ["restaurant", "cafe", "food", "hotel", "turf", "shop", "store"]):
                        fields.extend(["phone", "email", "address"])
                    elif any(kw in raw_goal for kw in ["startup", "company", "business"]):
                        fields.extend(["website", "founder", "industry"])
                    else:
                        fields.extend(["url", "key_info"])

                # Prepare the items to process (only keep page scrape items for LLM)
                pages_to_process = [r for r in results if r.get("type") == "url_extract"]
                if not pages_to_process:
                    # Fallback to top search result snippets if no pages were successfully scraped
                    pages_to_process = [r for r in results if r.get("type") == "search_result"][:10]

                # Limit number of pages processed for performance
                max_extract_pages = 15 if "100" in raw_goal or "hundred" in raw_goal else 8
                pages_to_process = pages_to_process[:max_extract_pages]
                total_pages = len(pages_to_process)

                for idx, item in enumerate(pages_to_process):
                    content = item.get("content", "") or item.get("snippet", "")
                    if not content or len(content) < 50:
                        continue

                    source_name = item.get("title", item.get("source", "Web page"))
                    self._emit_log(f"🧠 Extracting from page {idx+1}/{total_pages}: {source_name[:35]}...")

                    try:
                        extracted_list = llm.extract_structured_list(
                            raw_text=content,
                            fields=fields,
                            context=f"User is looking for: {raw_goal}",
                        )
                        if extracted_list:
                            for extracted_data in extracted_list:
                                if not isinstance(extracted_data, dict):
                                    continue

                                # Validate/normalize keys
                                normalized_item = {}
                                has_name = False
                                for f in fields:
                                    val = extracted_data.get(f)
                                    if val is None:
                                        for key, value in extracted_data.items():
                                            if f in key.lower():
                                                val = value
                                                break
                                    normalized_item[f] = val
                                    if f == "name" and val:
                                        has_name = True

                                if has_name:
                                    normalized_item["source_url"] = item.get("source", item.get("url", ""))
                                    structured_items.append(normalized_item)
                    except Exception as llm_err:
                        self.logger.warning(f"LLM list extraction failed for a page: {llm_err}")

                # Deduplicate structured items by name
                if structured_items:
                    seen_names = set()
                    unique_structured_items = []
                    for s_item in structured_items:
                        name = s_item.get("name", "")
                        if not name:
                            continue
                        normalized_name = re.sub(r'[^a-z0-9]', '', name.lower())
                        if normalized_name not in seen_names:
                            seen_names.add(normalized_name)
                            unique_structured_items.append(s_item)

                    structured_items = unique_structured_items
                    findings["structured_data"] = structured_items
                    findings["structured_fields"] = fields
                    self._emit_log(
                        f"✅ LLM extracted structured data for {len(structured_items)} unique items"
                    )

            self.publish("research_findings", findings)

            return findings

        except Exception as e:
            self.logger.error(f"Research failed: {e}")
            self._emit_log(f"❌ Research failed: {e}")
            return {
                "success": False,
                "summary": f"Research failed: {e}",
                "data": [],
            }

        finally:
            browser_tool.close()
