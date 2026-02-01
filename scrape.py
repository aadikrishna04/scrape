"""
Scrape - Generate APIs for any website.

Phase 1: Planning - LLM proposes API interface based on goal (no DOM needed)
Phase 2: Exploration - Capture network requests (manual or automated)
Phase 3: Implementation - Map proposed API to discovered endpoints

Usage:
    python scrape.py "get all videos in playlist" https://youtube.com/playlist?list=...
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional
from urllib.parse import urlparse, parse_qs

from openai import OpenAI


# =============================================================================
# PHASE 1: PLANNING
# =============================================================================

def plan_api(goal: str, url: str, client: OpenAI) -> dict:
    """
    Plan the API interface based on goal alone - no DOM or network capture.
    Returns a proposed API spec with methods and schemas.
    """

    # Parse URL for context
    parsed = urlparse(url)
    domain = parsed.netloc
    path = parsed.path

    prompt = f"""You are designing an API interface for a web scraping task.

GOAL: {goal}
WEBSITE: {domain}
URL PATTERN: {url}

Based on the goal and URL, propose a clean API interface. Think about:
- What methods would a developer want?
- What parameters make sense (IDs, filters, pagination)?
- What data should each method return?

Respond with a JSON object:
{{
    "api_name": "Short descriptive name",
    "description": "What this API does",
    "methods": [
        {{
            "name": "method_name",
            "description": "What this method does",
            "http_method": "GET",
            "parameters": [
                {{
                    "name": "param_name",
                    "type": "string|integer|boolean",
                    "required": true/false,
                    "description": "What this param does",
                    "default": null
                }}
            ],
            "returns": {{
                "type": "object|array",
                "description": "What is returned",
                "schema": {{
                    "field_name": "type (e.g., string, integer)",
                    ...
                }},
                "sample": {{ ... }}
            }}
        }}
    ]
}}

Be practical - design what a developer would actually want to use.
For YouTube playlists, you'd want to get videos with title, duration, video_id.
For earnings calendars, you'd want companies with name, symbol, report_date.

Output ONLY valid JSON."""

    print("\n" + "="*70)
    print("PHASE 1: PLANNING")
    print("="*70)
    print(f"Goal: {goal}")
    print(f"URL: {url}")
    print("\nProposing API interface...")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are an API designer. Create clean, practical API interfaces. Output only valid JSON."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    content = response.choices[0].message.content.strip()

    # Clean markdown
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]

    api_spec = json.loads(content)
    return api_spec


def display_api_plan(api_spec: dict):
    """Display the proposed API in a readable format."""

    print("\n" + "="*70)
    print(f"PROPOSED API: {api_spec.get('api_name', 'API')}")
    print("="*70)
    print(f"\n{api_spec.get('description', '')}\n")

    for i, method in enumerate(api_spec.get('methods', []), 1):
        print(f"{i}. {method.get('http_method', 'GET')} {method.get('name', 'unknown')}()")
        print(f"   {method.get('description', '')}")

        params = method.get('parameters', [])
        if params:
            print("\n   Parameters:")
            for p in params:
                req = "*" if p.get('required') else ""
                default = f" (default: {p.get('default')})" if p.get('default') else ""
                print(f"   - {p.get('name')}{req}: {p.get('type')}{default}")
                print(f"     {p.get('description', '')}")

        returns = method.get('returns', {})
        if returns:
            print(f"\n   Returns: {returns.get('type', 'object')}")
            sample = returns.get('sample', {})
            if sample:
                print(f"   Sample: {json.dumps(sample, indent=2)[:200]}")

        print()


# =============================================================================
# PHASE 2: EXPLORATION (Network Capture)
# =============================================================================

@dataclass
class CapturedRequest:
    method: str
    url: str
    base_url: str
    query_params: dict
    headers: dict
    post_data: Optional[str]
    status: int
    response_body: Optional[str]
    response_json: Optional[dict]


async def explore_with_agent(url: str, goal: str, client: OpenAI, headless: bool = False) -> tuple[list[CapturedRequest], Optional[str]]:
    """
    Use an AI agent to actively explore the site with the goal in mind.
    The agent decides what actions to take and captures relevant API calls.
    """
    from playwright.async_api import async_playwright

    captured = []
    html_content = None

    print("\n" + "="*70)
    print("PHASE 2: AGENT EXPLORATION")
    print("="*70)
    print(f"Goal: {goal}")
    print(f"URL: {url}")
    print("\nAgent is exploring the site...\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = await context.new_page()

        # Capture responses
        async def capture_response(response):
            try:
                resp_url = response.url
                content_type = response.headers.get('content-type', '')

                api_indicators = ['/api/', 'graphql', '.json', 'youtubei', 'ajax',
                                  'api.', '/v1/', '/v2/', '/v3/', 'spclient', 'wg/',
                                  'pathfinder', 'query', 'browse']

                if not any(x in content_type for x in ['json', 'xml']):
                    if not any(x in resp_url.lower() for x in api_indicators):
                        return

                body = None
                body_json = None
                try:
                    body = await response.text()
                    if body:
                        body_json = json.loads(body)
                except:
                    pass

                if body_json:  # Only capture if it has JSON
                    parsed = urlparse(resp_url)
                    req = CapturedRequest(
                        method=response.request.method,
                        url=resp_url,
                        base_url=f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
                        query_params=dict(parse_qs(parsed.query)),
                        headers=dict(response.request.headers),
                        post_data=response.request.post_data,
                        status=response.status,
                        response_body=body[:50000] if body else None,
                        response_json=body_json,
                    )
                    captured.append(req)
                    print(f"  📡 {req.method} {req.base_url[:70]}...")
            except:
                pass

        page.on("response", capture_response)

        # Navigate to the page
        print(f"  → Navigating to {url[:60]}...")
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        await asyncio.sleep(2)

        # Force initial scrolls to load lazy content (especially for lists/playlists)
        print("  Scrolling to load content...")
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(0.8)
        await page.evaluate("window.scrollTo(0, 0)")  # Back to top
        await asyncio.sleep(1)

        # Agent exploration loop
        for step in range(6):
            print(f"\n  Step {step + 1}/8:")

            # Get page state
            try:
                page_info = await page.evaluate('''() => {
                    const getText = (el) => (el.textContent || '').trim().substring(0, 100);
                    const elements = [];

                    document.querySelectorAll('button, a, [role="button"], input, select, [onclick]').forEach((el, i) => {
                        if (i > 30) return;
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0 && rect.top < 800) {
                            elements.push({
                                tag: el.tagName.toLowerCase(),
                                text: getText(el),
                                href: el.href || null,
                                type: el.type || null,
                                ariaLabel: el.getAttribute('aria-label') || null,
                            });
                        }
                    });

                    return {
                        url: location.href,
                        title: document.title,
                        text: document.body.innerText.substring(0, 2000),
                        elements: elements,
                    };
                }''')
            except:
                break

            # Ask agent what to do
            action_prompt = f"""You are exploring a website to find data for this goal: {goal}

