from urllib.parse import urlencode
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time 
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
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def parse_posting_urls(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    seen_urls = set()

    # New layout
    new_cards = soup.find_all("li", attrs={"data-hns-job-listing": True})

    for card in new_cards:
        title_link = card.find("a", href=True)
        if not title_link:
            continue

        title = title_link.get_text(" ", strip=True) or None
        job_url = urljoin("https://ca.indeed.com", title_link["href"])

        if job_url in seen_urls:
            continue
        seen_urls.add(job_url)

        if title and job_url:
            jobs.append({
                "job_url": job_url,
            })

    # Old layout fallback
    old_cards = soup.find_all("td", class_="resultContent")

    for card in old_cards:
        title_tag = card.find("h2", class_="jobTitle")
        link = title_tag.find("a", href=True) if title_tag else None
        if not link:
            continue

        title = link.get_text(" ", strip=True) or None
        job_url = urljoin("https://ca.indeed.com", link["href"])

        if job_url in seen_urls:
            continue
        seen_urls.add(job_url)

        jobs.append({
            "job_url": job_url,
        })

    return jobs
def parse_all_posting_urls(html: str) -> list[dict]:
    """
    Return all jobs found on one Indeed results page.
    Each item contains at least title + job_url.
    """
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    seen_urls = set()

    # Newer layout
    new_cards = soup.find_all("li", attrs={"data-hns-job-listing": True})
    for card in new_cards:
        link = card.find("a", attrs={"data-jk": True}, href=True)
        if not link:
            h2 = card.find("h2")
            link = h2.find("a", href=True) if h2 else None
        if not link:
            continue

        title = link.get_text(" ", strip=True) or None
        job_url = urljoin("https://ca.indeed.com", link["href"])

        if job_url not in seen_urls:
            seen_urls.add(job_url)
            jobs.append({
                "title": title,
                "job_url": job_url,
            })

    # Older layout fallback
    old_cards = soup.find_all("td", class_="resultContent")
    for card in old_cards:
        title_tag = card.find("h2", class_="jobTitle")
        link = title_tag.find("a", href=True) if title_tag else None
        if not link:
            continue

        title = link.get_text(" ", strip=True) or None
        job_url = urljoin("https://ca.indeed.com", link["href"])

        if job_url not in seen_urls:
            seen_urls.add(job_url)
            jobs.append({
                "title": title,
                "job_url": job_url,
            })

    return jobs
def parse_job_details(html: str, job_url: str) -> dict:
    """
    Parse a single Indeed job posting page.

    Args:
        html: HTML from the individual job page
        job_url: URL of the job page

    Returns:
        Dictionary with extracted job details
    """
    soup = BeautifulSoup(html, "html.parser")

    def clean_text(tag):
        return tag.get_text(" ", strip=True) if tag else None

    # Job title
    title = None
    title_container = soup.find(
        attrs={"data-testid": "jobsearch-JobInfoHeader-title-container"}
    )
    if title_container:
        h1 = title_container.find("h1")
        title = clean_text(h1)

    if not title:
        h1 = soup.find("h1")
        title = clean_text(h1)

    # Company name
    company = None
    company_container = soup.find(
        attrs={"data-testid": "jobsearch-CompanyInfoContainer"}
    )
    if company_container:
        company = clean_text(company_container)

    # fallback if container is too broad
    if not company:
        inline_company = soup.find(
            attrs={"data-testid": "inlineHeader-companyName"}
        )
        company = clean_text(inline_company)

    # Location
    location = None
    location_tag = soup.find(
        attrs={"data-testid": "inlineHeader-companyLocation"}
    )
    location = clean_text(location_tag)

    # Pay / compensation
    pay = None

    # First try common metadata items
    metadata_items = soup.find_all(
        attrs={"data-testid": "jobsearch-JobMetadataHeader-item"}
    )
    for item in metadata_items:
        text = clean_text(item)
        if text and "$" in text:
            pay = text
            break

    # Fallback: scan a visible details container
    if not pay:
        other_details = soup.find(
            attrs={"data-testid": "jobsearch-OtherJobDetailsContainer"}
        )
        if other_details:
            for line in other_details.get_text("\n", strip=True).split("\n"):
                if "$" in line:
                    pay = line.strip()
                    break

    # Job description
    description = None
    desc_tag = soup.find(id="jobDescriptionText")
    if desc_tag:
        description = desc_tag.get_text("\n", strip=True)

    return {
        "job_url": job_url,
        "job_title": title,
        "company_name": company,
        "location": location,
        "pay": pay,
        "job_description": description,
    }
def collect_search_result_links(
    query: str,
    location: str,
    pages: int = 5,
    remote: bool = False,
    days: int | None = 1,
    country: str = "ca",
    headless: bool = True,
) -> list[dict]:
    """
    Collect all job links from the first `pages` pages of one search.
    """
    all_jobs = []
    seen_urls = set()

    for page_num in range(pages):
        start = page_num * 10
        search_url = build_indeed_search_url(
            query=query,
            location=location,
            start=start,
            remote=remote,
            days=days,
            country=country,
        )

        print(f"Fetching search page {page_num + 1}: {search_url}")
        html = fetch_page_html(search_url, headless=headless)
        jobs_on_page = parse_all_posting_urls(html)

        for job in jobs_on_page:
            if job["job_url"] not in seen_urls:
                seen_urls.add(job["job_url"])
                job["search_query"] = query
                job["search_location"] = location
                job["search_page"] = page_num + 1
                all_jobs.append(job)

        time.sleep(1)

    return all_jobs


def collect_multiple_searches(
    searches: list[dict],
    pages_per_search: int = 5,
    headless: bool = True,
) -> list[dict]:
    """
    searches example:
    [
        {"query": "investments", "location": "Toronto, ON"},
        {"query": "private wealth", "location": "Toronto, ON"},
        {"query": "equity research", "location": "Toronto, ON"},
    ]
    """
    all_search_results = []
    seen_urls = set()

    for search in searches:
        query = search["query"]
        location = search.get("location", "")
        remote = search.get("remote", False)
        days = search.get("days", 1)
        country = search.get("country", "ca")

        jobs = collect_search_result_links(
            query=query,
            location=location,
            pages=pages_per_search,
            remote=remote,
            days=days,
            country=country,
            headless=headless,
        )

        for job in jobs:
            if job["job_url"] not in seen_urls:
                seen_urls.add(job["job_url"])
                all_search_results.append(job)

    return all_search_results


def fetch_details_for_jobs(
    jobs: list[dict],
    headless: bool = True,
) -> list[dict]:
    """
    Given a list of jobs with job_url, fetch each job page and parse details.
    """
    detailed_jobs = []

    for i, job in enumerate(jobs, start=1):
        print(f"[{i}/{len(jobs)}] Fetching job details: {job['job_url']}")
        try:
            job_html = fetch_page_html(job["job_url"], headless=headless)
            details = parse_job_details(job_html, job["job_url"])

            merged = {
                **job,      # search-level metadata
                **details,  # detailed page fields
            }
            detailed_jobs.append(merged)

            time.sleep(1)

        except Exception as e:
            print(f"Failed to fetch details for {job['job_url']}: {e}")

    return detailed_jobs


searches = [
    {"query": "investments", "location": "Toronto, ON", "days": 1},
    {"query": "private wealth", "location": "Canada", "days": 1},
    {"query": "finance", "location": "Toronto, ON", "days": 1},
    {"query": "finance", "location": "Canada", "days": 1},
    {"query": "investments", "location": "Canada", "days": 1},
]

jobs = collect_multiple_searches(
    searches=searches,
    pages_per_search=5,
    headless=False,
)

print(f"Collected {len(jobs)} unique job links.")

detailed_jobs = fetch_details_for_jobs(jobs, headless=False)

print(f"Fetched details for {len(detailed_jobs)} jobs.")
print(detailed_jobs[0])