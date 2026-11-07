"""
Web Scraper
-----------
A config-driven scraper: describe WHAT to collect in a JSON file (page URL, the CSS
selector for each item, and for each field), and the tool collects it across
multiple pages and saves a CSV (or JSON) file.

Usage:
    python scraper.py config.json
    python scraper.py config.json -o results.csv --max-pages 5
    python scraper.py config_local.json          # works on saved HTML files too

Use responsibly: only scrape public data you are allowed to collect, keep the
delay between requests, and respect the site's robots.txt and terms.
"""

import argparse
import csv
import json
import re
import sys
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests  # pyright: ignore[reportMissingImports, reportMissingModuleSource]
from bs4 import BeautifulSoup  # pyright: ignore[reportMissingImports, reportMissingModuleSource]

DEFAULTS = {
    "max_pages": 1,
    "delay_seconds": 1.5,
    "timeout_seconds": 15,
    "retries": 3,
    "respect_robots_txt": True,
    "output": "output.csv",
    "user_agent": "Mozilla/5.0 (compatible; StudentScraper/1.0)",
}


class ScraperError(Exception):
    """A problem the user can fix (bad config, unreachable page, ...)."""


# ------------------------------------------------------------------------- config
def validate_config(cfg):
    for key in ("url", "item_selector", "fields"):
        if key not in cfg:
            raise ScraperError(f"Config is missing '{key}'")
    if not isinstance(cfg["fields"], dict) or not cfg["fields"]:
        raise ScraperError("'fields' must list at least one field")
    for name, spec in cfg["fields"].items():
        if not isinstance(spec, dict) or "selector" not in spec:
            raise ScraperError(f"Field '{name}' needs a 'selector'")
    return {**DEFAULTS, **cfg}


def load_config(path):
    try:
        with open(path, encoding="utf-8") as f:
            return validate_config(json.load(f))
    except FileNotFoundError:
        raise ScraperError(f"Config file not found: {path}")
    except json.JSONDecodeError as e:
        raise ScraperError(f"Config is not valid JSON: {e}")


# ----------------------------------------------------------------------- fetching
def is_remote(url):
    return urlparse(url).scheme in ("http", "https")


def fetch_page(url, session, cfg, sleep=time.sleep):
    """Return the page HTML. Retries temporary failures; gives up at once on 404 etc."""
    if not is_remote(url):  # a saved HTML file on this computer
        try:
            with open(url, encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            raise ScraperError(f"Cannot read file {url}: {e}")

    last_error = None
    for attempt in range(1, cfg["retries"] + 1):
        try:
            resp = session.get(url, timeout=cfg["timeout_seconds"],
                               headers={"User-Agent": cfg["user_agent"]})
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code} (temporary)")
            if resp.status_code >= 400:
                raise ScraperError(f"{url} returned HTTP {resp.status_code}")
            if "charset" not in resp.headers.get("Content-Type", "").lower():
                resp.encoding = "utf-8"  # avoids '£' turning into 'Â£'
            return resp.text
        except requests.RequestException as e:  # network error or temporary status
            last_error = e
            if attempt < cfg["retries"]:
                sleep(cfg["delay_seconds"] * attempt)  # wait longer each retry
    raise ScraperError(f"Could not fetch {url} after {cfg['retries']} tries: {last_error}")


def load_robots(url, session, cfg):
    """Read the site's robots.txt. If it can't be read, assume everything is allowed."""
    parts = urlparse(url)
    parser = RobotFileParser()
    try:
        resp = session.get(f"{parts.scheme}://{parts.netloc}/robots.txt",
                           timeout=cfg["timeout_seconds"], headers={"User-Agent": cfg["user_agent"]})
        parser.parse(resp.text.splitlines() if resp.status_code == 200 else [])
    except requests.RequestException:
        parser.parse([])
    return parser


# --------------------------------------------------------------------- extracting
def to_number(text):
    """'£51.77' -> 51.77, '1,299' -> 1299, 'free' -> ''"""
    match = re.search(r"-?(?:\d[\d,]*(?:\.\d+)?|\.\d+)", text)  # first real number in the text
    if not match:
        return ""
    value = float(match.group(0).replace(",", ""))
    return int(value) if value.is_integer() else value


def extract_value(element, spec, page_url):
    """Pull one field out of one item, according to its spec."""
    node = element.select_one(spec["selector"]) if spec["selector"] else element
    if node is None:
        return ""  # a missing field never crashes the run
    if "attr" in spec:
        value = node.get(spec["attr"], "")
        if isinstance(value, list):  # BeautifulSoup returns 'class' as a list
            value = " ".join(value)
    else:
        value = node.get_text(" ", strip=True)
    value = value.strip()

    if spec.get("regex"):
        match = re.search(spec["regex"], value)
        value = (match.group(1) if match and match.groups() else match.group(0)) if match else ""
    if spec.get("absolute_url") and value:
        value = urljoin(page_url, value)
    if spec.get("type") == "number" and value != "":
        value = to_number(str(value))
    return value


def extract_items(soup, cfg, page_url):
    return [
        {name: extract_value(el, spec, page_url) for name, spec in cfg["fields"].items()}
        for el in soup.select(cfg["item_selector"])
    ]


# ------------------------------------------------------------------------ the run
def scrape(cfg, session=None, sleep=time.sleep, log=print):
    session = session or requests.Session()
    rows, seen, pages = [], set(), 0
    url = cfg["url"]
    robots = None

    while url and pages < cfg["max_pages"] and url not in seen:
        seen.add(url)

        if is_remote(url) and cfg["respect_robots_txt"]:
            robots = robots or load_robots(url, session, cfg)
            if not robots.can_fetch(cfg["user_agent"], url):
                log(f"Skipped (blocked by robots.txt): {url}")
                break

        log(f"Page {pages + 1}: {url}")
        soup = BeautifulSoup(fetch_page(url, session, cfg, sleep), "html.parser")
        items = extract_items(soup, cfg, url)
        if not items:
            log("  No items matched 'item_selector' on this page - check your selector.")
        rows.extend(items)
        pages += 1

        next_selector = cfg.get("next_page_selector")
        link = soup.select_one(next_selector) if next_selector else None
        url = urljoin(url, link["href"]) if link is not None and link.get("href") else None
        if url and pages < cfg["max_pages"]:
            sleep(cfg["delay_seconds"])  # be polite between pages

    return rows, pages


def save(rows, fields, path):
    if path.lower().endswith(".json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)
    else:  # utf-8-sig so Excel shows symbols like £ and ₹ correctly
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(fields))
            writer.writeheader()
            writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Scrape a website into a CSV file using a JSON config.")
    parser.add_argument("config", help="Path to the JSON config file")
    parser.add_argument("-o", "--output", help="Output file (.csv or .json); overrides the config")
    parser.add_argument("--max-pages", type=int, help="Maximum pages to scrape; overrides the config")
    parser.add_argument("--ignore-robots", action="store_true", help="Do not check robots.txt (not recommended)")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
        if args.output:
            cfg["output"] = args.output
        if args.max_pages:
            cfg["max_pages"] = args.max_pages
        if args.ignore_robots:
            cfg["respect_robots_txt"] = False
        rows, pages = scrape(cfg)
    except ScraperError as e:
        sys.exit(f"Error: {e}")

    save(rows, cfg["fields"], cfg["output"])
    print(f"\nDone: {len(rows)} items from {pages} page(s) -> {cfg['output']}")


if __name__ == "__main__":
    main()