Current page: {page_info['url']}
Title: {page_info['title']}

Visible text (excerpt):
{page_info['text'][:1500]}

Interactive elements:
{json.dumps(page_info['elements'][:20], indent=2)}

API calls captured so far: {len(captured)}
Current step: {step + 1}/8

IMPORTANT RULES:
1. For lists (playlists, search results, feeds) - ALWAYS scroll at least 3 times to load more items
2. Don't say "done" just because you see SOME data - make sure you've loaded the FULL list
3. For Spotify playlists - scroll to load all tracks before stopping
4. For any paginated content - scroll multiple times

What action should we take?
- "scroll" - to load more content (DO THIS FIRST for any list/feed)
- "click" - to interact with an element
- "wait" - to let content load
- "done" - ONLY when you've scrolled enough and loaded all the data

Respond with JSON:
{{"action": "done|click|scroll|wait", "target": "text of element to click if clicking", "reason": "why"}}"""

            try:
                action_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You explore websites to find data. Output only JSON."},
                        {"role": "user", "content": action_prompt}
                    ],
                    temperature=0.1,
                    max_tokens=200,
                )
                action_text = action_response.choices[0].message.content.strip()
                if "```" in action_text:
                    action_text = action_text.split("```")[1].replace("json", "").strip()
                action = json.loads(action_text)
            except:
                action = {"action": "scroll", "reason": "fallback"}

            print(f"    Action: {action.get('action')} - {action.get('reason', '')[:50]}")

            # Don't allow "done" on first 2 steps - force more exploration
            if action.get("action") == "done":
                if step < 2:
                    print("    → Too early to stop, scrolling more...")
                    action = {"action": "scroll", "reason": "need more exploration"}
                else:
                    print("    ✓ Agent found the data")
                    break
            elif action.get("action") == "click":
                target = action.get("target", "")
                try:
                    # Try clicking by text
                    await page.get_by_text(target, exact=False).first.click(timeout=3000)
                    await asyncio.sleep(2)
                except:
                    try:
                        await page.get_by_role("button", name=target).first.click(timeout=2000)
                        await asyncio.sleep(2)
                    except:
                        print(f"    Could not click: {target[:30]}")
            elif action.get("action") == "scroll":
                await page.evaluate("window.scrollBy(0, 600)")
                await asyncio.sleep(1)
            elif action.get("action") == "wait":
                await asyncio.sleep(3)

        # Get final HTML
        try:
            html_content = await page.content()
        except:
            pass

        await browser.close()

    print(f"\n  Captured {len(captured)} API requests")
    return captured, html_content


async def explore_with_browser(url: str, headless: bool = False) -> tuple[list[CapturedRequest], Optional[str]]:
    """
    Open browser and capture network requests.
    User navigates manually, or we can auto-scroll.
    """
    from playwright.async_api import async_playwright

    captured = []
    browser_closed = False

    print("\n" + "="*70)
    print("PHASE 2: MANUAL EXPLORATION")
    print("="*70)
    print(f"\nOpening browser to capture network requests...")
    print("Navigate the page to load the data you want, then close the browser.\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        def handle_response_sync(response):
            """Sync wrapper that schedules async work."""
            if browser_closed:
                return
            asyncio.create_task(handle_response_async(response))

        async def handle_response_async(response):
            """Async handler for responses."""
            if browser_closed:
                return
            try:
                resp_url = response.url
                content_type = response.headers.get('content-type', '')

                # Only capture API-like responses
                api_indicators = ['/api/', 'graphql', '.json', 'youtubei', 'ajax',
                                  'api.', '/v1/', '/v2/', '/v3/', 'spclient', 'wg/']
                if not any(x in content_type for x in ['json', 'xml']):
                    if not any(x in resp_url.lower() for x in api_indicators):
                        return

                body = None
                body_json = None
                try:
                    body = await response.text()
                    if body:
                        body_json = json.loads(body)
                except:
                    pass

                parsed = urlparse(resp_url)

                req = CapturedRequest(
                    method=response.request.method,
                    url=resp_url,
                    base_url=f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
                    query_params=dict(parse_qs(parsed.query)),
                    headers=dict(response.request.headers),
                    post_data=response.request.post_data,
                    status=response.status,
                    response_body=body[:50000] if body else None,
                    response_json=body_json,
                )
                captured.append(req)
                print(f"  Captured: {req.method} {req.base_url[:60]}...")

            except Exception:
                pass

        page.on("response", handle_response_sync)

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            print(f"  Warning: Initial load issue: {e}")

        # Auto-scroll to trigger lazy loading
        print("\nAuto-scrolling to load more content...")
        for _ in range(3):
            try:
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(1)
            except:
                break

        print("\nClose the browser window when done, or press Enter here to continue...")

        # Wait for page close or user input
        page_closed = asyncio.Event()

        def on_page_close():
            page_closed.set()

        page.on("close", lambda: on_page_close())
        context.on("close", lambda: on_page_close())

        # Also listen for Enter key in terminal
        async def wait_for_input():
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, input)
            page_closed.set()

        input_task = asyncio.create_task(wait_for_input())

        try:
            await asyncio.wait_for(page_closed.wait(), timeout=120)
        except asyncio.TimeoutError:
            print("\nTimeout reached, continuing...")

        input_task.cancel()
        browser_closed = True

        # Capture the page HTML for fallback scraping
        html_content = None
        try:
            html_content = await page.content()
        except:
            pass

        # Give pending tasks a moment to complete
        await asyncio.sleep(0.3)

        try:
            await browser.close()
        except:
            pass

    print(f"\nCaptured {len(captured)} API requests")
    return captured, html_content


def explore_from_extension_capture(capture_file: str) -> list[CapturedRequest]:
    """Load captured requests from the browser extension."""

    with open(capture_file) as f:
        data = json.load(f)

    captured = []
    for req in data.get('requests', []):
        url = req.get('url', '')
        parsed = urlparse(url)

        body_json = None
        body = req.get('responseBody')
        if body:
            try:
                body_json = json.loads(body)
            except:
                pass

        captured.append(CapturedRequest(
            method=req.get('method', 'GET'),
            url=url,
            base_url=f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
            query_params=dict(parse_qs(parsed.query)),
            headers=req.get('requestHeaders', {}),
            post_data=req.get('postData'),
            status=req.get('status', 0),
            response_body=body,
            response_json=body_json,
        ))

    return captured


# =============================================================================
# PHASE 3: IMPLEMENTATION
# =============================================================================

def analyze_captured_requests(requests: list[CapturedRequest], target_url: str) -> tuple[list[dict], Optional[str]]:
    """
    Analyze captured requests to find the relevant API endpoints.
    Returns (api_requests, html_content) - html_content is set if no APIs found.
    """

    # Extract target domain and base domain
    target_parsed = urlparse(target_url)
    target_domain = target_parsed.netloc.lower().replace('www.', '')

    # Extract base domain (e.g., "spotify.com" from "open.spotify.com")
    domain_parts = target_domain.split('.')
    if len(domain_parts) >= 2:
        base_domain = '.'.join(domain_parts[-2:])  # e.g., "spotify.com"
    else:
        base_domain = target_domain

    analyzed = []
    html_content = None

    # Important headers to preserve
    important_headers = [
        'user-agent', 'accept', 'accept-language', 'accept-encoding',
        'referer', 'origin', 'x-requested-with', 'content-type',
        'authorization', 'cookie', 'x-api-key', 'x-csrf-token'
    ]

    for req in requests:
        if req.status < 200 or req.status >= 400:
            continue

        # Filter to only requests from the target domain (or its subdomains/API domains)
        req_domain = urlparse(req.url).netloc.lower().replace('www.', '')

        # Check if request is related to target domain
        # Match on base domain to catch api-partner.spotify.com, spclient.wg.spotify.com, etc.
        domain_match = (
            base_domain in req_domain or  # spotify.com in api-partner.spotify.com
            target_domain in req_domain or
            req_domain in target_domain
        )

        if not domain_match:
            continue

        # Capture HTML for fallback scraping
        if req.response_body and 'text/html' in req.headers.get('accept', ''):
            if req.url == target_url or req.base_url == target_url.split('?')[0]:
                html_content = req.response_body

        # Analyze query parameters
        param_info = []
        for name, values in req.query_params.items():
            value = values[0] if values else ""
            param_info.append({
                "name": name,
                "sample_value": value[:100] if value else None,
            })

        # Get MORE of the response - we need to see the actual structure
        response_sample = None
        if req.response_json:
            # Get a larger sample - enough to see the real structure
            response_sample = json.dumps(req.response_json, indent=2)[:15000]

        # Extract important headers (these are needed to replay the request)
        request_headers = {}
        for k, v in req.headers.items():
            if k.lower() in important_headers:
                if k.lower() != 'cookie':
                    request_headers[k] = v

        # Parse POST data as JSON if possible
        post_data_json = None
        if req.post_data:
            try:
                post_data_json = json.loads(req.post_data)
            except:
                pass

        # Only add if it has a JSON response (API endpoint)
        if req.response_json:
            analyzed.append({
                "method": req.method,
                "url": req.url[:500],
                "base_url": req.base_url,
                "params": param_info,
                "headers": request_headers,
                "post_data_raw": req.post_data[:3000] if req.post_data else None,
                "post_data_json": post_data_json,
                "response_sample": response_sample,
                "response_json": req.response_json,  # parsed JSON for programmatic field extraction
                "response_size": len(req.response_body) if req.response_body else 0,
            })

    # Sort by response size (larger responses likely have the data)
    analyzed.sort(key=lambda x: x['response_size'], reverse=True)

    print(f"  Found {len(analyzed)} API endpoints matching *{base_domain}")

    return analyzed[:10], html_content  # Top 10 + HTML fallback


def identify_relevant_endpoint(goal: str, captured_requests: list[dict], client: OpenAI) -> dict:
    """
    Use LLM to identify which captured request contains the data we want,
    and exactly where in the response the data lives.
    """

    print("\nAnalyzing captured requests to find the right endpoint...")

    # Exclude response_json from payload to LLM (huge); keep response_sample for analysis
    requests_for_llm = [
        {k: v for k, v in r.items() if k != "response_json"}
        for r in captured_requests
    ]

    prompt = f"""Analyze these captured API requests and identify which one contains the data for this goal:

