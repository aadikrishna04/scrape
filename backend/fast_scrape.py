"""
Fast Scrape - HTTP-based web scraping with LLM extraction (like parse.bot)
10x faster than browser automation for most scraping tasks.
"""
import os
import re
import asyncio
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from google import genai
from google.genai import types


# Default headers to mimic a browser
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def html_to_text(html: str, base_url: str = "") -> str:
    """
    Convert HTML to clean text/markdown format.
    Preserves structure like headings, lists, and links.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove script, style, and other non-content elements
    for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
        element.decompose()

    # Convert to structured text
    lines = []

    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "div", "span", "a"]):
        text = element.get_text(strip=True)
        if not text:
            continue

        # Handle headings
        if element.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            level = int(element.name[1])
            lines.append(f"{'#' * level} {text}")
        # Handle list items
        elif element.name == "li":
            lines.append(f"- {text}")
        # Handle links (include href)
        elif element.name == "a" and element.get("href"):
            href = element.get("href", "")
            if base_url and not href.startswith(("http://", "https://")):
                href = urljoin(base_url, href)
            lines.append(f"[{text}]({href})")
        # Handle paragraphs and other text
        elif element.name in ["p", "div"] and len(text) > 20:
            lines.append(text)

    # Deduplicate while preserving order
    seen = set()
    unique_lines = []
    for line in lines:
        if line not in seen:
            seen.add(line)
            unique_lines.append(line)

    return "\n\n".join(unique_lines)


def extract_metadata(soup: BeautifulSoup) -> Dict[str, str]:
    """Extract metadata from HTML."""
    metadata = {}

    # Title
    title = soup.find("title")
    if title:
        metadata["title"] = title.get_text(strip=True)

    # Meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc:
        metadata["description"] = meta_desc.get("content", "")

    # Open Graph data
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title:
        metadata["og_title"] = og_title.get("content", "")

    og_desc = soup.find("meta", attrs={"property": "og:description"})
    if og_desc:
        metadata["og_description"] = og_desc.get("content", "")

    return metadata


async def fetch_url(url: str, timeout: float = 30.0) -> Dict[str, Any]:
    """
    Fetch URL content via HTTP.

    Returns:
        Dict with success, html, status_code, and error
    """
    try:
        async with httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
            timeout=timeout
        ) as client:
            response = await client.get(url)

            return {
                "success": True,
                "html": response.text,
                "status_code": response.status_code,
                "final_url": str(response.url),
                "content_type": response.headers.get("content-type", ""),
            }

    except httpx.TimeoutException:
        return {"success": False, "error": f"Request timed out after {timeout}s"}
    except httpx.RequestError as e:
        return {"success": False, "error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


async def extract_with_llm(text: str, extract_prompt: str, metadata: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Use LLM to extract structured data from text.

    Args:
        text: Cleaned text content
        extract_prompt: What to extract
        metadata: Page metadata

    Returns:
        Dict with extracted data
    """
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    metadata_str = ""
    if metadata:
        metadata_str = f"\nPage metadata: {metadata}\n"

    # Truncate text if too long (keep first ~15000 chars)
    if len(text) > 15000:
        text = text[:15000] + "\n\n[Content truncated...]"

    prompt = f"""Extract the following information from this web page content.

{metadata_str}
Page content:
{text}

---

Extraction task: {extract_prompt}

Provide a structured response with the extracted information. If specific information is not found, indicate that clearly. Be concise but complete."""

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3)
        )

        return {
            "success": True,
            "data": response.text,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"LLM extraction failed: {str(e)}"
        }


def find_pagination_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    """
    Find pagination links on a page.
    Returns list of unique URLs for additional pages.
    """
    pagination_links = []
    seen_urls = set()

    # Common pagination patterns
    pagination_selectors = [
        'a[rel="next"]',
        '.pagination a',
        '.pager a',
        'nav.pagination a',
        '[class*="pagination"] a',
        '[class*="pager"] a',
        'a[aria-label*="next"]',
        'a[aria-label*="Next"]',
        'a:contains("Next")',
        'a:contains("next")',
        'a:contains("→")',
        'a:contains("»")',
    ]

    # Also look for numbered page links
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        text = link.get_text(strip=True)

        # Skip empty or javascript links
        if not href or href.startswith('javascript:') or href == '#':
            continue

        # Check if it's a pagination link
        is_pagination = False

        # Check link text
        if text.lower() in ['next', 'next page', '→', '»', '>>', 'more']:
            is_pagination = True
        elif text.isdigit() and int(text) > 1:
            is_pagination = True

        # Check URL patterns
        pagination_patterns = [
            r'[?&]page=\d+',
            r'[?&]p=\d+',
            r'/page/\d+',
            r'/p/\d+',
            r'[?&]offset=\d+',
            r'[?&]start=\d+',
        ]
        for pattern in pagination_patterns:
            if re.search(pattern, href):
                is_pagination = True
                break

        # Check parent elements for pagination class
        parent = link.parent
        while parent and parent.name:
            parent_classes = parent.get('class', [])
            if any('pag' in c.lower() for c in parent_classes):
                is_pagination = True
                break
            parent = parent.parent

        if is_pagination:
            full_url = urljoin(base_url, href)
            if full_url not in seen_urls and full_url != base_url:
                seen_urls.add(full_url)
                pagination_links.append(full_url)

    return pagination_links[:10]  # Limit to 10 pages max


