"""
seo_checker.py
SEO要素のチェックとスコアリングを行うモジュール
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from loguru import logger

from .scraper import RawArticle


@dataclass
class SeoResult:
    """SEO分析結果"""
    url: str

    # タイトル
    meta_title: str = ""
    meta_title_length: int = 0
    title_ok: bool = False          # 20〜60文字

    # Description
    meta_description: str = ""
    meta_description_length: int = 0
    description_ok: bool = False    # 70〜160文字

    # OGP
    has_og_title: bool = False
    has_og_description: bool = False
    has_og_image: bool = False

    @property
    def has_ogp(self) -> bool:
        return self.has_og_title or self.has_og_description or self.has_og_image

    # 構造
    has_canonical: bool = False
    canonical_url: str = ""
    has_structured_data: bool = False

    # リンク
    internal_links: int = 0
    external_links: int = 0

    # スコア（0〜100）
    seo_score: int = 0
    score_breakdown: dict = field(default_factory=dict)


class SeoChecker:
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.title_min = cfg.get("title_min_length", 20)
        self.title_max = cfg.get("title_max_length", 60)
        self.desc_min = cfg.get("description_min_length", 70)
        self.desc_max = cfg.get("description_max_length", 160)

    def check(self, article: RawArticle) -> SeoResult:
        result = SeoResult(url=article.url)

        if not article.is_valid:
            return result

        soup = article.soup
        domain = article.domain

        # ── タイトル ──────────────────────────────
        title_tag = soup.find("title")
        if title_tag:
            result.meta_title = title_tag.get_text(strip=True)
            result.meta_title_length = len(result.meta_title)
            result.title_ok = self.title_min <= result.meta_title_length <= self.title_max

        # ── Description ───────────────────────────
        desc_tag = soup.find("meta", attrs={"name": "description"})
        if desc_tag and desc_tag.get("content"):
            result.meta_description = desc_tag["content"].strip()
            result.meta_description_length = len(result.meta_description)
            result.description_ok = self.desc_min <= result.meta_description_length <= self.desc_max

        # ── OGP ───────────────────────────────────
        result.has_og_title = bool(soup.find("meta", property="og:title"))
        result.has_og_description = bool(soup.find("meta", property="og:description"))
        result.has_og_image = bool(soup.find("meta", property="og:image"))

        # ── Canonical ─────────────────────────────
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            result.has_canonical = True
            result.canonical_url = canonical["href"]

        # ── 構造化データ（JSON-LD）────────────────
        result.has_structured_data = bool(
            soup.find("script", type="application/ld+json")
        )

        # ── リンク数 ──────────────────────────────
        internal, external = self._count_links(soup, domain)
        result.internal_links = internal
        result.external_links = external

        # ── SEOスコア計算 ─────────────────────────
        result.seo_score, result.score_breakdown = self._calc_score(result)

        logger.debug(f"SEO スコア {result.seo_score}/100: {article.url}")
        return result

    def _count_links(self, soup: BeautifulSoup, domain: str) -> tuple[int, int]:
        internal = 0
        external = 0
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("#") or href.startswith("javascript"):
                continue
            if href.startswith("/") or domain in href:
                internal += 1
            elif href.startswith("http"):
                external += 1
        return internal, external

    def _calc_score(self, r: SeoResult) -> tuple[int, dict]:
        """
        SEOスコア 0〜100点
        各項目の配点:
          title_exists      : 10点
          title_length_ok   : 10点
          desc_exists       : 10点
          desc_length_ok    : 10点
          has_og_title      : 10点
          has_og_image      : 10点
          has_canonical     : 15点
          has_structured    : 15点
          has_internal_links: 10点（1本以上あれば）
        """
        breakdown = {
            "title_exists":       10 if r.meta_title else 0,
            "title_length_ok":    10 if r.title_ok else 0,
            "desc_exists":        10 if r.meta_description else 0,
            "desc_length_ok":     10 if r.description_ok else 0,
            "has_og_title":       10 if r.has_og_title else 0,
            "has_og_image":       10 if r.has_og_image else 0,
            "has_canonical":      15 if r.has_canonical else 0,
            "has_structured":     15 if r.has_structured_data else 0,
            "has_internal_links": 10 if r.internal_links > 0 else 0,
        }
        return sum(breakdown.values()), breakdown
