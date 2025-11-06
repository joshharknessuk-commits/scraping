"""Base orchestration helpers shared by council scrapers."""

from __future__ import annotations

import json
import random
import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple, TypeVar

from .browser import BrowserEnv
from .config import ScraperSettings, SnapshotMode
from .logging import configure_logging
from .models import LicenceRecord, ResultRow
from .storage import (
    OutputPaths,
    append_jsonl_record,
    build_output_paths,
    save_html,
    slugify_for_filename,
    write_dataset,
    write_metadata,
)

T = TypeVar("T")

PostcodeResult = Tuple[dict[str, LicenceRecord], dict[str, dict], List[str]]


@dataclass(slots=True)
class FetchOutcome:
    detail_html: Optional[str]
    additional_html: Optional[str]
    additional_url: Optional[str]
    detail_from_cache: bool = False
    additional_from_cache: bool = False


class _DryRunEnv:
    """Minimal stand-in for ``BrowserEnv`` used during dry runs."""

    def __init__(self, settings: ScraperSettings, logger) -> None:
        self.settings = settings
        self.logger = logger

    def __enter__(self) -> "_DryRunEnv":
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        return None

    def throttle(self) -> None:  # pragma: no cover - trivial
        return None

    def sleep(self, seconds: float) -> None:  # pragma: no cover - trivial
        return None

    def wait_for_idle(self, page) -> None:  # pragma: no cover - dry run only
        return None

    def with_retries(self, fn: Callable[[], T], *, label: str, attempts=None, base_delay=None) -> T:
        return fn()

    def restart_context(self) -> None:  # pragma: no cover - dry run only
        return None