GOAL: {goal}

CAPTURED REQUESTS:
{json.dumps(requests_for_llm, indent=2)}

YOUR TASK:
1. Look at each response_sample carefully - find which one has the actual data
2. Find the EXACT JSON path to the data array
3. Identify the field names for each item

COMMON PATTERNS BY SITE:

YouTube (youtube.com):
- Use /youtubei/v1/browse endpoint (NOT /guide which is for sidebar)
- Playlist data path: contents.twoColumnBrowseResultsRenderer.tabs[0].tabRenderer.content.sectionListRenderer.contents[0].itemSectionRenderer.contents[0].playlistVideoListRenderer.contents
- Video fields: videoId, title.runs[0].text, lengthText.simpleText
- POST body needs: browseId = "VL" + playlist_id

Spotify (spotify.com):
- Data usually in: items, tracks.items, playlists.items
- Fields: name, id, duration_ms, artists[0].name

NASDAQ/Financial (nasdaq.com):
- Data usually in: data.rows, data.table.rows
- Fields: symbol, name, date, etc.

Generic sites:
- Look for arrays in: data, items, results, rows, records, entries

Respond with JSON:
{{
    "endpoint_index": 0,
    "endpoint_url": "the full base URL to call",
    "http_method": "GET or POST",
    "data_path": "exact.json.path.to.array",
    "item_fields": {{
        "desired_field": "path.in.each.item"
    }},
    "request_notes": "special notes (e.g., browseId needs VL prefix)",
    "post_body_template": null // or the POST body structure if needed
}}

