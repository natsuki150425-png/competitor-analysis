"""
tests/test_seo_checker.py
"""
import pytest
from bs4 import BeautifulSoup
from src.scraper import RawArticle
from src.seo_checker import SeoChecker


def _make_article(html: str) -> RawArticle:
    return RawArticle(
        url="https://example.com/blog/1",
        domain="example.com",
        html=html,
        soup=BeautifulSoup(html, "lxml"),
        load_time_ms=200.0,
        status_code=200,
    )


FULL_SEO_HTML = """
<html>
<head>
  <title>Python入門：初心者向け完全ガイド2024年版</title>
  <meta name="description" content="Pythonの基礎から応用まで丁寧に解説。インストール方法、基本文法、実践プロジェクトまで網羅した初心者向け完全ガイドです。" />
  <meta property="og:title" content="Python入門ガイド" />
  <meta property="og:description" content="初心者向けPython解説" />
  <meta property="og:image" content="https://example.com/ogp.jpg" />
  <link rel="canonical" href="https://example.com/blog/1" />
  <script type="application/ld+json">{"@type": "Article"}</script>
</head>
<body>
  <a href="/other">内部リンク</a>
  <a href="https://external.com">外部リンク</a>
</body>
</html>
"""


def test_full_seo_score():
    checker = SeoChecker()
    result = checker.check(_make_article(FULL_SEO_HTML))
    assert result.seo_score == 100
    assert result.has_canonical is True
    assert result.has_structured_data is True
    assert result.has_ogp is True


def test_missing_description():
    html = "<html><head><title>短いタイトル</title></head><body></body></html>"
    checker = SeoChecker()
    result = checker.check(_make_article(html))
    assert result.meta_description == ""
    assert result.description_ok is False
    assert result.seo_score < 100


def test_link_counting():
    html = """
    <html><body>
      <a href="/page1">内部1</a>
      <a href="/page2">内部2</a>
      <a href="https://external.com">外部</a>
      <a href="#anchor">アンカー</a>
    </body></html>
    """
    checker = SeoChecker()
    result = checker.check(_make_article(html))
    assert result.internal_links == 2
    assert result.external_links == 1
