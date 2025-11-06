"""Council-agnostic orchestration for the scrapers."""

from __future__ import annotations

import json
import os
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Pattern, Tuple

from bs4 import BeautifulSoup
from patchright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from .browser import BrowserEnv
from .config import BaseSettings, SnapshotMode, SOUP_PARSER
from .fetch import fetch_pages
from .logging import get_logger
from .models import LicenceRecord, ResultRow, ScrapePaths
from .parse import extract_reference
from .search import SaveHtmlCallback
from .storage import (
    append_jsonl_record,
    ensure_output_paths,
    save_html,
    slugify_for_filename,
    write_dataset,
    write_metadata,
)

ParseSearchResults = Callable[[str], List[ResultRow]]
ExtractAddress = Callable[[BeautifulSoup], Optional[str]]
ExtractExpiry = Callable[[BeautifulSoup], Optional[str]]
ExtractLicenceType = Callable[[BeautifulSoup | str | None], Optional[str]]
ExtractOccupancy = Callable[[Optional[BeautifulSoup]], Optional[int]]
ResolveAdditional = Callable[[BeautifulSoup, str], Optional[str]]
SearchPostcode = Callable[[BrowserEnv, str, BaseSettings, SaveHtmlCallback], List[ResultRow]]


@dataclass(frozen=True)
class CouncilSpec:
    name: str
    dataset_basename: str
    reference_pattern: Pattern[str]
    search_postcode: SearchPostcode
    parse_search_results: ParseSearchResults
    extract_address: ExtractAddress
    extract_expiry: ExtractExpiry
    extract_licence_type: ExtractLicenceType
    extract_occupancy: ExtractOccupancy
    resolve_additional_url: ResolveAdditional


PostcodeResult = Tuple[dict[str, LicenceRecord], dict[str, dict], list[str]]