Output ONLY valid JSON."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You analyze API responses to find exactly where the target data lives. Be precise about JSON paths."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=1500,
    )

    content = response.choices[0].message.content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]

    try:
        return json.loads(content)
    except:
        return None


def _get_data_array_by_path(obj, path: str):
    """Navigate path like 'data.rows' or 'data.table.rows' and return the array, or None."""
    if not path or not path.strip():
        return None
    parts = path.strip().split(".")
    current = obj
    for p in parts:
        if current is None:
            return None
        try:
            idx = int(p)
            current = current[idx] if isinstance(current, list) and 0 <= idx < len(current) else None
        except ValueError:
            current = current.get(p) if isinstance(current, dict) else None
    return current if isinstance(current, list) else None


def _to_snake_case(name: str) -> str:
    """Convert camelCase or PascalCase to snake_case."""
    result = []
    for i, c in enumerate(name):
        if c.isupper():
            if i > 0:
                result.append("_")
            result.append(c.lower())
        else:
            result.append(c)
    return "".join(result)


def get_actual_item_fields_from_response(target_endpoint: dict, data_path: str) -> dict:
    """
    Derive item_fields from the actual API response so generated code uses real keys.
    Returns { python_snake_name: exact_api_key } e.g. {"market_cap": "marketCap", "eps": "eps"}.
    """
    response_json = target_endpoint.get("response_json")
    if not response_json or not data_path:
        return {}
    arr = _get_data_array_by_path(response_json, data_path)
    if not arr:
        return {}
    keys = set()
    for item in arr[:30]:
        if isinstance(item, dict):
            keys.update(item.keys())
    return {_to_snake_case(k): k for k in sorted(keys)}


