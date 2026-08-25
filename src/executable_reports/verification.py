"""Fast browser verification and intentionally unstable agent diagnostics."""

from __future__ import annotations

import contextlib
import datetime as dt
import os
import re
import shutil
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from .artifacts import HTML, VERIFY_RECEIPT, VERIFY_SCREENSHOT
from .inventory import sha256

SCHEMA_VERSION = 1
DEFAULT_VIEWPORT = (1440, 900)
MAX_DETAILS = 25
DIAGNOSTIC_API_STABILITY = "internal-pre-1.0"


class VerificationError(RuntimeError):
    pass


class BrowserUnavailable(VerificationError):
    pass


def _bounded(value: Any, limit: int = 8_000) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n... <truncated {len(text) - limit} characters>"


_LOOPBACK = re.compile(r"https?://(?:127\.0\.0\.1|localhost|\[::1\]):\d+/([^\s\"']*)")


def _portable_text(value: str) -> str:
    return _LOOPBACK.sub(lambda match: unquote(match.group(1)) or ".", value)


def _portable_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        value = unquote(parsed.path).lstrip("/") or "."
        if parsed.query:
            value += f"?{parsed.query}"
        if parsed.fragment:
            value += f"#{parsed.fragment}"
    return _bounded(value, 2_000)


def _portable(value: Any, key: str | None = None) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _portable(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_portable(item, key) for item in value]
    if isinstance(value, str) and key in {"url", "src", "name"}:
        return _portable_url(value)
    return value


@dataclass
class BrowserEvents:
    console: list[dict[str, Any]] = field(default_factory=list)
    page_errors: list[dict[str, Any]] = field(default_factory=list)
    request_failures: list[dict[str, Any]] = field(default_factory=list)
    response_errors: list[dict[str, Any]] = field(default_factory=list)
    dialogs: list[dict[str, Any]] = field(default_factory=list)
    crashes: list[dict[str, Any]] = field(default_factory=list)
    requests_total: int = 0
    _pending: dict[int, dict[str, Any]] = field(default_factory=dict)

    @staticmethod
    def _append(target: list[dict[str, Any]], value: dict[str, Any]) -> None:
        if len(target) < MAX_DETAILS:
            target.append(value)

    def on_console(self, message: Any) -> None:
        location = getattr(message, "location", None) or {}
        self._append(
            self.console,
            {
                "type": str(getattr(message, "type", "log")),
                "text": _bounded(getattr(message, "text", ""), 4_000),
                "location": {
                    "url": _bounded(location.get("url", ""), 2_000),
                    "line": int(location.get("lineNumber", 0) or 0),
                    "column": int(location.get("columnNumber", 0) or 0),
                },
            },
        )

    def on_page_error(self, error: Any) -> None:
        self._append(
            self.page_errors,
            {
                "message": _bounded(getattr(error, "message", error), 4_000),
                "stack": _bounded(getattr(error, "stack", ""), 8_000),
            },
        )

    def on_request(self, request: Any) -> None:
        self.requests_total += 1
        self._pending[id(request)] = {
            "url": _bounded(getattr(request, "url", ""), 2_000),
            "method": str(getattr(request, "method", "GET")),
            "resource_type": str(getattr(request, "resource_type", "")),
        }

    def on_request_finished(self, request: Any) -> None:
        self._pending.pop(id(request), None)

    def on_request_failed(self, request: Any) -> None:
        value = self._pending.pop(id(request), {})
        failure = getattr(request, "failure", None)
        if callable(failure):
            failure = failure()
        value["error"] = _bounded(failure or "request failed", 4_000)
        self._append(self.request_failures, value)

    def on_response(self, response: Any) -> None:
        status = int(getattr(response, "status", 0) or 0)
        if status >= 400:
            request = getattr(response, "request", None)
            self._append(
                self.response_errors,
                {
                    "status": status,
                    "url": _bounded(getattr(response, "url", ""), 2_000),
                    "method": str(getattr(request, "method", "GET")),
                },
            )

    def on_dialog(self, dialog: Any) -> None:
        self._append(
            self.dialogs,
            {
                "type": str(getattr(dialog, "type", "dialog")),
                "message": _bounded(getattr(dialog, "message", ""), 4_000),
            },
        )
        with contextlib.suppress(Exception):
            dialog.dismiss()

    def on_crash(self, _page: Any) -> None:
        self._append(self.crashes, {"message": "browser page crashed"})

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def snapshot(self) -> dict[str, Any]:
        return {
            "requests_total": self.requests_total,
            "pending_requests": list(self._pending.values())[:MAX_DETAILS],
            "console": self.console,
            "page_errors": self.page_errors,
            "request_failures": self.request_failures,
            "response_errors": self.response_errors,
            "dialogs": self.dialogs,
            "crashes": self.crashes,
        }


