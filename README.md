# Southwark licence scraping

This folder now contains a single requests + BeautifulSoup pipeline for collecting Southwark licence data from the Metastreet public register.

## Prerequisites

```bash
cd packages/housing-data
python -m venv .venv
source .venv/bin/activate
pip install -r src/scraping/requirements.txt
```

## Run the scraper

```bash
python src/scraping/southwark_fetch.py
```

The scraper issues HTTP requests per postcode, saves the underlying HTML, and parses the responses offline. It writes:

- Search results to `src/scraping/data/southwark/search_pages/`
- Licence detail pages to `src/scraping/data/southwark/licence_pages/`
- Additional info pages to `src/scraping/data/southwark/additional_pages/`
- Structured data to `src/scraping/data/southwark/southwark_licences.json` and `.csv`
- Debug HTML for recent errors to `src/scraping/data/southwark/debug.html`
- Fetch logs to `src/scraping/data/southwark/logs/`

You can re-run `python src/scraping/southwark_parse.py` if you need to reprocess previously saved HTML.

## Postcode source

`southwark_postcodes.txt` holds the SE postcode list used by the scraper. Update the file if the coverage needs to change.