def revise_api_spec(original_spec: dict, endpoint_analysis: dict, target_endpoint: dict, client: OpenAI) -> dict:
    """
    Revise the API spec based on what data is actually available.
    Don't force the implementation to match the original plan - adapt the plan to reality.
    """

    print("\nRevising API spec based on actual available data...")

    prompt = f"""Revise this API specification based on what data is actually available.

ORIGINAL API SPEC (planned before seeing data):
{json.dumps(original_spec, indent=2)}

ENDPOINT ANALYSIS (what we found):
{json.dumps(endpoint_analysis, indent=2) if endpoint_analysis else "Not available"}

ACTUAL RESPONSE DATA (sample):
{target_endpoint.get('response_sample', 'Not available')[:8000] if target_endpoint else 'Not available'}

YOUR TASK:
1. Describe what the endpoint ACTUALLY provides - do not force the spec to match the original plan if it's wrong.
2. If the original plan doesn't match reality, prefer reality: change method names, parameters, or return schema to match the actual response.
3. Add all fields that exist in the response; remove any planned fields that aren't in the response.
4. You may add/remove methods or restructure the spec so it accurately reflects the real API.

When in doubt, the actual response data and endpoint_analysis are the source of truth—not the original plan.

Respond with the REVISED API spec as JSON (same structure as original, but updated to match reality):
{{
    "api_name": "...",
    "description": "...",
    "methods": [...]
}}

Output ONLY valid JSON."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You revise API specifications to match actual available data. Do NOT force the spec to match the original plan when it's wrong—prefer the actual endpoint and response. You may change method names, parameters, and schemas freely so the spec describes reality."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=2000,
    )

    content = response.choices[0].message.content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]

    try:
        revised = json.loads(content)
        print("API spec revised to match actual data.")
        return revised
    except:
        print("Warning: Could not revise spec, using original.")
        return original_spec


def implement_html_scraper(goal: str, api_spec: dict, html_content: str, target_url: str, client: OpenAI) -> str:
    """
    Generate a BeautifulSoup-based scraper when no JSON API is available.
    """

    print("\n" + "="*70)
    print("PHASE 3: HTML SCRAPING (no JSON API found)")
    print("="*70)
    print("\nGenerating HTML scraper using BeautifulSoup...")

    # Truncate HTML to reasonable size
    html_sample = html_content[:30000] if html_content else ""

    prompt = f"""Generate a Python scraper for this HTML page. There's no JSON API, so we need to parse HTML.

