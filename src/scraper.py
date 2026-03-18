"""
scraper.py
競合サイトの記事をスクレイピングして生データを取得するモジュール
"""
from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from loguru import logger


@dataclass
class RawArticle:
    """スクレイピングで取得した生記事データ"""
    url: str
    domain: str
    html: str
    soup: BeautifulSoup
    load_time_ms: float
    status_code: int
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.error is None and self.status_code == 200


@dataclass
class ScraperConfig:
    request_delay_sec: float = 1.0
    timeout_sec: int = 15
    max_retries: int = 3
    user_agent: str = "CompetitorAnalysisBot/1.0"
    respect_robots_txt: bool = True


class RobotsCache:
    """robots.txt キャッシュ"""
    def __init__(self):
        self._cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    def can_fetch(self, url: str, user_agent: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._cache:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"{base}/robots.txt")
            try:
                rp.read()
            except Exception:
                # robots.txt が取得できない場合は許可とみなす
                self._cache[base] = None
                return True
            self._cache[base] = rp
        rp = self._cache[base]
        if rp is None:
            return True
        return rp.can_fetch(user_agent, url)


class Scraper:
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.robots_cache = RobotsCache()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})

    def fetch(self, url: str) -> RawArticle:
        """1件のURLを取得してRawArticleを返す"""
        domain = urlparse(url).netloc

        # robots.txt チェック
        if self.config.respect_robots_txt:
            if not self.robots_cache.can_fetch(url, self.config.user_agent):
                logger.warning(f"robots.txt によりブロック: {url}")
                return RawArticle(
                    url=url, domain=domain, html="", soup=BeautifulSoup("", "lxml"),
                    load_time_ms=0, status_code=0,
                    error="Blocked by robots.txt"
                )

        for attempt in range(1, self.config.max_retries + 1):
            try:
                start = time.perf_counter()
                response = self.session.get(
                    url,
                    timeout=self.config.timeout_sec,
                    allow_redirects=True
                )
                elapsed_ms = (time.perf_counter() - start) * 1000

                if response.status_code != 200:
                    logger.warning(f"HTTP {response.status_code}: {url}")
                    return RawArticle(
                        url=url, domain=domain, html="", soup=BeautifulSoup("", "lxml"),
                        load_time_ms=elapsed_ms, status_code=response.status_code,
                        error=f"HTTP {response.status_code}"
                    )

                # エンコーディング自動検出
                response.encoding = response.apparent_encoding
                html = response.text
                soup = BeautifulSoup(html, "lxml")

                logger.info(f"取得成功 ({elapsed_ms:.0f}ms): {url}")
                return RawArticle(
                    url=url, domain=domain, html=html, soup=soup,
                    load_time_ms=elapsed_ms, status_code=200
                )

            except requests.exceptions.Timeout:
                logger.warning(f"タイムアウト (試行 {attempt}/{self.config.max_retries}): {url}")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"接続エラー (試行 {attempt}/{self.config.max_retries}): {url} - {e}")
            except Exception as e:
                logger.error(f"予期しないエラー: {url} - {e}")
                return RawArticle(
                    url=url, domain=domain, html="", soup=BeautifulSoup("", "lxml"),
                    load_time_ms=0, status_code=0, error=str(e)
                )

            if attempt < self.config.max_retries:
                time.sleep(self.config.request_delay_sec * attempt)

        return RawArticle(
            url=url, domain=domain, html="", soup=BeautifulSoup("", "lxml"),
            load_time_ms=0, status_code=0, error="Max retries exceeded"
        )

    def fetch_all(self, urls: list[str], delay: float | None = None) -> list[RawArticle]:
        """URLリストを順番に取得（delay秒間隔）"""
        delay = delay if delay is not None else self.config.request_delay_sec
        results = []
        for i, url in enumerate(urls):
            if i > 0:
                time.sleep(delay)
            results.append(self.fetch(url))
        return results
