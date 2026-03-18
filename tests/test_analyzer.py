"""
tests/test_analyzer.py
"""
import pytest
from bs4 import BeautifulSoup
from src.scraper import RawArticle
from src.analyzer import ArticleAnalyzer


def _make_article(html: str, url: str = "https://example.com/blog/1") -> RawArticle:
    return RawArticle(
        url=url,
        domain="example.com",
        html=html,
        soup=BeautifulSoup(html, "lxml"),
        load_time_ms=100.0,
        status_code=200,
    )


def test_heading_extraction():
    html = """
    <html><body>
      <h1>タイトル</h1>
      <h2>セクション1</h2>
      <h3>サブセクション</h3>
      <p>本文テキスト</p>
    </body></html>
    """
    analyzer = ArticleAnalyzer()
    result = analyzer.analyze(_make_article(html))

    assert result.h1_count == 1
    assert result.h2_count == 1
    assert result.h3_count == 1
    assert result.h4_count == 0
    assert result.h1_texts[0] == "タイトル"


def test_word_count():
    html = "<html><body><article><p>日本語のテスト文章です。</p></article></body></html>"
    analyzer = ArticleAnalyzer()
    result = analyzer.analyze(_make_article(html))
    assert result.word_count > 0


def test_invalid_article():
    article = RawArticle(
        url="https://example.com/404",
        domain="example.com",
        html="",
        soup=BeautifulSoup("", "lxml"),
        load_time_ms=0,
        status_code=404,
        error="HTTP 404",
    )
    analyzer = ArticleAnalyzer()
    result = analyzer.analyze(article)
    assert result.word_count == 0
    assert result.h1_count == 0


def test_heading_tree():
    html = """
    <html><body>
      <h1>H1</h1>
      <h2>H2-1</h2>
      <h3>H3-1</h3>
      <h2>H2-2</h2>
    </body></html>
    """
    analyzer = ArticleAnalyzer()
    result = analyzer.analyze(_make_article(html))
    assert len(result.heading_tree) == 1
    assert result.heading_tree[0]["text"] == "H1"
    assert len(result.heading_tree[0]["children"]) == 2
