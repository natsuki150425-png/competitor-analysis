"""
analyzer.py
記事構成・見出し・本文テキストを分析するモジュール
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup, Tag
from loguru import logger

from .scraper import RawArticle


@dataclass
class HeadingNode:
    """見出し階層ノード"""
    level: int          # 1〜4
    text: str
    children: list["HeadingNode"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "text": self.text,
            "children": [c.to_dict() for c in self.children]
        }


@dataclass
class ArticleStructure:
    """記事構造分析結果"""
    url: str
    domain: str
    title: str
    load_time_ms: float
    status_code: int
    error: Optional[str]

    # 見出し
    h1_texts: list[str] = field(default_factory=list)
    h2_texts: list[str] = field(default_factory=list)
    h3_texts: list[str] = field(default_factory=list)
    h4_texts: list[str] = field(default_factory=list)
    heading_tree: list[dict] = field(default_factory=list)

    # テキスト統計
    body_text: str = ""
    word_count: int = 0
    paragraph_count: int = 0
    image_count: int = 0
    avg_heading_length: float = 0.0
    max_heading_depth: int = 0

    @property
    def h1_count(self) -> int: return len(self.h1_texts)
    @property
    def h2_count(self) -> int: return len(self.h2_texts)
    @property
    def h3_count(self) -> int: return len(self.h3_texts)
    @property
    def h4_count(self) -> int: return len(self.h4_texts)
    @property
    def total_heading_count(self) -> int:
        return self.h1_count + self.h2_count + self.h3_count + self.h4_count


class ArticleAnalyzer:
    # 除外するタグ（ナビ・フッターなど）
    NOISE_TAGS = ["nav", "header", "footer", "aside", "script", "style", "form"]

    def analyze(self, article: RawArticle) -> ArticleStructure:
        structure = ArticleStructure(
            url=article.url,
            domain=article.domain,
            title="",
            load_time_ms=article.load_time_ms,
            status_code=article.status_code,
            error=article.error,
        )

        if not article.is_valid:
            return structure

        soup = article.soup

        # タイトル
        title_tag = soup.find("title")
        structure.title = title_tag.get_text(strip=True) if title_tag else ""

        # ノイズ除去
        for tag in soup.find_all(self.NOISE_TAGS):
            tag.decompose()

        # 見出し抽出
        structure.h1_texts = self._extract_headings(soup, "h1")
        structure.h2_texts = self._extract_headings(soup, "h2")
        structure.h3_texts = self._extract_headings(soup, "h3")
        structure.h4_texts = self._extract_headings(soup, "h4")

        # 見出し階層ツリー
        structure.heading_tree = self._build_heading_tree(soup)

        # 見出し統計
        all_headings = (
            structure.h1_texts + structure.h2_texts +
            structure.h3_texts + structure.h4_texts
        )
        if all_headings:
            structure.avg_heading_length = sum(len(h) for h in all_headings) / len(all_headings)

        depths = []
        if structure.h1_count: depths.append(1)
        if structure.h2_count: depths.append(2)
        if structure.h3_count: depths.append(3)
        if structure.h4_count: depths.append(4)
        structure.max_heading_depth = max(depths) if depths else 0

        # 本文テキスト・段落・画像
        main_content = self._find_main_content(soup)
        structure.body_text = main_content.get_text(separator=" ", strip=True)
        structure.word_count = len(structure.body_text.replace(" ", ""))  # 日本語は文字数
        structure.paragraph_count = len(main_content.find_all("p"))
        structure.image_count = len(soup.find_all("img"))

        logger.debug(
            f"分析完了: {article.url} "
            f"| {structure.word_count}字 "
            f"| H1:{structure.h1_count} H2:{structure.h2_count} H3:{structure.h3_count}"
        )
        return structure

    def _extract_headings(self, soup: BeautifulSoup, tag: str) -> list[str]:
        return [h.get_text(strip=True) for h in soup.find_all(tag) if h.get_text(strip=True)]

    def _build_heading_tree(self, soup: BeautifulSoup) -> list[dict]:
        """H1〜H4 を階層構造に変換"""
        headings = []
        for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
            level = int(tag.name[1])
            text = tag.get_text(strip=True)
            if text:
                headings.append((level, text))

        if not headings:
            return []

        root_nodes: list[HeadingNode] = []
        stack: list[HeadingNode] = []

        for level, text in headings:
            node = HeadingNode(level=level, text=text)
            while stack and stack[-1].level >= level:
                stack.pop()
            if stack:
                stack[-1].children.append(node)
            else:
                root_nodes.append(node)
            stack.append(node)

        return [n.to_dict() for n in root_nodes]

    def _find_main_content(self, soup: BeautifulSoup) -> Tag:
        """メインコンテンツ領域を推定して返す"""
        for selector in ["article", "main", '[role="main"]', ".post-content",
                         ".entry-content", ".article-body", "#content"]:
            found = soup.select_one(selector)
            if found:
                return found
        # フォールバック: body全体
        return soup.find("body") or soup
