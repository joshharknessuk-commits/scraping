# Southwark landlord licence scraper

This project provides a modular Python scraper for the Southwark Council landlord licence public register. It combines `requests`
for HTTP fetching, BeautifulSoup for HTML parsing, and Playwright for a human-in-the-loop CAPTCHA workflow. Results are emitted as
both JSON Lines (streaming) and aggregated JSON files for downstream analysis.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python -m src.main --postcode SE1 --max-pages 100 --use-playwright
```

- `--postcode` is required and is passed straight to the council search box.
- `--max-pages` controls pagination depth; omit to crawl until the register stops returning new links.
- Pass `--resume` to skip URLs that already exist in `out/licences.jsonl`.
- Add `--use-playwright` to launch a headed Chromium session so you can solve the CAPTCHA manually and persist the cookies for
  subsequent `requests` calls.

## Outputs

Scraped artefacts are written under `out/`:

- `out/licences.jsonl`: one JSON record per licence written as it is scraped.
- `out/licences.json`: aggregated list of all scraped licences (including resumed records).
- `out/licence_links.csv`: optional history of discovered detail-page URLs.
- `out/cookies.json`: Playwright-exported cookies that allow the scraper to reuse a CAPTCHA-cleared session.

## Ethical considerations

The Southwark register uses reCAPTCHA to protect against automated scraping. This project does **not** attempt to bypass that
protection. Instead, run the scraper with `--use-playwright`, manually solve the CAPTCHA in the opened Chromium window, and press
Enter in the terminal to continue. Respect the built-in rate limiting (`0.8s` between requests by default) and avoid overwhelming
the council systems.

## Testing

The repository includes a lightweight pytest suite exercising the AjaxCom parsing utilities and the HTML parsers:

```bash
pytest
```

## Project layout

```
requirements.txt
README.md
src/
  ajaxcom.py
  config.py
  detail_parser.py
  main.py
  outputter.py
  playwright_capture.py
  sessioner.py
  utils.py
  __init__.py
tests/
  test_ajaxcom.py
  test_parsers.py
```