GOAL: {goal}

TARGET URL: {target_url}

API SPECIFICATION (guide for what to return—adapt to what's actually in the HTML):
{json.dumps(api_spec, indent=2)}

HTML CONTENT (sample):
{html_sample}

Generate a Python script that:
1. Uses requests to fetch the page
2. Uses BeautifulSoup to parse the HTML
3. Extracts the data; if the HTML structure doesn't match the spec, return what's actually there rather than forcing the spec
4. Returns it as a list of dicts

Example:
```python
import requests
from bs4 import BeautifulSoup
from typing import List, Dict

HEADERS = {{
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}}

def get_top_stories() -> List[Dict]:
    '''Get top stories from the page.'''
    response = requests.get("{target_url}", headers=HEADERS, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')

    stories = []
    for item in soup.select('.story-item'):  # Adjust selector based on HTML
        stories.append({{
            "title": item.select_one('.title').text.strip(),
            "url": item.select_one('a')['href'],
        }})
    return stories

if __name__ == "__main__":
    results = get_top_stories()
    for r in results[:5]:
        print(r)
```

IMPORTANT:
- Look at the actual HTML structure to find the right CSS selectors
- Handle missing elements gracefully
- Include timeout=10 on requests

Output ONLY valid Python code."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You generate Python web scrapers using BeautifulSoup. Analyze HTML to find the right CSS selectors."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=3000,
    )

    code = response.choices[0].message.content.strip()
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0]
    elif "```" in code:
        code = code.split("```")[1].split("```")[0]

    return code.strip()


def get_structure(obj, depth=0, max_depth=3):
    """Get structure of JSON without full data."""
    if depth >= max_depth:
        return "..."

    if isinstance(obj, dict):
        result = {}
        for k, v in list(obj.items())[:8]:
            result[k] = get_structure(v, depth + 1, max_depth)
        if len(obj) > 8:
            result["..."] = f"({len(obj) - 8} more)"
        return result
    elif isinstance(obj, list):
        if not obj:
            return []
        return [get_structure(obj[0], depth + 1, max_depth), f"({len(obj)} items)"]
    elif isinstance(obj, str):
        return obj[:50] + "..." if len(obj) > 50 else obj
    else:
        return obj


