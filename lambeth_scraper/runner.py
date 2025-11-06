"""End-to-end orchestration for scraping the Lambeth register."""

from __future__ import annotations

import json
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, List, Optional, Tuple

from collections import defaultdict

from bs4 import BeautifulSoup
from patchright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from .browser import BrowserEnv
from .config import COUNCIL_NAME, RESULT_LINK_PATTERN, Settings, SnapshotMode, SOUP_PARSER
from .fetch import fetch_pages
from .logging_setup import get_logger
from .models import LicenceRecord
from .parse_common import extract_reference as parse_reference_from_text
from .parse_lambeth import (
    extract_address,
    extract_expiry,
    extract_licence_type,
    extract_occupancy,
)
from .search_flow import search_postcode
from .storage import (
    ensure_output_paths,
    save_html,
    slugify_for_filename,
    write_dataset,
    write_metadata,
    append_jsonl_record,
)

PostcodeResult = Tuple[dict[str, LicenceRecord], dict[str, dict], list[str]]


def _metadata_reference(entry: dict) -> Optional[str]:
    """Attempt to recover a licence reference from a metadata entry."""
    reference = entry.get("reference")
    if isinstance(reference, str) and reference.strip():
        return reference.strip().upper()

    for key in ("detail_url", "additional_url", "detail_html", "additional_html"):
        value = entry.get(key)
        if isinstance(value, str):
            extracted = parse_reference_from_text(value, pattern=RESULT_LINK_PATTERN.pattern)
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


def run(postcodes: Iterable[str], settings: Settings) -> List[LicenceRecord]:
    """Scrape the Lambeth register for the supplied postcodes."""
    postcodes = list(postcodes)
    rng = random.Random(settings.seed)
    rng.shuffle(postcodes)

    paths = ensure_output_paths(settings.output_root)
    logger = get_logger(f"{COUNCIL_NAME.lower()}.scraper", paths.log_dir, settings.log_level)

    logger.info(
        "Starting %s scrape for %s postcodes (concurrency=%s, snapshots=%s, jsonl=%s)",
        COUNCIL_NAME,
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
                if not isinstance(detail_url, str) or detail_url.strip().startswith("<"):
                    logger.debug(
                        "Existing record %s missing URL-style html field; scheduling refetch",
                        item.get("reference"),
                    )
                    continue
                try:
                    record = LicenceRecord(
                        council=item.get("council", COUNCIL_NAME),
                        reference=item["reference"],
                        address=item.get("address"),
                        occupancy=item.get("occupancy"),
                        licence_expiry=item.get("licence_expiry"),
                        licence_type=item.get("licence_type"),
                        detail_url=detail_url,
                    )
                except KeyError:
                    continue
                records_by_ref[record.reference] = record
                captured_refs.add(record.reference)

    if not settings.force_refresh and paths.jsonl_path.exists():
        try:
            with paths.jsonl_path.open("r", encoding="utf-8") as handle:
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
                    if not isinstance(reference, str):
                        continue
                    detail_url = item.get("detail_url") or item.get("html")
                    if not isinstance(detail_url, str) or detail_url.strip().startswith("<"):
                        continue
                    if reference not in records_by_ref:
                        record = LicenceRecord(
                            council=item.get("council", COUNCIL_NAME),
                            reference=reference,
                            address=item.get("address"),
                            occupancy=item.get("occupancy"),
                            licence_expiry=item.get("licence_expiry"),
                            licence_type=item.get("licence_type"),
                            detail_url=detail_url,
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
                reference = _metadata_reference(entry)
                if reference:
                    copy = dict(entry)
                    copy["reference"] = reference
                    metadata_by_ref[reference] = copy

    def _scrape_postcode(postcode: str) -> PostcodeResult:
        local_records: dict[str, LicenceRecord] = {}
        local_metadata: dict[str, dict] = {}
        local_failures: list[str] = []

        try:
            with BrowserEnv(settings, logger) as env:
                try:
                    rows = search_postcode(env, postcode, settings, _save_search_html)
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

                    address = extract_address(detail_soup) or row.address
                    licence_expiry = extract_expiry(detail_soup)
                    licence_type = extract_licence_type(detail_soup) or extract_licence_type(row.summary_text)
                    occupancy = extract_occupancy(additional_soup)

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

                        refreshed_rows = search_postcode(env, postcode, settings, _save_search_html)
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
                        council=COUNCIL_NAME,
                        reference=current_reference,
                        address=address,
                        occupancy=occupancy,
                        licence_expiry=licence_expiry,
                        licence_type=licence_type,
                        detail_url=row.detail_url,
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

                    if settings.refresh_interval and settings.refresh_interval > 0 and captures_since_refresh >= settings.refresh_interval and pending_rows:
                        logger.info(
                            "Refresh interval reached (%s); refreshing search results for %s",
                            settings.refresh_interval,
                            postcode,
                        )
                        refreshed_rows = search_postcode(env, postcode, settings, _save_search_html)
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
        failures_path.write_text("\n".join(failures), encoding="utf-8")
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
