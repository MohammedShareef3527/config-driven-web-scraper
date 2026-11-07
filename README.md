# Web Scraper

A config-driven web scraper in Python. You describe **what to collect** in a small JSON file (the page URL, the CSS selector for each item, and for each field), and the tool collects it across multiple pages and saves a CSV or JSON file. To scrape a different website, you change the config and not the code.

## Features

- **Config-driven**: a new site is a new JSON file, with no coding needed
- **Multi-page scraping**: follows "next page" links up to a page limit you set
- **Field options**: read text or an HTML attribute, extract part of a value with a regex, turn relative links into full URLs, convert prices to numbers (`£1,047.82` becomes `1047.82`)
- **Polite by default**: waits between pages, identifies itself with a User-Agent, and checks `robots.txt` before scraping
- **Reliable**: retries temporary failures (timeouts, server errors) with growing waits, but gives up straight away on a 404
- **Forgiving**: a missing field leaves a blank cell and the run continues
- **Excel-friendly output**: CSV is saved so `£` and `₹` display correctly in Excel; use a `.json` file name for JSON
- **Tested offline**: 17 automated tests run on saved HTML pages and a fake network, never the live web

## How to run

```bash
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

## The config file

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

To find a selector: in Chrome, right-click an item, choose **Inspect**, and look at its tag and class names.

## How it works

1. `load_config()` reads and validates the JSON
2. `fetch_page()` downloads a page (or reads a local file), retrying temporary failures
3. `extract_items()` finds every item with `item_selector`, then `extract_value()` reads each field
4. `scrape()` loops over pages: it checks `robots.txt`, extracts items, finds the next link, and waits before the next request. It stops at `max_pages` or if a page repeats
5. `save()` writes the CSV or JSON file

## Run the tests

```bash
pytest
```

## Use responsibly

Only scrape public data you are allowed to collect. Keep the delay between requests, don't overload a site, and respect its `robots.txt` and terms of service. Avoid collecting personal data.

## Tech Stack

Python 3, requests, BeautifulSoup4, pytest

## Possible Future Improvements

- Pages that load their content with JavaScript (would need a browser tool such as Playwright)
- Save results to a database or Google Sheets
- Run on a schedule to track price changes
