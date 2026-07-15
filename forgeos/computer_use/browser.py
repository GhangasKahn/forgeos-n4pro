"""Playwright browser session — deterministic eyes + hands for the web."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class BrowserSession:
    """Sync Playwright Chromium session (headless or headed on DISPLAY)."""

    headless: bool = True
    display: str = ":1"
    artifact_dir: Path = Path("/opt/cursor/artifacts/computer_use")
    _pw: Any = field(default=None, repr=False)
    _browser: Any = field(default=None, repr=False)
    _page: Any = field(default=None, repr=False)

    def start(self) -> "BrowserSession":
        import os

        from playwright.sync_api import sync_playwright

        os.environ.setdefault("DISPLAY", self.display)
        self.artifact_dir = Path(self.artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--window-size=1600,1000"],
        )
        self._page = self._browser.new_page(viewport={"width": 1600, "height": 1000})
        return self

    @property
    def page(self):
        if self._page is None:
            raise RuntimeError("BrowserSession not started")
        return self._page

    def goto(self, url: str, wait: str = "domcontentloaded") -> None:
        self.page.goto(url, wait_until=wait, timeout=60000)

    def title(self) -> str:
        return self.page.title()

    def url(self) -> str:
        return self.page.url

    def text(self, selector: str = "body") -> str:
        return self.page.locator(selector).inner_text(timeout=10000)

    def click(self, selector: str) -> None:
        self.page.click(selector, timeout=15000)

    def fill(self, selector: str, value: str) -> None:
        self.page.fill(selector, value, timeout=15000)

    def screenshot(self, name: str = "browser") -> Path:
        out = self.artifact_dir / ("%s_%d.png" % (name, int(time.time() * 1000)))
        self.page.screenshot(path=str(out), full_page=False)
        return out

    def eval_js(self, expression: str) -> Any:
        return self.page.evaluate(expression)

    def content_snippet(self, n: int = 500) -> str:
        return (self.page.content() or "")[:n]

    def close(self) -> None:
        try:
            if self._browser:
                self._browser.close()
        finally:
            if self._pw:
                self._pw.stop()
            self._browser = None
            self._page = None
            self._pw = None

    def __enter__(self) -> "BrowserSession":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.close()

    def info(self) -> Dict[str, Any]:
        return {"url": self.url(), "title": self.title()}
