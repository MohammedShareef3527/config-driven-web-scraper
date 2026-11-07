import csv
import json

import pytest
import requests
from bs4 import BeautifulSoup

import scraper
from scraper import (ScraperError, extract_items, fetch_page, load_config, main,
                     scrape, to_number, validate_config)

NO_WAIT = lambda seconds: None  # tests never really sleep


def local_cfg(**overrides):
    cfg = load_config("config_local.json")
    cfg.update(overrides)
    return cfg


# ------------------------------------------------------------------ fake network
class FakeResponse:
    def __init__(self, status=200, text="", content_type="text/html; charset=utf-8"):
        self.status_code, self.text = status, text
        self.headers = {"Content-Type": content_type}
        self.encoding = None


class FakeSession:
    """Returns queued responses (or raises queued exceptions), in order."""
    def __init__(self, *queue):
        self.queue, self.calls = list(queue), []

    def get(self, url, **kwargs):
        self.calls.append(url)
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


PAGE = '<article class="product_pod"><h3><a href="a.html" title="Book A">x</a></h3></article>'
REMOTE_CFG = dict(url="https://example.com/p1", item_selector="article",
                  fields={"title": {"selector": "a", "attr": "title"}},
                  respect_robots_txt=False, delay_seconds=0)


# ------------------------------------------------------------------------ helpers
def test_to_number():
    assert to_number("£51.77") == 51.77
    assert to_number("1,299") == 1299
    assert to_number("Rs. 40") == 40
    assert to_number("free") == ""


def test_config_validation():
    with pytest.raises(ScraperError):
        validate_config({"url": "x"})
    with pytest.raises(ScraperError):
        validate_config({"url": "x", "item_selector": "a", "fields": {}})
    with pytest.raises(ScraperError):
        validate_config({"url": "x", "item_selector": "a", "fields": {"t": {}}})
    assert validate_config({"url": "x", "item_selector": "a",
                            "fields": {"t": {"selector": "a"}}})["retries"] == 3


def test_missing_config_file():
    with pytest.raises(ScraperError):
        load_config("nope.json")


# ------------------------------------------------------------------- extraction
def test_extract_all_field_types():
    html = open("sample_pages/page1.html", encoding="utf-8").read()
    items = extract_items(BeautifulSoup(html, "html.parser"), local_cfg(), "sample_pages/page1.html")
    first = items[0]
    assert first["title"] == "A Light in the Attic"   # attribute
    assert first["price"] == 51.77                      # number conversion
    assert first["rating"] == "Three"                   # regex on class attribute
    assert first["in_stock"] == "In stock"              # plain text
    assert first["link"] == "sample_pages/catalogue/a-light-in-the-attic_1000/index.html"
    assert items[3]["price"] == 1047.82                 # thousands separator


def test_missing_fields_become_blank_not_errors():
    html = open("sample_pages/page2.html", encoding="utf-8").read()
    items = extract_items(BeautifulSoup(html, "html.parser"), local_cfg(), "p")
    assert items[1]["price"] == "" and items[1]["rating"] == ""


# ---------------------------------------------------------------------- the run
def test_follows_pagination_over_local_pages():
    rows, pages = scrape(local_cfg(), sleep=NO_WAIT, log=lambda m: None)
    assert pages == 2 and len(rows) == 7


def test_max_pages_is_respected():
    rows, pages = scrape(local_cfg(max_pages=1), sleep=NO_WAIT, log=lambda m: None)
    assert pages == 1 and len(rows) == 4


def test_waits_between_pages_but_not_after_the_last():
    waits = []
    scrape(local_cfg(delay_seconds=2), sleep=waits.append, log=lambda m: None)
    assert waits == [2]  # one wait between the two pages


# ---------------------------------------------------------------- failure cases
def test_retries_a_temporary_failure():
    session = FakeSession(requests.ConnectionError("blip"), FakeResponse(text=PAGE))
    cfg = validate_config(REMOTE_CFG)
    assert "Book A" in fetch_page(cfg["url"], session, cfg, sleep=NO_WAIT)
    assert len(session.calls) == 2


def test_retries_server_errors_then_gives_up():
    session = FakeSession(*[FakeResponse(status=503)] * 3)
    cfg = validate_config(REMOTE_CFG)
    with pytest.raises(ScraperError, match="after 3 tries"):
        fetch_page(cfg["url"], session, cfg, sleep=NO_WAIT)
    assert len(session.calls) == 3


def test_404_is_not_retried():
    session = FakeSession(FakeResponse(status=404))
    cfg = validate_config(REMOTE_CFG)
    with pytest.raises(ScraperError, match="404"):
        fetch_page(cfg["url"], session, cfg, sleep=NO_WAIT)
    assert len(session.calls) == 1


def test_robots_txt_blocks_scraping():
    robots = FakeResponse(text="User-agent: *\nDisallow: /")
    session = FakeSession(robots)
    cfg = validate_config({**REMOTE_CFG, "respect_robots_txt": True})
    messages = []
    rows, pages = scrape(cfg, session=session, sleep=NO_WAIT, log=messages.append)
    assert rows == [] and pages == 0
    assert any("robots.txt" in m for m in messages)
    assert session.calls == ["https://example.com/robots.txt"]  # the page itself was never requested


def test_robots_txt_allows_scraping():
    session = FakeSession(FakeResponse(text="User-agent: *\nDisallow: /admin"), FakeResponse(text=PAGE))
    cfg = validate_config({**REMOTE_CFG, "respect_robots_txt": True})
    rows, pages = scrape(cfg, session=session, sleep=NO_WAIT, log=lambda m: None)
    assert rows == [{"title": "Book A"}]


def test_loop_in_next_links_does_not_run_forever():
    page = PAGE + '<a class="next" href="p1">again</a>'
    session = FakeSession(FakeResponse(text=page), FakeResponse(text=page))
    cfg = validate_config({**REMOTE_CFG, "next_page_selector": "a.next", "max_pages": 10})
    rows, pages = scrape(cfg, session=session, sleep=NO_WAIT, log=lambda m: None)
    assert pages == 1


# -------------------------------------------------------------------------- CLI
def test_cli_writes_csv(tmp_path):
    out = tmp_path / "out.csv"
    main(["config_local.json", "-o", str(out)])
    with open(out, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 7 and rows[0]["title"] == "A Light in the Attic"


def test_cli_writes_json(tmp_path):
    out = tmp_path / "out.json"
    main(["config_local.json", "-o", str(out)])
    assert len(json.loads(out.read_text(encoding="utf-8"))) == 7


def test_cli_bad_config_exits_cleanly(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(SystemExit):
        main([str(bad)])