@dataclass
class BrowserSession:
    page: Any
    events: BrowserEvents
    response_status: int | None
    browser: dict[str, Any]
    timing_ms: dict[str, int]


def _parse_range(header: str, size: int) -> tuple[int, int] | None:
    if size <= 0 or not header.startswith("bytes=") or "," in header:
        return None
    start_text, separator, end_text = header[6:].strip().partition("-")
    if not separator:
        return None
    try:
        if not start_text:
            suffix = int(end_text)
            return (max(0, size - suffix), size - 1) if suffix > 0 else None
        start = int(start_text)
        end = int(end_text) if end_text else size - 1
    except ValueError:
        return None
    if start < 0 or end < start or start >= size:
        return None
    return start, min(end, size - 1)


class _ReportHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".arrow": "application/vnd.apache.arrow.file",
        ".feather": "application/vnd.apache.arrow.file",
        ".ipc": "application/vnd.apache.arrow.file",
        ".parquet": "application/vnd.apache.parquet",
        ".mjs": "text/javascript",
        ".wasm": "application/wasm",
    }
    _range: tuple[int, int] | None = None

    def send_head(self) -> Any:
        self._range = None
        path = self.translate_path(self.path)
        if urlsplit(self.path).path == "/favicon.ico" and not os.path.isfile(path):
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        header = self.headers.get("Range")
        if not header:
            return super().send_head()
        if not os.path.isfile(path):
            return super().send_head()
        stream = open(path, "rb")
        stat = os.fstat(stream.fileno())
        selected = _parse_range(header, stat.st_size)
        if selected is None:
            stream.close()
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{stat.st_size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        start, end = selected
        self._range = selected
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{stat.st_size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        stream.seek(start)
        return stream

    def copyfile(self, source: Any, outputfile: Any) -> None:
        if self._range is None:
            return super().copyfile(source, outputfile)
        start, end = self._range
        source.seek(start)
        remaining = end - start + 1
        while remaining:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)

    def end_headers(self) -> None:
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, _format: str, *_args: Any) -> None:
        return


@contextlib.contextmanager
def serve_report(root: str | Path) -> Iterator[str]:
    handler = partial(_ReportHandler, directory=str(Path(root).expanduser().resolve()))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    thread = threading.Thread(
        target=lambda: server.serve_forever(poll_interval=0.01), daemon=True
    )
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}/{quote(HTML)}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def _load_playwright() -> tuple[Any, type[Exception], type[Exception]]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as error:
        raise BrowserUnavailable(
            "report verify needs the Python package 'playwright'; install it in the report "
            "CLI environment, then provide Chrome/Chromium or run 'playwright install chromium'"
        ) from error
    return sync_playwright, PlaywrightError, PlaywrightTimeoutError


def resolve_browser_path(explicit: str | Path | None = None) -> tuple[Path | None, str]:
    if explicit or os.environ.get("REPORT_BROWSER_PATH"):
        raw = explicit or os.environ["REPORT_BROWSER_PATH"]
        path = Path(raw).expanduser().resolve()
        if not path.is_file():
            raise BrowserUnavailable("configured browser executable does not exist; check --browser or REPORT_BROWSER_PATH")
        return path, "explicit" if explicit else "environment"
    for name in (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "microsoft-edge",
        "msedge",
    ):
        if found := shutil.which(name):
            return Path(found).resolve(), "system"
    return None, "playwright"