def run_scraper(postcodes: Iterable[str], settings: BaseSettings, spec: CouncilSpec) -> List[LicenceRecord]:
    postcodes = [postcode.strip().upper() for postcode in postcodes if postcode.strip()]
    if not postcodes:
        return []

    if settings.seed is not None:
        import random

        rng = random.Random(settings.seed)
        rng.shuffle(postcodes)

    paths = ensure_output_paths(settings.output_root, spec.dataset_basename)
    logger = get_logger(f"{spec.name.lower()}.scraper", paths.log_dir, settings.log_level)

    logger.info(
        "Starting %s scrape for %s postcodes (concurrency=%s, snapshots=%s, jsonl=%s)",
        spec.name,
        len(postcodes),
        settings.concurrency,
        settings.snapshot_mode.value,
        settings.jsonl_output,
    )

    records_by_ref: dict[str, LicenceRecord] = {}
    metadata_by_ref: dict[str, dict] = {}
    failures: list[str] = []

    captured_refs_lock = threading.Lock()
    captured_refs: set[str] = set()

    jsonl_lock = threading.Lock() if settings.jsonl_output else None

    if settings.force_refresh and settings.jsonl_output and paths.jsonl_path.exists():
        paths.jsonl_path.unlink()

    def _save_search_html(postcode: str, page_index: int, html: str) -> None:
        if settings.snapshot_mode != SnapshotMode.ALL:
            return
        filename = f"{postcode}-{page_index:04d}.html"
        save_html(paths.search_dir / filename, html)

    if not settings.force_refresh and paths.json_path.exists():
        try:
            existing_dataset = json.loads(paths.json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Existing dataset at %s is not valid JSON; ignoring it", paths.json_path)
        else:
            for item in existing_dataset:
                if not isinstance(item, dict):
                    continue
                detail_url = item.get("detail_url") or item.get("html")
                reference = item.get("reference")
                if not isinstance(detail_url, str) or detail_url.strip().startswith("<"):
                    continue
                if not isinstance(reference, str):
                    continue
                record = LicenceRecord(
                    council=item.get("council", spec.name),
                    reference=reference,
                    detail_url=detail_url,
                    address=item.get("address"),
                    licence_type=item.get("licence_type"),
                    licence_expiry=item.get("licence_expiry"),
                    occupancy=item.get("occupancy"),
                )
                records_by_ref[record.reference] = record
                captured_refs.add(record.reference)

    if not settings.force_refresh and paths.jsonl_path.exists():
        try:
            with open(paths.jsonl_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(item, dict):
                        continue
                    reference = item.get("reference")
                    detail_url = item.get("detail_url") or item.get("html")
                    if not isinstance(reference, str) or not isinstance(detail_url, str):
                        continue
                    if detail_url.strip().startswith("<"):
                        continue
                    if reference not in records_by_ref:
                        record = LicenceRecord(
                            council=item.get("council", spec.name),
                            reference=reference,
                            detail_url=detail_url,
                            address=item.get("address"),
                            licence_type=item.get("licence_type"),
                            licence_expiry=item.get("licence_expiry"),
                            occupancy=item.get("occupancy"),
                        )
                        records_by_ref[reference] = record
                    captured_refs.add(reference)
        except FileNotFoundError:
            pass

    if not settings.force_refresh and paths.metadata_path.exists():
        try:
            existing_metadata = json.loads(paths.metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Existing metadata at %s is not valid JSON; ignoring it", paths.metadata_path)
        else:
            for entry in existing_metadata:
                if not isinstance(entry, dict):
                    continue
                reference = _metadata_reference(entry, spec.reference_pattern)
                if reference:
                    copy = dict(entry)
                    copy["reference"] = reference
                    metadata_by_ref[reference] = copy

    if settings.dry_run:
        return _run_dry_run(postcodes, settings, spec, paths, records_by_ref, metadata_by_ref, logger)

    def _scrape_postcode(postcode: str) -> PostcodeResult:
        local_records: dict[str, LicenceRecord] = {}
        local_metadata: dict[str, dict] = {}
        local_failures: list[str] = []

        try:
            with BrowserEnv(settings, logger) as env:
                try:
                    rows = spec.search_postcode(env, postcode, settings, _save_search_html)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Postcode %s failed: %s", postcode, exc)
                    local_failures.append(f"{postcode}: {exc}")
                    return local_records, local_metadata, local_failures

                if rows:
                    logger.info("Postcode %s returned %s rows", postcode, len(rows))
                else:
                    logger.info("Postcode %s returned no rows", postcode)
                    return local_records, local_metadata, local_failures

                pending_rows = [
                    row for row in rows if settings.force_refresh or row.reference not in records_by_ref
                ]
                if not pending_rows:
                    logger.info("All rows already captured for postcode %s", postcode)
                    return local_records, local_metadata, local_failures

                row_attempts: dict[str, int] = defaultdict(int)
                captures_since_refresh = 0

                while pending_rows:
                    row = pending_rows.pop(0)
                    current_reference = row.reference

                    if not settings.force_refresh:
                        with captured_refs_lock:
                            if current_reference in captured_refs:
                                logger.info("Skipping %s (already captured)", current_reference)
                                continue

                    slug = slugify_for_filename(current_reference)
                    detail_path = paths.licence_dir / f"{slug}.html"
                    additional_path = paths.additional_dir / f"{slug}.html"

                    detail_from_cache = not settings.force_refresh and detail_path.exists()
                    additional_from_cache = not settings.force_refresh and additional_path.exists()

                    try:
                        detail_html, additional_html, additional_url = fetch_pages(
                            env,
                            current_reference,
                            row.detail_url,
                            settings,
                            {"detail": detail_path, "additional": additional_path},
                            settings.force_refresh,
                            spec.resolve_additional_url,
                        )
                    except (PlaywrightTimeoutError, PlaywrightError) as exc:
                        logger.warning("Failed to fetch pages for %s: %s", current_reference, exc)
                        local_failures.append(f"{current_reference}: {exc}")
                        continue

                    if not detail_html:
                        local_failures.append(f"{current_reference}: missing detail HTML")
                        continue

                    if (
                        settings.snapshot_mode == SnapshotMode.ALL
                        and (settings.force_refresh or not detail_from_cache)
                    ):
                        save_html(detail_path, detail_html)
                    if (
                        settings.snapshot_mode == SnapshotMode.ALL
                        and additional_html
                        and (settings.force_refresh or not additional_from_cache)
                    ):
                        save_html(additional_path, additional_html)

                    detail_soup = BeautifulSoup(detail_html, SOUP_PARSER)
                    additional_soup = BeautifulSoup(additional_html, SOUP_PARSER) if additional_html else None

                    address = _clean_address(spec.extract_address(detail_soup)) or row.address
                    licence_expiry = spec.extract_expiry(detail_soup)
                    licence_type = spec.extract_licence_type(detail_soup) or spec.extract_licence_type(
                        row.summary_text
                    )
                    occupancy = spec.extract_occupancy(additional_soup)

                    if _is_access_denied(detail_html, address):
                        row_attempts[current_reference] += 1
                        attempt = row_attempts[current_reference]
                        if attempt > settings.access_denied_retries:
                            logger.warning(
                                "Access denied persisted for %s after %s attempts; marking as failure",
                                current_reference,
                                attempt - 1,
                            )
                            local_failures.append(f"{current_reference}: access denied")
                            continue

                        backoff = settings.access_denied_backoff * attempt
                        if backoff > 0:
                            logger.info(
                                "Access denied for %s; sleeping %.1fs before retry",
                                current_reference,
                                backoff,
                            )
                            env.sleep(backoff)

                        logger.info(
                            "Access denied for %s; refreshing search results (attempt %s/%s)",
                            current_reference,
                            attempt,
                            settings.access_denied_retries,
                        )
                        try:
                            env.restart_context()
                        except RuntimeError as exc:
                            logger.warning(
                                "Failed to restart browser context for %s: %s",
                                current_reference,
                                exc,
                            )
                            local_failures.append(f"{current_reference}: context restart failed")
                            continue

                        refreshed_rows = spec.search_postcode(env, postcode, settings, _save_search_html)
                        ref_map = {r.reference: r for r in refreshed_rows}
                        refreshed_row = ref_map.get(current_reference)
                        if refreshed_row:
                            pending_rows.insert(0, refreshed_row)
                            pending_rows = [ref_map.get(p.reference, p) for p in pending_rows]
                        else:
                            local_failures.append(f"{current_reference}: missing after refresh")
                        captures_since_refresh = 0
                        continue

                    record = LicenceRecord(
                        council=spec.name,
                        reference=current_reference,
                        detail_url=row.detail_url,
                        address=address,
                        occupancy=occupancy,
                        licence_expiry=licence_expiry,
                        licence_type=licence_type,
                    )

                    if not settings.force_refresh:
                        with captured_refs_lock:
                            if current_reference in captured_refs:
                                logger.info(
                                    "Discarding %s after fetch; captured by another worker",
                                    current_reference,
                                )
                                continue
                            captured_refs.add(current_reference)
                    else:
                        with captured_refs_lock:
                            captured_refs.add(current_reference)

                    local_records[current_reference] = record
                    if settings.jsonl_output:
                        append_jsonl_record(paths.jsonl_path, record, jsonl_lock)
                    local_metadata[current_reference] = {
                        "reference": current_reference,
                        "postcode": postcode,
                        "detail_url": row.detail_url,
                        "detail_html": (
                            detail_path.relative_to(paths.root).as_posix()
                            if settings.snapshot_mode == SnapshotMode.ALL
                            else None
                        ),
                        "additional_url": additional_url,
                        "additional_html": (
                            additional_path.relative_to(paths.root).as_posix()
                            if settings.snapshot_mode == SnapshotMode.ALL
                            and (additional_html or additional_path.exists())
                            else None
                        ),
                    }

                    logger.info(
                        "Captured licence %s (postcode %s, cached_detail=%s)",
                        current_reference,
                        postcode,
                        detail_from_cache,
                    )

                    row_attempts.pop(current_reference, None)
                    captures_since_refresh += 1

                    if (
                        settings.refresh_interval
                        and settings.refresh_interval > 0
                        and captures_since_refresh >= settings.refresh_interval
                        and pending_rows
                    ):
                        logger.info(
                            "Refresh interval reached (%s); refreshing search results for %s",
                            settings.refresh_interval,
                            postcode,
                        )
                        refreshed_rows = spec.search_postcode(env, postcode, settings, _save_search_html)
                        ref_map = {r.reference: r for r in refreshed_rows}
                        pending_rows = [ref_map.get(p.reference, p) for p in pending_rows]
                        captures_since_refresh = 0

        except KeyboardInterrupt:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected failure while scraping postcode %s: %s", postcode, exc)
            local_failures.append(f"{postcode}: {exc}")

        return local_records, local_metadata, local_failures

    interrupted = False
    executor: ThreadPoolExecutor | None = None
    try:
        if settings.concurrency <= 1:
            for postcode in postcodes:
                local_records, local_metadata, local_failures = _scrape_postcode(postcode)
                records_by_ref.update(local_records)
                metadata_by_ref.update(local_metadata)
                failures.extend(local_failures)
        else:
            logger.info(
                "Executing scrape with %s workers across %s postcodes",
                settings.concurrency,
                len(postcodes),
            )
            executor = ThreadPoolExecutor(max_workers=settings.concurrency)
            future_to_postcode = {
                executor.submit(_scrape_postcode, postcode): postcode for postcode in postcodes
            }
            try:
                for future in as_completed(future_to_postcode):
                    postcode = future_to_postcode[future]
                    try:
                        local_records, local_metadata, local_failures = future.result()
                    except KeyboardInterrupt:
                        interrupted = True
                        logger.info("Interrupted while waiting for postcode %s; cancelling remaining work", postcode)
                        raise
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("Worker for postcode %s raised an error: %s", postcode, exc)
                        failures.append(f"{postcode}: {exc}")
                        continue

                    records_by_ref.update(local_records)
                    metadata_by_ref.update(local_metadata)
                    failures.extend(local_failures)
            except KeyboardInterrupt:
                for fut in future_to_postcode:
                    fut.cancel()
                interrupted = True
                logger.info("Interrupted by user; shutting down remaining workers")
            finally:
                if executor is not None:
                    executor.shutdown(wait=False, cancel_futures=True)
                    executor = None
    except KeyboardInterrupt:
        interrupted = True
        logger.info("Keyboard interrupt received; attempting graceful shutdown")
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)
            executor = None

    ordered_records = [records_by_ref[key] for key in sorted(records_by_ref)]
    if settings.json_array_output:
        write_dataset(ordered_records, paths.json_path)

    if interrupted:
        logger.warning("Scrape interrupted; returning partial dataset with %s records", len(ordered_records))

    metadata_entries = [metadata_by_ref[key] for key in sorted(metadata_by_ref)]
    if metadata_entries:
        write_metadata(metadata_entries, paths.metadata_path)

    if failures:
        failures_path = paths.log_dir / "fetch_failures.log"
        os.makedirs(failures_path.parent, exist_ok=True)
        with open(failures_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(failures))
        logger.warning("Finished with %s failures; see %s", len(failures), failures_path.name)
    else:
        logger.info("Scrape completed without recorded failures")

    if settings.json_array_output:
        logger.info("Wrote %s records to %s", len(ordered_records), paths.json_path)
    else:
        logger.info("Captured %s records (JSON array output disabled)", len(ordered_records))

    if settings.jsonl_output:
        logger.info("Streaming output available at %s", paths.jsonl_path)

    return ordered_records


def _metadata_reference(entry: dict, pattern: Pattern[str]) -> Optional[str]:
    reference = entry.get("reference")
    if isinstance(reference, str) and reference.strip():
        return reference.strip().upper()

    for key in ("detail_url", "additional_url", "detail_html", "additional_html"):
        value = entry.get(key)
        if isinstance(value, str):
            extracted = extract_reference(value, pattern=pattern.pattern)
            if extracted:
                return extracted
    return None


def _is_access_denied(detail_html: str, address: Optional[str]) -> bool:
    content = (detail_html or "").lower()
    if "access denied" in content:
        return True
    if "support links" in content:
        return True
    if address and "support links" in address.lower():
        return True
    return False


def _clean_address(address: Optional[str]) -> Optional[str]:
    if not address:
        return None
    stripped = address.strip()
    if not stripped:
        return None
    if stripped.startswith("http"):
        return None
    return stripped


def _run_dry_run(
    postcodes: List[str],
    settings: BaseSettings,
    spec: CouncilSpec,
    paths: ScrapePaths,
    records_by_ref: dict[str, LicenceRecord],
    metadata_by_ref: dict[str, dict],
    logger,
) -> List[LicenceRecord]:
    if not settings.fixture_dir:
        raise ValueError("Dry-run mode requires fixture_dir to be set on settings")

    for postcode in postcodes:
        search_fixture = _fixture_path(settings.fixture_dir, f"{postcode}_search.html")
        if not search_fixture.exists():
            logger.warning("Missing search fixture for %s; skipping", postcode)
            continue
        html = search_fixture.read_text(encoding="utf-8")
        rows = spec.parse_search_results(html)
        logger.info("Loaded %s rows for %s from fixture", len(rows), postcode)

        for index, row in enumerate(rows, start=1):
            detail_path = _fixture_path(settings.fixture_dir, f"{row.reference}_detail.html")
            additional_path = _fixture_path(settings.fixture_dir, f"{row.reference}_additional.html")

            if not detail_path.exists():
                logger.warning("Missing detail fixture for %s; skipping", row.reference)
                continue

            detail_html = detail_path.read_text(encoding="utf-8")
            additional_html = additional_path.read_text(encoding="utf-8") if additional_path.exists() else None

            detail_soup = BeautifulSoup(detail_html, SOUP_PARSER)
            additional_soup = BeautifulSoup(additional_html, SOUP_PARSER) if additional_html else None

            address = _clean_address(spec.extract_address(detail_soup)) or row.address
            licence_expiry = spec.extract_expiry(detail_soup)
            licence_type = spec.extract_licence_type(detail_soup) or spec.extract_licence_type(
                row.summary_text
            )
            occupancy = spec.extract_occupancy(additional_soup)

            record = LicenceRecord(
                council=spec.name,
                reference=row.reference,
                detail_url=row.detail_url,
                address=address,
                occupancy=occupancy,
                licence_expiry=licence_expiry,
                licence_type=licence_type,
            )
            records_by_ref[row.reference] = record
            metadata_by_ref[row.reference] = {
                "reference": row.reference,
                "postcode": postcode,
                "detail_fixture": str(detail_path),
                "additional_fixture": str(additional_path) if additional_html else None,
            }

            logger.info(
                "Fixture %s/%s produced licence %s",
                index,
                len(rows),
                row.reference,
            )

    ordered_records = [records_by_ref[key] for key in sorted(records_by_ref)]
    if settings.json_array_output:
        write_dataset(ordered_records, paths.json_path)
    if metadata_by_ref:
        write_metadata([metadata_by_ref[key] for key in sorted(metadata_by_ref)], paths.metadata_path)
    logger.info("Dry-run completed with %s records", len(ordered_records))
    return ordered_records


def _fixture_path(root: Path, name: str) -> Path:
    return root / name