def implement_api(api_spec: dict, captured_requests: list[dict], endpoint_analysis: dict, client: OpenAI) -> str:
    """
    Generate Python implementation that maps the proposed API to discovered endpoints.
    """

    print("\n" + "="*70)
    print("PHASE 3: IMPLEMENTATION")
    print("="*70)
    print("\nMapping proposed API to discovered endpoints...")

    # Get the identified endpoint details
    endpoint_idx = endpoint_analysis.get("endpoint_index", 0) if endpoint_analysis else 0
    target_endpoint = captured_requests[endpoint_idx] if endpoint_idx < len(captured_requests) else captured_requests[0]

    # Build list outside f-string to avoid {{ being parsed as set literal (unhashable dict)
    captured_preview = [{"url": r["url"][:100], "method": r["method"]} for r in captured_requests]

    prompt = f"""Implement this API using the discovered internal endpoints.

API SPECIFICATION (guide only—do not force code to match if actual data differs):
{json.dumps(api_spec, indent=2)}

ENDPOINT ANALYSIS (which endpoint has the data and where—this is source of truth):
{json.dumps(endpoint_analysis, indent=2) if endpoint_analysis else "Not available"}

TARGET ENDPOINT (the one that contains the data):
{json.dumps(target_endpoint, indent=2)}

ALL CAPTURED ENDPOINTS (for reference):
{json.dumps(captured_preview, indent=2)}

CRITICAL: If the spec doesn't match the actual endpoint (e.g. different params, different return fields), implement based on the ACTUAL endpoint and item_fields. Do not force the code to match the spec when they conflict.

CRITICAL REQUIREMENTS:

1. USE THE EXACT ENDPOINT from the analysis - don't use a different one.

2. USE THE EXACT HEADERS from the target endpoint. Copy them exactly or the request will fail.

3. If it's a POST request, USE THE POST BODY structure from the captured data.
   - For YouTube: note that playlist browseId is usually "VL" + playlist_id
   - Copy the exact structure, just parameterize the parts that should change

4. USE THE DATA PATH from the analysis to extract the data.
   - The analysis tells you exactly where in the response the data array is
   - Use that exact path, don't guess

5. MAP FIELDS USING THE EXACT item_fields FROM THE ANALYSIS.
   - If endpoint_analysis has item_fields_from_actual_response: true, then item_fields were derived from the real API response.
   - Each key is the Python output name (snake_case), each value is the EXACT key in the JSON.
   - For each (output_name, api_key) in item_fields, use item.get(api_key) and put it under output_name.
   - Do NOT guess or invent field names; use only the keys listed in item_fields.

6. Set timeout=10 on all requests.

Example for a POST endpoint (like YouTube):
```python
import requests
from typing import Optional, List, Dict

HEADERS = {{
    "User-Agent": "Mozilla/5.0 ...",
    "Content-Type": "application/json",
    # ... copy exact headers from captured data
}}

def get_playlist_videos(playlist_id: str) -> List[Dict]:
    # YouTube uses "VL" prefix for playlist browseId
    browse_id = f"VL{{playlist_id}}" if not playlist_id.startswith("VL") else playlist_id

    # Copy the exact POST body structure from captured data
    payload = {{
        "context": {{
            "client": {{
                "clientName": "WEB",
                "clientVersion": "2.20240101.00.00"
            }}
        }},
        "browseId": browse_id
    }}

    response = requests.post(
        "https://www.youtube.com/youtubei/v1/browse",
        json=payload,
        headers=HEADERS,
        timeout=10
    )
    data = response.json()

    # Use the exact data path from analysis
    videos = []
    # Navigate to: contents.twoColumnBrowseResultsRenderer.tabs[0]...
    # (use the actual path from endpoint_analysis["data_path"])
    ...
    return videos
```

IMPORTANT:
- Copy headers EXACTLY from the target endpoint
- Copy POST body structure EXACTLY, parameterize only what needs to change
- Use the data_path from endpoint_analysis to navigate the response
- Use item_fields from endpoint_analysis: each key = Python output name (snake_case), each value = EXACT JSON key. Use item.get(value) for each (key, value). Do NOT guess field names.

Output ONLY valid Python code."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """You implement Python APIs using discovered internal endpoints.

CRITICAL RULES:
1. The API spec is a guide only. If it conflicts with the actual endpoint or item_fields, follow the actual endpoint and item_fields—do not force the code to match the spec.
2. Use the EXACT endpoint URL from endpoint_analysis
3. Copy headers EXACTLY from the target endpoint
4. For POST requests, copy the EXACT body structure from post_data
5. Use the data_path from endpoint_analysis to navigate the response
6. Map fields using item_fields: output_name -> item.get(api_key). Do NOT guess field names; use only keys from item_fields.
7. Always set timeout=10

COMMON SITE PATTERNS:

YouTube:
- Playlist browseId = "VL" + playlist_id (e.g., "VLPLxxxxxxx")
- Use /youtubei/v1/browse, NOT /guide
- Copy the full "context" object from captured post_data
- Videos are in deeply nested path like contents.twoColumnBrowseResultsRenderer.tabs[0].tabRenderer.content.sectionListRenderer.contents[0].itemSectionRenderer.contents[0].playlistVideoListRenderer.contents
- Each video has: title.runs[0].text, videoId, lengthText.simpleText

Spotify:
- API usually at api.spotify.com
- Needs Authorization header (captured from browser)
- Data usually in "items" or "tracks.items"

NASDAQ/Financial:
- API at api.nasdaq.com
- Data usually in "data.rows" or "data.table.rows"
- Date format: YYYY-MM-DD

