<div align="center">

# Config-Driven Web Scraper

**Describe what to collect in a small JSON file and get a clean CSV or JSON, across multiple pages, without changing code.**

![Python](https://img.shields.io/badge/Python-0d1117?style=flat-square&logo=python&logoColor=3776AB)
![Requests](https://img.shields.io/badge/Requests-0d1117?style=flat-square)
![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup4-0d1117?style=flat-square)
![pytest](https://img.shields.io/badge/tests-17%20passing-3fb950?style=flat-square&logo=pytest&logoColor=white&labelColor=0d1117)

</div>

---

## Overview

A config-driven web scraper in Python. You describe **what to collect** in a small JSON file (the page URL, the CSS selector for each item, and for each field), and the tool collects it across multiple pages and saves a CSV or JSON file. To scrape a different website, you change the config and not the code.

## Problem Statement

Most scraping scripts are written for one website and break or need rewriting for the next one. Collecting product lists, prices or listings for different sites should only require saying *where* the data is on the page. This tool separates that description (the config) from the scraping engine, and is polite to the sites it visits by default.

## Features

- **Config-driven**: a new site is a new JSON file, with no coding needed
- **Multi-page scraping**: follows "next page" links up to a page limit you set
- **Field options**: read text or an HTML attribute, extract part of a value with a regex, turn relative links into full URLs, convert prices to numbers (`£1,047.82` becomes `1047.82`)
- **Polite by default**: waits between pages, identifies itself with a User-Agent, and checks `robots.txt` before scraping
- **Reliable**: retries temporary failures (timeouts, server errors) with growing waits, but gives up straight away on a 404
- **Forgiving**: a missing field leaves a blank cell and the run continues
- **Excel-friendly output**: CSV is saved so `£` and `₹` display correctly in Excel; use a `.json` file name for JSON
- **Tested offline**: 17 automated tests run on saved HTML pages and a fake network, never the live web

## Sample Output

[`books_sample.csv`](books_sample.csv) is the real output of running the scraper on the saved pages in `sample_pages/`.

## Tech Stack

- **Language:** Python 3
- **HTTP:** requests
- **HTML parsing:** BeautifulSoup4 (CSS selectors)
- **robots.txt:** `urllib.robotparser`
- **Testing:** pytest

## Project Structure

```text
config-driven-web-scraper/
├── scraper.py          # scraping engine and command-line interface
├── test_scraper.py     # 17 offline tests
├── config.json         # live example: books.toscrape.com (a site built for practice)
├── config_local.json   # offline example using the saved pages
├── sample_pages/       # two saved HTML pages for offline runs and tests
├── books_sample.csv    # output produced by config_local.json
├── requirements.txt
└── .gitignore
```

## Installation and Setup

```bash
git clone https://github.com/MohammedShareef3527/config-driven-web-scraper.git
cd config-driven-web-scraper
pip install -r requirements.txt

# try it on the saved sample pages (no internet needed)
python scraper.py config_local.json

# scrape a live practice site (books.toscrape.com is built for learning)
python scraper.py config.json
```

Options:

```bash
python scraper.py config.json -o results.json --max-pages 5
```

## Configuration

```json
{
  "url": "https://books.toscrape.com/",
  "item_selector": "article.product_pod",
  "fields": {
    "title":  { "selector": "h3 a", "attr": "title" },
    "price":  { "selector": "p.price_color", "type": "number" },
    "rating": { "selector": "p.star-rating", "attr": "class", "regex": "star-rating (\\w+)" },
    "link":   { "selector": "h3 a", "attr": "href", "absolute_url": true }
  },
  "next_page_selector": "li.next a",
  "max_pages": 3,
  "delay_seconds": 1.5,
  "output": "books.csv"
}
```

| Setting | Meaning |
|---|---|
| `url` | first page to scrape (a saved `.html` file path also works) |
| `item_selector` | CSS selector matching one item (one product, one listing) |
| `fields` | one entry per column; `selector` is required |
| `attr` | read this HTML attribute instead of the visible text |
| `regex` | keep only the part of the value matched by the first group |
| `absolute_url` | turn a relative link into a full URL |
| `type` | `"number"` converts text like `£51.77` to `51.77` |
| `next_page_selector` | CSS selector of the "next" link; leave out for a single page |
| `max_pages`, `delay_seconds`, `retries`, `timeout_seconds` | limits and politeness settings |
| `respect_robots_txt` | `true` by default |

Command-line options `-o/--output`, `--max-pages` and `--ignore-robots` override the config. No API keys are needed.

To find a selector: in Chrome, right-click an item, choose **Inspect**, and look at its tag and class names.

## How It Works

1. `load_config()` reads and validates the JSON
2. `fetch_page()` downloads a page (or reads a local file), retrying temporary failures
3. `extract_items()` finds every item with `item_selector`, then `extract_value()` reads each field
4. `scrape()` loops over pages: it checks `robots.txt`, extracts items, finds the next link, and waits before the next request. It stops at `max_pages` or if a page repeats
5. `save()` writes the CSV or JSON file

## Run the Tests

```bash
pytest
```

## Use Responsibly

Only scrape public data you are allowed to collect. Keep the delay between requests, don't overload a site, and respect its `robots.txt` and terms of service. Avoid collecting personal data.

## Future Improvements

These are planned ideas, not current features:

- Pages that load their content with JavaScript (would need a browser tool such as Playwright)
- Save results to a database or Google Sheets
- Run on a schedule to track price changes

## Learning Outcomes

- HTTP requests, sessions, timeouts and retry with backoff
- HTML parsing with CSS selectors in BeautifulSoup
- Designing a data-driven tool where behaviour comes from configuration
- Ethical scraping: robots.txt, rate limiting and identifying the client
- Testing network code offline with saved pages and a fake session

## Author

**Mohammed Shamsul Qhadri Shareef**
GitHub: [@MohammedShareef3527](https://github.com/MohammedShareef3527)