async def fast_scrape(url: str, extract_prompt: str, max_pages: int = 1) -> Dict[str, Any]:
    """
    Fast HTTP-based web scraping with LLM extraction.

    This is 10x faster than browser automation for most use cases.
    Use browser automation only when you need interaction (clicks, login, etc.)

    Args:
        url: URL to scrape
        extract_prompt: What information to extract from the page
        max_pages: Maximum number of pages to scrape (for pagination). Default 1.

    Returns:
        Dict with success, data, and metadata
    """
    # Validate URL
    if not url or not url.startswith(("http://", "https://")):
        return {
            "success": False,
            "error": f"Invalid URL: {url}. Must start with http:// or https://"
        }

    all_text = []
    all_metadata = {}
    pages_scraped = 0
    urls_to_scrape = [url]
    scraped_urls = set()

    while urls_to_scrape and pages_scraped < max_pages:
        current_url = urls_to_scrape.pop(0)

        if current_url in scraped_urls:
            continue

        scraped_urls.add(current_url)

        # Step 1: Fetch the page
        fetch_result = await fetch_url(current_url)

        if not fetch_result.get("success"):
            if pages_scraped == 0:
                return {
                    "success": False,
                    "error": fetch_result.get("error", "Failed to fetch URL"),
                    "url": url
                }
            continue  # Skip failed pages if we have some content

        html = fetch_result.get("html", "")

        # Step 2: Parse and clean HTML
        soup = BeautifulSoup(html, "html.parser")

        if pages_scraped == 0:
            all_metadata = extract_metadata(soup)
            all_metadata["scraped_url"] = url

        text = html_to_text(html, base_url=current_url)

        if text and len(text) >= 50:
            all_text.append(f"--- Page {pages_scraped + 1}: {current_url} ---\n{text}")
            pages_scraped += 1

            # Find pagination links if we need more pages
            if pages_scraped < max_pages:
                pagination_links = find_pagination_links(soup, current_url)
                for link in pagination_links:
                    if link not in scraped_urls and link not in urls_to_scrape:
                        urls_to_scrape.append(link)

    if not all_text:
        return {
            "success": False,
            "error": "Page content too short or empty. The page might require JavaScript rendering.",
            "url": url,
            "metadata": all_metadata
        }

    combined_text = "\n\n".join(all_text)
    all_metadata["pages_scraped"] = pages_scraped

    # Step 3: Extract with LLM
    extraction_result = await extract_with_llm(combined_text, extract_prompt, all_metadata)

    if not extraction_result.get("success"):
        return {
            "success": False,
            "error": extraction_result.get("error", "Extraction failed"),
            "url": url,
            "metadata": all_metadata
        }

    return {
        "success": True,
        "data": extraction_result.get("data"),
        "url": url,
        "pages_scraped": pages_scraped,
        "metadata": all_metadata,
    }


# Convenience function for direct calls
async def scrape(url: str, prompt: str, max_pages: int = 1) -> str:
    """
    Simple interface for fast scraping.

    Args:
        url: URL to scrape
        prompt: What to extract
        max_pages: Max pages to follow for pagination (default 1)

    Returns extracted data as string, or error message.
    """
    result = await fast_scrape(url, prompt, max_pages=max_pages)
    if result.get("success"):
        pages_info = f" (scraped {result.get('pages_scraped', 1)} pages)" if result.get('pages_scraped', 1) > 1 else ""
        return result.get("data", "") + pages_info
    else:
        return f"Error: {result.get('error', 'Unknown error')}"


if __name__ == "__main__":
    # Test the fast scrape
    import asyncio

    async def test():
        # Test single page
        print("=== Single Page Test ===")
        result = await fast_scrape(
            "https://stripe.com/pricing",
            "Extract all pricing information including product names, prices, and features"
        )
        print(result)

        # Test pagination
        print("\n=== Pagination Test ===")
        result = await fast_scrape(
            "https://news.ycombinator.com",
            "Extract all story titles and their URLs",
            max_pages=2
        )
        print(result)

    asyncio.run(test())