class BasePostcodeScraper(ABC):
    """Common orchestration shared by individual council scrapers."""

    def __init__(self, council_name: str, settings: ScraperSettings) -> None:
        self.council_name = council_name
        self.settings = settings
        self.paths: OutputPaths = build_output_paths(settings)
        self.logger = configure_logging(
            f"{settings.council_slug}.scraper", self.paths.log_dir, settings.log_level
        )
        self._jsonl_lock = threading.Lock() if settings.jsonl_output else None
        if settings.force_refresh and settings.jsonl_output and self.paths.jsonl_path.exists():
            self.paths.jsonl_path.unlink()

    # -- Hooks -----------------------------------------------------------------

    @abstractmethod
    def search_postcode(
        self,
        env: BrowserEnv,
        postcode: str,
        save_html: Callable[[str, int, str], None],
    ) -> List[ResultRow]:
        """Return search rows for ``postcode``."""

    @abstractmethod
    def fetch_record(
        self,
        env: BrowserEnv,
        row: ResultRow,
        postcode: str,
        detail_path: Path,
        additional_path: Path,
    ) -> FetchOutcome:
        """Retrieve HTML required to parse ``row``."""

    @abstractmethod
    def parse_record(
        self,
        row: ResultRow,
        outcome: FetchOutcome,
        postcode: str,
    ) -> LicenceRecord:
        """Create a ``LicenceRecord`` from the fetched HTML."""

    @abstractmethod
    def detect_access_denied(self, detail_html: str, row: ResultRow) -> bool:
        """Return ``True`` when the fetched detail page indicates access denial."""

    def build_metadata(
        self,
        record: LicenceRecord,
        row: ResultRow,
        outcome: FetchOutcome,
        detail_path: Path,
        additional_path: Path,
        postcode: str,
    ) -> dict:
        """Construct metadata for the captured record."""

        metadata = {
            "reference": record.reference,
            "postcode": postcode,
            "detail_url": row.detail_url,
            "detail_html": (
                detail_path.relative_to(self.paths.root).as_posix()
                if self.settings.snapshot_mode == SnapshotMode.ALL
                else None
            ),
            "additional_url": outcome.additional_url,
            "additional_html": (
                additional_path.relative_to(self.paths.root).as_posix()
                if self.settings.snapshot_mode == SnapshotMode.ALL
                and (
                    outcome.additional_html
                    or (self.settings.snapshot_mode == SnapshotMode.ALL and additional_path.exists())
                )
                else None
            ),
        }
        return metadata

    # -- Public API ------------------------------------------------------------

    def run(self, postcodes: Iterable[str]) -> List[LicenceRecord]:
        postcodes = list(postcodes)
        if not postcodes:
            self.logger.info("No postcodes supplied; nothing to do")
            return []

        rng = random.Random(self.settings.seed)
        rng.shuffle(postcodes)

        self.logger.info(
            "Starting scrape for %s postcodes (concurrency=%s, snapshots=%s, jsonl=%s)",
            len(postcodes),
            self.settings.concurrency,
            self.settings.snapshot_mode.value,
            self.settings.jsonl_output,
        )

        records_by_ref: dict[str, LicenceRecord] = {}
        metadata_by_ref: dict[str, dict] = {}
        failures: list[str] = []
        captured_refs: set[str] = set()
        captured_refs_lock = threading.Lock()

        self._load_existing_records(records_by_ref, captured_refs)

        def _save_search_html(postcode: str, page_index: int, html: str) -> None:
            if self.settings.snapshot_mode != SnapshotMode.ALL:
                return
            filename = f"{postcode}-{page_index:04d}.html"
            save_html(self.paths.search_dir / filename, html)

        def _scrape(postcode: str) -> PostcodeResult:
            return self._scrape_postcode(
                postcode,
                records_by_ref,
                captured_refs,
                captured_refs_lock,
                _save_search_html,
            )

        interrupted = False
        executor: ThreadPoolExecutor | None = None
        try:
            if self.settings.concurrency <= 1:
                for postcode in postcodes:
                    local_records, local_metadata, local_failures = _scrape(postcode)
                    records_by_ref.update(local_records)
                    metadata_by_ref.update(local_metadata)
                    failures.extend(local_failures)
            else:
                executor = ThreadPoolExecutor(max_workers=self.settings.concurrency)
                future_to_postcode = {
                    executor.submit(_scrape, postcode): postcode for postcode in postcodes
                }
                try:
                    for future in as_completed(future_to_postcode):
                        postcode = future_to_postcode[future]
                        try:
                            local_records, local_metadata, local_failures = future.result()
                        except KeyboardInterrupt:
                            interrupted = True
                            self.logger.info(
                                "Interrupted while waiting for postcode %s; cancelling remaining work",
                                postcode,
                            )
                            raise
                        except Exception as exc:  # noqa: BLE001
                            self.logger.exception(
                                "Worker for postcode %s raised an error: %s", postcode, exc
                            )
                            failures.append(f"{postcode}: {exc}")
                            continue

                        records_by_ref.update(local_records)
                        metadata_by_ref.update(local_metadata)
                        failures.extend(local_failures)
                except KeyboardInterrupt:
                    interrupted = True
                    for future in future_to_postcode:
                        future.cancel()
                    self.logger.info("Interrupted by user; shutting down workers")
                finally:
                    if executor is not None:
                        executor.shutdown(wait=False, cancel_futures=True)
                        executor = None
        except KeyboardInterrupt:
            interrupted = True
            self.logger.info("Keyboard interrupt received; stopping scrape")
            if executor is not None:
                executor.shutdown(wait=False, cancel_futures=True)
                executor = None

        ordered_records = [records_by_ref[key] for key in sorted(records_by_ref)]
        if self.settings.json_array_output:
            write_dataset(ordered_records, self.paths.json_path)
        metadata_entries = [metadata_by_ref[key] for key in sorted(metadata_by_ref)]
        if metadata_entries:
            write_metadata(metadata_entries, self.paths.metadata_path)

        if failures:
            failures_path = self.paths.log_dir / "fetch_failures.log"
            failures_path.write_text("\n".join(failures), encoding="utf-8")
            self.logger.warning("Finished with %s failures; see %s", len(failures), failures_path.name)
        else:
            self.logger.info("Scrape completed without recorded failures")

        if interrupted:
            self.logger.warning(
                "Scrape interrupted; returning partial dataset with %s records",
                len(ordered_records),
            )

        if self.settings.json_array_output:
            self.logger.info("Wrote %s records to %s", len(ordered_records), self.paths.json_path)
        else:
            self.logger.info("Captured %s records (JSON array output disabled)", len(ordered_records))

        if self.settings.jsonl_output:
            self.logger.info("Streaming output available at %s", self.paths.jsonl_path)

        return ordered_records

    # -- Internal helpers ------------------------------------------------------

    def _scrape_postcode(
        self,
        postcode: str,
        records_by_ref: dict[str, LicenceRecord],
        captured_refs: set[str],
        captured_refs_lock: threading.Lock,
        save_search_html: Callable[[str, int, str], None],
    ) -> PostcodeResult:
        local_records: dict[str, LicenceRecord] = {}
        local_metadata: dict[str, dict] = {}
        local_failures: list[str] = []

        try:
            env_manager = _DryRunEnv(self.settings, self.logger) if self.settings.dry_run else BrowserEnv(self.settings, self.logger)
            with env_manager as env:
                try:
                    rows = self.search_postcode(env, postcode, save_search_html)
                except Exception as exc:  # noqa: BLE001
                    self.logger.exception("Postcode %s failed during search: %s", postcode, exc)
                    local_failures.append(f"{postcode}: {exc}")
                    return local_records, local_metadata, local_failures

                if not rows:
                    self.logger.info("Postcode %s returned no rows", postcode)
                    return local_records, local_metadata, local_failures

                self.logger.info("Postcode %s returned %s rows", postcode, len(rows))
                pending_rows = [
                    row for row in rows if self.settings.force_refresh or row.reference not in records_by_ref
                ]
                if not pending_rows:
                    self.logger.info("All rows already captured for postcode %s", postcode)
                    return local_records, local_metadata, local_failures

                row_attempts: dict[str, int] = defaultdict(int)
                captures_since_refresh = 0

                while pending_rows:
                    row = pending_rows.pop(0)
                    reference = row.reference

                    if not self.settings.force_refresh:
                        with captured_refs_lock:
                            if reference in captured_refs:
                                self.logger.info("Skipping %s (already captured)", reference)
                                continue

                    slug = slugify_for_filename(reference)
                    detail_path = self.paths.detail_dir / f"{slug}.html"
                    additional_path = self.paths.additional_dir / f"{slug}.html"

                    try:
                        outcome = self.fetch_record(env, row, postcode, detail_path, additional_path)
                    except Exception as exc:  # noqa: BLE001
                        self.logger.warning("Failed to fetch pages for %s: %s", reference, exc)
                        local_failures.append(f"{reference}: {exc}")
                        continue

                    if not outcome.detail_html:
                        local_failures.append(f"{reference}: missing detail HTML")
                        continue

                    if self.detect_access_denied(outcome.detail_html, row):
                        row_attempts[reference] += 1
                        attempt = row_attempts[reference]
                        if attempt > self.settings.access_denied_retries:
                            self.logger.warning(
                                "Access denied persisted for %s after %s attempts; giving up",
                                reference,
                                attempt - 1,
                            )
                            local_failures.append(f"{reference}: access denied")
                            continue

                        backoff = self.settings.access_denied_backoff * attempt
                        if backoff > 0:
                            self.logger.info(
                                "Access denied for %s; sleeping %.1fs before retry",
                                reference,
                                backoff,
                            )
                            env.sleep(backoff)
                        try:
                            env.restart_context()
                        except RuntimeError as exc:
                            self.logger.warning(
                                "Failed to restart browser context for %s: %s", reference, exc
                            )
                            local_failures.append(f"{reference}: context restart failed")
                            continue

                        refreshed_rows = self.search_postcode(env, postcode, save_search_html)
                        ref_map = {r.reference: r for r in refreshed_rows}
                        refreshed_row = ref_map.get(reference)
                        if refreshed_row:
                            pending_rows.insert(0, refreshed_row)
                            pending_rows = [ref_map.get(p.reference, p) for p in pending_rows]
                        else:
                            local_failures.append(f"{reference}: missing after refresh")
                        captures_since_refresh = 0
                        continue

                    record = self.parse_record(row, outcome, postcode)

                    if not self.settings.force_refresh:
                        with captured_refs_lock:
                            if reference in captured_refs:
                                self.logger.info(
                                    "Discarding %s after fetch; captured by another worker",
                                    reference,
                                )
                                continue
                            captured_refs.add(reference)
                    else:
                        with captured_refs_lock:
                            captured_refs.add(reference)

                    if self.settings.jsonl_output:
                        append_jsonl_record(self.paths.jsonl_path, record, self._jsonl_lock)

                    if (
                        self.settings.snapshot_mode == SnapshotMode.ALL
                        and outcome.detail_html
                        and (self.settings.force_refresh or not outcome.detail_from_cache)
                    ):
                        save_html(detail_path, outcome.detail_html)
                    if (
                        self.settings.snapshot_mode == SnapshotMode.ALL
                        and outcome.additional_html
                        and (self.settings.force_refresh or not outcome.additional_from_cache)
                    ):
                        save_html(additional_path, outcome.additional_html)

                    self.logger.info(
                        "Captured licence %s (postcode %s, cached_detail=%s)",
                        reference,
                        postcode,
                        outcome.detail_from_cache,
                    )

                    row_attempts.pop(reference, None)
                    captures_since_refresh += 1

                    metadata = self.build_metadata(
                        record,
                        row,
                        outcome,
                        detail_path,
                        additional_path,
                        postcode,
                    )
                    local_metadata[reference] = metadata

                    if (
                        self.settings.refresh_interval
                        and self.settings.refresh_interval > 0
                        and captures_since_refresh >= self.settings.refresh_interval
                        and pending_rows
                    ):
                        self.logger.info(
                            "Refresh interval reached (%s); refreshing search results for %s",
                            self.settings.refresh_interval,
                            postcode,
                        )
                        refreshed_rows = self.search_postcode(env, postcode, save_search_html)
                        ref_map = {r.reference: r for r in refreshed_rows}
                        pending_rows = [ref_map.get(p.reference, p) for p in pending_rows]
                        captures_since_refresh = 0
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Unexpected failure while scraping postcode %s: %s", postcode, exc)
            local_failures.append(f"{postcode}: {exc}")

        return local_records, local_metadata, local_failures

    def _load_existing_records(
        self, records_by_ref: dict[str, LicenceRecord], captured_refs: set[str]
    ) -> None:
        if self.settings.force_refresh:
            return
        if not self.paths.json_path.exists():
            return
        try:
            existing_dataset = json.loads(self.paths.json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.logger.warning(
                "Existing dataset at %s is not valid JSON; ignoring it", self.paths.json_path
            )
            return
        for item in existing_dataset:
            if not isinstance(item, dict):
                continue
            reference = item.get("reference")
            detail_url = item.get("detail_url")
            if not isinstance(reference, str) or not isinstance(detail_url, str):
                continue
            record = LicenceRecord(
                council=item.get("council", self.council_name),
                reference=reference,
                address=item.get("address"),
                occupancy=item.get("occupancy"),
                licence_expiry=item.get("licence_expiry"),
                licence_type=item.get("licence_type"),
                detail_url=detail_url,
            )
            records_by_ref[reference] = record
            captured_refs.add(reference)
