"""
tests/test_keyword_extractor.py
"""
import pytest
from src.keyword_extractor import KeywordExtractor


def test_basic_extraction():
    extractor = KeywordExtractor()
    text = "機械学習と深層学習は人工知能の重要な技術です。機械学習を使ったシステムが増えています。"
    result = extractor.extract("https://example.com/1", "example.com", text)
    assert len(result.keywords_freq) > 0


def test_empty_text():
    extractor = KeywordExtractor()
    result = extractor.extract("https://example.com/1", "example.com", "")
    assert result.keywords_freq == []
    assert result.cooccurrence_pairs == []


def test_cooccurrence():
    extractor = KeywordExtractor({"cooccurrence_window": 3})
    text = "Python データ 分析 Python データ サイエンス Python 機械学習"
    result = extractor.extract("https://example.com/1", "example.com", text)
    # 共起ペアが抽出されること
    assert isinstance(result.cooccurrence_pairs, list)


def test_tfidf_multiple_docs():
    extractor = KeywordExtractor()
    texts = [
        "機械学習 深層学習 ニューラルネットワーク 機械学習 機械学習",
        "ウェブ開発 フロントエンド バックエンド ウェブ開発 JavaScript",
    ]
    results = []
    for i, text in enumerate(texts):
        r = extractor.extract(f"https://example.com/{i}", "example.com", text)
        results.append(r)
    results = extractor.extract_tfidf(results)
    # TF-IDFスコアが付与されていること
    assert len(results[0].keywords_tfidf) > 0