def _bind_events(page: Any, events: BrowserEvents) -> None:
    page.on("console", events.on_console)
    page.on("pageerror", events.on_page_error)
    page.on("request", events.on_request)
    page.on("requestfinished", events.on_request_finished)
    page.on("requestfailed", events.on_request_failed)
    page.on("response", events.on_response)
    page.on("dialog", events.on_dialog)
    page.on("crash", events.on_crash)


def _settle(page: Any, events: BrowserEvents, maximum_ms: int) -> int:
    started = time.perf_counter()
    quiet_since: float | None = None
    while (time.perf_counter() - started) * 1000 < maximum_ms:
        now = time.perf_counter()
        if events.pending_count:
            quiet_since = None
        elif quiet_since is None:
            quiet_since = now
        elif (now - quiet_since) * 1000 >= 100:
            break
        page.wait_for_timeout(25)
    return round((time.perf_counter() - started) * 1000)


@contextlib.contextmanager
def browser_session(
    root: str | Path,
    *,
    browser_path: str | Path | None = None,
    timeout_seconds: float = 15,
    viewport: tuple[int, int] = DEFAULT_VIEWPORT,
    trace_path: str | Path | None = None,
) -> Iterator[BrowserSession]:
    """Open the rendered report and expose the live Playwright page for diagnostics."""

    root = Path(root).expanduser().resolve()
    if not (root / HTML).is_file():
        raise VerificationError(f"missing rendered report: {root / HTML}; run report render first")
    if timeout_seconds <= 0:
        raise VerificationError("browser timeout must be positive")

    sync_playwright, PlaywrightError, PlaywrightTimeoutError = _load_playwright()
    executable, source = resolve_browser_path(browser_path)
    timeout_ms = round(timeout_seconds * 1000)
    trace = Path(trace_path).expanduser().resolve() if trace_path else None
    if trace:
        trace.parent.mkdir(parents=True, exist_ok=True)

    play = sync_playwright().start()
    browser = context = None
    tracing = False
    try:
        launched = time.perf_counter()
        options: dict[str, Any] = {"headless": True}
        if executable:
            options["executable_path"] = str(executable)
        browser = play.chromium.launch(**options)
        launch_ms = round((time.perf_counter() - launched) * 1000)
        context = browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            device_scale_factor=1,
            reduced_motion="reduce",
            service_workers="block",
        )
        context.set_default_timeout(timeout_ms)
        if trace:
            context.tracing.start(screenshots=True, snapshots=True, sources=False)
            tracing = True
        page = context.new_page()
        events = BrowserEvents()
        _bind_events(page, events)
        with serve_report(root) as url:
            started = time.perf_counter()
            response = page.goto(url, wait_until="load", timeout=timeout_ms)
            navigation_ms = round((time.perf_counter() - started) * 1000)
            settle_ms = _settle(page, events, max(250, min(1_500, timeout_ms // 4)))
            with contextlib.suppress(PlaywrightError):
                page.evaluate(
                    """async () => {
                      if (document.fonts?.ready) await Promise.race([
                        document.fonts.ready,
                        new Promise(resolve => setTimeout(resolve, 500))
                      ]);
                      await new Promise(resolve => requestAnimationFrame(
                        () => requestAnimationFrame(resolve)
                      ));
                    }"""
                )
            yield BrowserSession(
                page=page,
                events=events,
                response_status=int(response.status) if response else None,
                browser={
                    "engine": "chromium",
                    "version": str(getattr(browser, "version", "")),
                    "executable_source": source,
                    "executable_name": executable.name if executable else None,
                    "viewport": {"width": viewport[0], "height": viewport[1], "dpr": 1},
                },
                timing_ms={
                    "launch": launch_ms,
                    "navigation": navigation_ms,
                    "settle": settle_ms,
                },
            )
    except PlaywrightTimeoutError as error:
        raise VerificationError(
            f"browser verification timed out after {timeout_seconds:g}s: {error}"
        ) from error
    except PlaywrightError as error:
        raise VerificationError(f"browser operation failed: {error}") from error
    finally:
        if context and tracing and trace:
            with contextlib.suppress(Exception):
                context.tracing.stop(path=str(trace))
        if context:
            with contextlib.suppress(Exception):
                context.close()
        if browser:
            with contextlib.suppress(Exception):
                browser.close()
        play.stop()


_PAGE_PROBE = r"""
async (hookTimeout) => {
  const round = x => Number.isFinite(x) ? Math.round(x * 100) / 100 : null;
  const selector = el => {
    if (el.id) return `#${CSS.escape(el.id)}`;
    const view = el.getAttribute("data-report-view");
    if (view) return `[data-report-view="${CSS.escape(view)}"]`;
    return el.tagName.toLowerCase();
  };
  const record = el => {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return {
      selector: selector(el), tag: el.tagName.toLowerCase(),
      declared_view: el.hasAttribute("data-report-view"),
      renderer: el.getAttribute("data-report-renderer"),
      visible: style.display !== "none" && style.visibility !== "hidden" &&
               Number(style.opacity || 1) !== 0 && rect.width > 0 && rect.height > 0,
      rect: {x: round(rect.x), y: round(rect.y), width: round(rect.width), height: round(rect.height)},
      canvas: el instanceof HTMLCanvasElement ? {width: el.width, height: el.height} : null,
      view_box: el instanceof SVGSVGElement ? {
        width: round(el.viewBox.baseVal.width), height: round(el.viewBox.baseVal.height)
      } : null
    };
  };

  const viewSet = new Set();
  for (const query of [
    "[data-report-view]", "perspective-viewer", ".ag-root-wrapper", ".bk-Root",
    ".bk-root", ".plotly-graph-div", ".vega-embed", "canvas"
  ]) for (const el of document.querySelectorAll(query)) viewSet.add(el);
  for (const el of document.querySelectorAll("*") ) {
    if (el.tagName.includes("-")) {
      const rect = el.getBoundingClientRect();
      if (rect.width >= 32 || rect.height >= 32) viewSet.add(el);
    }
  }

  const root = document.documentElement;
  const brokenImages = Array.from(document.images)
    .filter(img => !img.complete || img.naturalWidth === 0).slice(0, 20)
    .map(img => ({src: img.currentSrc || img.src}));

  const hook = {present: false, result: null, error: null};
  const candidate = globalThis.__REPORT_VERIFY__;
  if (candidate !== undefined) {
    hook.present = true;
    try {
      const operation = typeof candidate === "function" ? candidate()
        : candidate && typeof candidate.verify === "function" ? candidate.verify()
        : candidate;
      const value = await Promise.race([
        Promise.resolve(operation),
        new Promise((_, reject) => setTimeout(
          () => reject(new Error(`__REPORT_VERIFY__ exceeded ${hookTimeout} ms`)), hookTimeout
        ))
      ]);
      const encoded = JSON.stringify(value, (_key, item) =>
        typeof item === "bigint" ? item.toString() : item
      );
      if (encoded?.length > 100000) {
        hook.result = {
          status: value?.status, message: String(value?.message || "").slice(0, 2000),
          checks: Array.isArray(value?.checks) ? value.checks.slice(0, 100) : [],
          truncated: true, original_json_characters: encoded.length
        };
      } else hook.result = encoded === undefined ? null : JSON.parse(encoded);
    } catch (error) {
      hook.error = {
        message: String(error?.message || error).slice(0, 4000),
        stack: String(error?.stack || "").slice(0, 8000)
      };
    }
  }

  return {
    page: {url: location.href, title: document.title, ready_state: document.readyState},
    document: {
      elements: document.querySelectorAll("*").length,
      client_width: root.clientWidth, scroll_width: root.scrollWidth,
      client_height: root.clientHeight, scroll_height: root.scrollHeight,
      horizontal_overflow_px: Math.max(0, root.scrollWidth - root.clientWidth),
      allow_horizontal_overflow: document.body?.dataset.reportAllowOverflow === "x" ||
                                 root.dataset.reportAllowOverflow === "x",
      broken_images: brokenImages
    },
    views: Array.from(viewSet).slice(0, 100).map(record),
    hook
  };
}
"""


_SELECTOR_PROBE = r"""
selector => {
  const round = x => Number.isFinite(x) ? Math.round(x * 100) / 100 : null;
  try {
    const matches = Array.from(document.querySelectorAll(selector)).slice(0, 10);
    return {selector, count: document.querySelectorAll(selector).length, elements: matches.map(el => {
      const rect = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      const html = el.outerHTML || "";
      return {
        tag: el.tagName.toLowerCase(), id: el.id || null,
        classes: Array.from(el.classList || []).slice(0, 12),
        rect: {x: round(rect.x), y: round(rect.y), width: round(rect.width), height: round(rect.height)},
        client: {width: el.clientWidth, height: el.clientHeight},
        scroll: {width: el.scrollWidth, height: el.scrollHeight},
        style: {display: style.display, visibility: style.visibility, position: style.position,
                overflow_x: style.overflowX, overflow_y: style.overflowY,
                width: style.width, height: style.height, transform: style.transform},
        text: (el.innerText || el.textContent || "").slice(0, 4000),
        outer_html: html.length <= 20000 ? html : html.slice(0, 20000) + "<!-- truncated -->"
      };
    })};
  } catch (error) { return {selector, count: 0, error: String(error)}; }
}
"""


_OVERFLOW_PROBE = r"""
limit => Array.from(document.querySelectorAll("*"))
  .map(el => ({el, rect: el.getBoundingClientRect(), style: getComputedStyle(el)}))
  .filter(x => x.style.display !== "none" && x.style.visibility !== "hidden" &&
               x.rect.width > 0 && x.rect.height > 0 &&
               (x.rect.right > document.documentElement.clientWidth + 2 || x.rect.left < -2))
  .map(x => ({
    tag: x.el.tagName.toLowerCase(), id: x.el.id || null,
    right_overflow: Math.max(0, Math.round(x.rect.right - document.documentElement.clientWidth)),
    left_overflow: Math.max(0, Math.round(-x.rect.left)),
    rect: {left: Math.round(x.rect.left), right: Math.round(x.rect.right),
           width: Math.round(x.rect.width), height: Math.round(x.rect.height)},
    overflow: {x: x.style.overflowX, y: x.style.overflowY}
  }))
  .sort((a, b) => Math.max(b.right_overflow, b.left_overflow) -
                   Math.max(a.right_overflow, a.left_overflow))
  .slice(0, Math.max(1, Math.min(Number(limit) || 50, 200)))
"""


def inspect_page(page: Any) -> dict[str, Any]:
    return dict(page.evaluate(_PAGE_PROBE, 2_000))


def inspect_elements(page: Any, selectors: Sequence[str]) -> list[dict[str, Any]]:
    return [dict(page.evaluate(_SELECTOR_PROBE, str(selector))) for selector in selectors]


def inspect_overflow(page: Any, limit: int = 50) -> list[dict[str, Any]]:
    return list(page.evaluate(_OVERFLOW_PROBE, max(1, min(int(limit), 200))))


def _diagnostics() -> dict[str, Any]:
    return {
        "stability": DIAGNOSTIC_API_STABILITY,
        "problem_api": "executable_reports.verification.diagnose_problem",
        "quick_start": (
            "from pathlib import Path; import json; "
            "from executable_reports.verification import diagnose_problem; "
            f"r=json.loads(Path('{VERIFY_RECEIPT}').read_text()); "
            "print(json.dumps(diagnose_problem('.', r['problems'][0], "
            "screenshot_path='report.problem.png', trace_path='report.problem.trace.zip'), indent=2))"
        ),
        "custom_session": (
            "from executable_reports.verification import browser_session; "
            "use browser_session('.') to access session.page for renderer-specific inspection"
        ),
    }


def _problem(
    identifier: str,
    category: str,
    severity: str,
    message: str,
    *,
    selector: str | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "id": identifier,
        "category": category,
        "severity": severity,
        "message": message,
        "diagnostic_api": "executable_reports.verification.diagnose_problem",
        "diagnostic_hint": (
            "Pass this problem to diagnose_problem(); it reopens the same report harness and "
            "returns targeted browser evidence without rebuilding setup."
        ),
    }
    if selector:
        value["selector"] = selector
    if evidence:
        value["evidence"] = dict(evidence)
    return value


def build_verification_receipt(
    *,
    target_sha256: str,
    response_status: int | None,
    browser: Mapping[str, Any],
    events: Mapping[str, Any],
    probe: Mapping[str, Any],
    timing_ms: Mapping[str, int],
    screenshot_path: str | None,
    checked_at: str | None = None,
) -> dict[str, Any]:
    events = _portable(dict(events))
    probe = _portable(dict(probe))
    problems: list[dict[str, Any]] = []

    def add(identifier: str, category: str, severity: str, message: str, **kwargs: Any) -> None:
        problems.append(_problem(identifier, category, severity, message, **kwargs))

    if response_status is None or response_status >= 400:
        add("navigation.http", "navigation", "error", f"report navigation returned HTTP {response_status!r}")
    if probe.get("page", {}).get("ready_state") != "complete":
        add("navigation.ready-state", "navigation", "error", "document did not reach readyState='complete'")

    for index, item in enumerate(events.get("page_errors", []), 1):
        add(f"runtime.page-error.{index}", "runtime", "error", item.get("message", "page error"), evidence=item)
    for index, item in enumerate(events.get("crashes", []), 1):
        add(f"runtime.crash.{index}", "runtime", "error", item.get("message", "page crash"), evidence=item)
    for index, item in enumerate(events.get("console", []), 1):
        kind = str(item.get("type", "")).lower()
        if kind in {"error", "warning"}:
            add(
                f"runtime.console-{kind}.{index}", "runtime",
                "error" if kind == "error" else "warning",
                item.get("text", f"console {kind}"), evidence=item,
            )
    for index, item in enumerate(events.get("dialogs", []), 1):
        add(f"runtime.dialog.{index}", "runtime", "error", f"unexpected dialog: {item.get('message', '')}", evidence=item)

    for index, item in enumerate(events.get("request_failures", []), 1):
        severity = "warning" if "ERR_ABORTED" in str(item.get("error", "")) else "error"
        add(
            f"resources.request-failed.{index}", "resources", severity,
            f"{item.get('method', 'GET')} {item.get('url', '')}: {item.get('error', '')}", evidence=item,
        )
    for index, item in enumerate(events.get("response_errors", []), 1):
        add(f"resources.http-error.{index}", "resources", "error", f"HTTP {item.get('status')} for {item.get('url', '')}", evidence=item)
    pending = list(events.get("pending_requests", []))
    if pending:
        add("resources.pending", "resources", "warning", f"{len(pending)} request(s) still pending after settle window", evidence={"requests": pending})
    for index, item in enumerate(probe.get("document", {}).get("broken_images", []), 1):
        add(f"resources.broken-image.{index}", "resources", "error", f"image failed to render: {item.get('src', '')}", evidence=item)

    document = dict(probe.get("document", {}))
    overflow = int(document.get("horizontal_overflow_px", 0) or 0)
    if overflow > 2 and not document.get("allow_horizontal_overflow"):
        add(
            "layout.document-overflow-x", "layout", "error",
            f"document is {overflow}px wider than the verification viewport",
            evidence={
                "overflow_px": overflow,
                "next": "diagnose_problem() runs a whole-document overflow scan on this failure",
            },
        )

    views = list(probe.get("views", []))
    for index, view in enumerate(views, 1):
        rect = view.get("rect", {})
        if view.get("declared_view") and (
            float(rect.get("width", 0) or 0) < 1 or float(rect.get("height", 0) or 0) < 1
        ):
            add(f"views.zero-size.{index}", "views", "error", "declared report view has zero rendered size", selector=view.get("selector"), evidence=view)
        if view.get("visible") and view.get("canvas") and (
            int(view["canvas"].get("width", 0) or 0) < 1 or int(view["canvas"].get("height", 0) or 0) < 1
        ):
            add(f"views.canvas-zero-bitmap.{index}", "views", "error", "visible canvas has a zero-sized drawing buffer", selector=view.get("selector"), evidence=view)
        if view.get("visible") and view.get("view_box") and (
            float(view["view_box"].get("width", 0) or 0) <= 0
            or float(view["view_box"].get("height", 0) or 0) <= 0
        ):
            add(f"views.svg-zero-viewbox.{index}", "views", "warning", "visible SVG has a zero-sized viewBox", selector=view.get("selector"), evidence=view)

    hook = dict(probe.get("hook", {}))
    if hook.get("error"):
        add("report-hook.error", "report_hook", "error", f"__REPORT_VERIFY__ failed: {hook['error'].get('message', '')}", evidence=hook["error"])
    result = hook.get("result")
    if isinstance(result, Mapping):
        for index, check in enumerate(result.get("checks", []), 1):
            if not isinstance(check, Mapping):
                continue
            status = str(check.get("status", "passed")).lower()
            if status in {"failed", "error", "warning"}:
                add(
                    f"report-hook.check.{index}", "report_hook",
                    "warning" if status == "warning" else "error",
                    str(check.get("message", check.get("name", "report-owned check failed"))),
                    selector=check.get("selector"), evidence=check,
                )
        if result.get("truncated"):
            add("report-hook.truncated", "report_hook", "warning", "__REPORT_VERIFY__ result was bounded in the receipt")
        if str(result.get("status", "")).lower() in {"failed", "error"} and not any(
            p["category"] == "report_hook" and p["severity"] == "error" for p in problems
        ):
            add("report-hook.status", "report_hook", "error", str(result.get("message", "report-owned verification failed")), evidence=result)

    if probe.get("screenshot_error"):
        add("evidence.screenshot", "evidence", "warning", f"viewport screenshot failed: {probe['screenshot_error']}")

    errors = sum(p["severity"] == "error" for p in problems)
    warnings = sum(p["severity"] == "warning" for p in problems)
    categories = ("navigation", "runtime", "resources", "layout", "views", "report_hook", "evidence")
    checks = []
    for category in categories:
        related = [p for p in problems if p["category"] == category]
        checks.append({
            "name": category,
            "status": "failed" if any(p["severity"] == "error" for p in related) else "passed",
            "errors": sum(p["severity"] == "error" for p in related),
            "warnings": sum(p["severity"] == "warning" for p in related),
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "executable_report_browser_verification",
        "status": "failed" if errors else "passed",
        "checked_at": checked_at or dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        "target": {"path": HTML, "sha256": target_sha256},
        "browser": dict(browser),
        "timing_ms": dict(timing_ms),
        "summary": {"errors": errors, "warnings": warnings, "views_observed": len(views), "requests": int(events.get("requests_total", 0) or 0)},
        "checks": checks,
        "problems": problems,
        "runtime": {key: list(events.get(key, [])) for key in (
            "console", "page_errors", "request_failures", "response_errors", "dialogs", "pending_requests"
        )},
        "page": dict(probe.get("page", {})),
        "layout": {"document": document},
        "views": views,
        "report_hook": hook,
        "evidence": {
            "receipt": VERIFY_RECEIPT,
            "screenshot": screenshot_path,
            "screenshot_scope": "initial viewport" if screenshot_path else None,
            "visual_judgment_automated": False,
        },
        "diagnostics": _diagnostics(),
    }


def build_error_receipt(root: str | Path, message: str) -> dict[str, Any]:
    root = Path(root).expanduser().resolve()
    html = root / HTML
    problem = _problem("setup.browser", "setup", "error", _portable_text(message))
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "executable_report_browser_verification",
        "status": "error",
        "checked_at": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        "target": {"path": HTML, "sha256": sha256(html) if html.is_file() else None},
        "browser": None,
        "timing_ms": {},
        "summary": {"errors": 1, "warnings": 0, "views_observed": 0, "requests": 0},
        "checks": [{"name": "setup", "status": "failed", "errors": 1, "warnings": 0}],
        "problems": [problem],
        "runtime": {}, "page": {}, "layout": {}, "views": [], "report_hook": {},
        "evidence": {"receipt": VERIFY_RECEIPT, "screenshot": None, "visual_judgment_automated": False},
        "diagnostics": _diagnostics(),
    }


def verify_report(
    root: str | Path,
    *,
    browser_path: str | Path | None = None,
    timeout_seconds: float = 15,
    screenshot_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(root).expanduser().resolve()
    screenshot = Path(screenshot_path).expanduser().resolve() if screenshot_path else None
    if screenshot:
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        screenshot.unlink(missing_ok=True)
    started = time.perf_counter()
    try:
        with browser_session(root, browser_path=browser_path, timeout_seconds=timeout_seconds) as session:
            probe_started = time.perf_counter()
            probe = inspect_page(session.page)
            probe_ms = round((time.perf_counter() - probe_started) * 1000)
            screenshot_ms = 0
            relative_screenshot: str | None = None
            if screenshot:
                shot_started = time.perf_counter()
                try:
                    session.page.screenshot(path=str(screenshot), full_page=False, animations="disabled", scale="css")
                    try:
                        relative_screenshot = screenshot.relative_to(root).as_posix()
                    except ValueError:
                        relative_screenshot = str(screenshot)
                except Exception as error:
                    probe["screenshot_error"] = _bounded(error, 4_000)
                    screenshot.unlink(missing_ok=True)
                screenshot_ms = round((time.perf_counter() - shot_started) * 1000)
            return build_verification_receipt(
                target_sha256=sha256(root / HTML),
                response_status=session.response_status,
                browser=session.browser,
                events=session.events.snapshot(),
                probe=probe,
                timing_ms={
                    **session.timing_ms,
                    "probe": probe_ms,
                    "screenshot": screenshot_ms,
                    "total": round((time.perf_counter() - started) * 1000),
                },
                screenshot_path=relative_screenshot,
            )
    except VerificationError as error:
        return build_error_receipt(root, str(error))
    except Exception as error:
        return build_error_receipt(root, f"unexpected browser verifier failure: {error}")


def diagnose_report(
    root: str | Path,
    *,
    selector: str = "body",
    browser_path: str | Path | None = None,
    timeout_seconds: float = 15,
    screenshot_path: str | Path | None = None,
    trace_path: str | Path | None = None,
    deep_overflow: bool = False,
) -> dict[str, Any]:
    root = Path(root).expanduser().resolve()
    screenshot = Path(screenshot_path).expanduser().resolve() if screenshot_path else None
    if screenshot:
        screenshot.parent.mkdir(parents=True, exist_ok=True)
    with browser_session(
        root,
        browser_path=browser_path,
        timeout_seconds=timeout_seconds,
        trace_path=trace_path,
    ) as session:
        screenshot_error = None
        if screenshot:
            try:
                locator = session.page.locator(selector)
                if locator.count():
                    locator.first.screenshot(path=str(screenshot), animations="disabled")
                else:
                    session.page.screenshot(path=str(screenshot), full_page=True, animations="disabled")
            except Exception as error:
                screenshot_error = _bounded(error, 4_000)
        return {
            "kind": "executable_report_browser_diagnostic",
            "stability": DIAGNOSTIC_API_STABILITY,
            "target": {"path": HTML, "sha256": sha256(root / HTML)},
            "browser": session.browser,
            "events": _portable(session.events.snapshot()),
            "page": _portable(inspect_page(session.page)),
            "elements": inspect_elements(session.page, [selector]),
            "overflow": inspect_overflow(session.page) if deep_overflow else [],
            "evidence": {
                "screenshot": str(screenshot) if screenshot else None,
                "screenshot_error": screenshot_error,
                "trace": str(Path(trace_path).expanduser()) if trace_path else None,
            },
        }


def diagnose_problem(
    root: str | Path,
    problem: Mapping[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    kwargs.setdefault("selector", str(problem.get("selector") or "body"))
    kwargs.setdefault(
        "deep_overflow", str(problem.get("id", "")).startswith("layout.document-overflow")
    )
    result = diagnose_report(root, **kwargs)
    result["problem"] = dict(problem)
    return result


__all__ = [
    "BrowserSession",
    "BrowserUnavailable",
    "VerificationError",
    "browser_session",
    "build_error_receipt",
    "build_verification_receipt",
    "diagnose_problem",
    "diagnose_report",
    "inspect_elements",
    "inspect_overflow",
    "inspect_page",
    "resolve_browser_path",
    "serve_report",
    "verify_report",
]