Generic patterns:
- Data arrays are often in: data, items, results, rows, records, entries, content
- Pagination: look for offset/limit, page/pageSize, cursor, nextToken"""
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=4000,
    )

    code = response.choices[0].message.content.strip()

    # Clean markdown
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0]
    elif "```" in code:
        parts = code.split("```")
        if len(parts) >= 2:
            code = parts[1]
            if code.startswith("python"):
                code = code[6:]

    return code.strip()


# =============================================================================
# MAIN
# =============================================================================

async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate APIs for any website",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scrape.py "get all videos in playlist" "https://youtube.com/playlist?list=..."
    python scrape.py "get companies reporting earnings" "https://nasdaq.com/market-activity/earnings"
    python scrape.py "get job listings" "https://linkedin.com/jobs/search?keywords=python"
        """
    )
    parser.add_argument("goal", help="What you want to extract")
    parser.add_argument("url", help="The website URL")
    parser.add_argument("--output", "-o", default="generated_api.py", help="Output file")
    parser.add_argument("--capture-file", "-c", help="Use existing capture from extension")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument("--agent", "-a", action="store_true", help="Use AI agent to explore (recommended for complex sites)")
    parser.add_argument("--plan-only", action="store_true", help="Only show the API plan, don't implement")

    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY required")
        print("Set with: export OPENAI_API_KEY='your-key'")
        sys.exit(1)

    client = OpenAI()

    # Phase 1: Planning
    api_spec = plan_api(args.goal, args.url, client)
    display_api_plan(api_spec)

    # Save the plan
    with open("api_plan.json", "w") as f:
        json.dump(api_spec, f, indent=2)
    print(f"Saved plan to: api_plan.json")

    if args.plan_only:
        print("\n--plan-only specified, stopping here.")
        return

    # Ask user to confirm
    print("\n" + "-"*70)
    response = input("Proceed with this API plan? [Y/n/edit]: ").strip().lower()
    if response == 'n':
        print("Aborted.")
        return
    elif response == 'edit':
        print("Edit api_plan.json and re-run with: python scrape.py --from-plan api_plan.json ...")
        return

    # Phase 2: Exploration
    html_content = None
    if args.capture_file:
        captured = explore_from_extension_capture(args.capture_file)
        # No HTML from extension capture
    elif args.agent:
        # Use AI agent to explore (better for complex sites)
        captured, html_content = await explore_with_agent(args.url, args.goal, client, args.headless)
    else:
        # Manual exploration
        captured, html_content = await explore_with_browser(args.url, args.headless)

    if not captured:
        print("No requests captured.")
        if html_content:
            print("But we have HTML - will try HTML scraping.")
        else:
            return

    # Analyze captured requests (filter to target domain only)
    analyzed, _ = analyze_captured_requests(captured, args.url)

    # Decide: API-based or HTML scraping
    if analyzed:
        # Found JSON APIs - use them
        endpoint_analysis = identify_relevant_endpoint(args.goal, analyzed, client)

        if endpoint_analysis:
            ep_url = endpoint_analysis.get('endpoint_url') or 'unknown'
            data_path = endpoint_analysis.get('data_path') or 'unknown'
            print(f"\nIdentified endpoint: {ep_url[:60]}")
            print(f"Data path: {data_path}")
        else:
            print("\nWarning: Could not identify specific endpoint, will use best guess")

        # Get the target endpoint for revision
        endpoint_idx = 0
        if endpoint_analysis and endpoint_analysis.get("endpoint_index") is not None:
            endpoint_idx = endpoint_analysis.get("endpoint_index")
        target_endpoint = analyzed[endpoint_idx] if endpoint_idx < len(analyzed) else (analyzed[0] if analyzed else None)

        # Derive item_fields from actual API response so generated code uses real keys (no guessing)
        if target_endpoint and endpoint_analysis:
            data_path = endpoint_analysis.get("data_path")
            actual_fields = get_actual_item_fields_from_response(target_endpoint, data_path)
            if actual_fields:
                endpoint_analysis["item_fields"] = actual_fields
                endpoint_analysis["item_fields_from_actual_response"] = True
                print(f"Item fields from actual response: {list(actual_fields.keys())}")

        # Revise API spec based on actual available data
        revised_spec = revise_api_spec(api_spec, endpoint_analysis, target_endpoint, client)

        # Show what changed
        print("\n" + "-"*70)
        print("REVISED API (based on actual data):")
        display_api_plan(revised_spec)

        # Phase 3: Implementation (API-based)
        code = implement_api(revised_spec, analyzed, endpoint_analysis, client)
    else:
        # No JSON APIs found - fall back to HTML scraping
        print("\nNo JSON APIs found for this domain. Falling back to HTML scraping...")

        if not html_content:
            print("Error: No HTML content captured. Try browsing the page longer.")
            return

        # Phase 3: Implementation (HTML scraping)
        # For HTML, we let the scraper determine fields from the actual HTML
        code = implement_html_scraper(args.goal, api_spec, html_content, args.url, client)

    with open(args.output, "w") as f:
        f.write(code)

    print("\n" + "="*70)
    print("COMPLETE")
    print("="*70)
    print(f"\nGenerated: {args.output}")
    print(f"\nUsage:")
    print(f"    python {args.output}")
    print(f"\nThe interface was adapted to match the actual available data.")


if __name__ == "__main__":
    asyncio.run(main())

