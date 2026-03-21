from urllib.parse import urlencode
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from urllib.parse import urljoin
def build_indeed_search_url(
    query: str,
    location: str = "",
    start: int = 0,
    remote: bool = False,
    days: int | None = None,
    country: str = "ca"
) -> str:
    """
    Build an Indeed search URL.

    Args:
        query: Job search keywords, e.g. "software engineer intern"
        location: Location text, e.g. "Toronto, ON"
        start: Pagination offset. 0 = first page, 10 = second page, etc.
        remote: If True, adds a remote-job filter.
        days: Optional age filter in days, e.g. 1, 3, 7, 14.
        country: Indeed country domain prefix, e.g. "ca", "www", "uk"

    Returns:
        A full Indeed search URL as a string.
    """
    if not query.strip():
        raise ValueError("query cannot be empty")

    if start < 0:
        raise ValueError("start must be 0 or greater")

    params = {
        "q": query.strip(),
        "l": location.strip(),
        "start": start,
    }

    if remote:
        params["sc"] = "0kf:attr(DSQF7);"  # common remote filter token

    if days is not None:
        if days not in {1, 3, 7, 14}:
            raise ValueError("days must be one of: 1, 3, 7, 14")
        params["fromage"] = days

    query_string = urlencode(params)
    return f"https://{country}.indeed.com/jobs?{query_string}"

   
def fetch_page_html(url: str, headless: bool = True, timeout_ms: int = 30000) -> str:
    """
    Open a page with Playwright and return the final HTML.

    Args:
        url: The page URL to open.
        headless: Whether to run the browser headlessly.
        timeout_ms: Navigation timeout in milliseconds.

    Returns:
        The full page HTML as a string.
    """
    if not url.strip():
        raise ValueError("url cannot be empty")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(2000)  # small buffer for dynamic content
            html = page.content()
            return html

        except PlaywrightTimeoutError as e:
            raise RuntimeError(f"Timed out loading page: {url}") from e

        finally:
            context.close()
            browser.close()
def parse_posting_url(html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")


    new_cards = soup.find_all("li", attrs={"data-hns-job-listing": True})

    for card in new_cards:
        title_link = card.find("a", href=True)
        if not title_link:
            continue

        title = title_link.get_text(" ", strip=True) or None
        job_url = urljoin("https://ca.indeed.com", title_link["href"])

  

        if title and job_url:
            return {
                "title": title,
                "job_url": job_url,
            }

    
    old_cards = soup.find_all("td", class_="resultContent")

    for card in old_cards:
        title_tag = card.find("h2", class_="jobTitle")
        link = title_tag.find("a", href=True) if title_tag else None

        if not link:
            continue

        title = link.get_text(" ", strip=True)
        job_url = urljoin("https://ca.indeed.com", link["href"])


        return {
            "title": title,
            "job_url": job_url,
        }

    return None
url = build_indeed_search_url(
    query="investments",
    location="Toronto, ON",
    start=0,
    remote=False,
    days=1,
    country="ca"
)


html = fetch_page_html(url, headless=False)
job = parse_posting_url(html)



