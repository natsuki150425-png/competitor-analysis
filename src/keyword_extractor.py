"""
keyword_extractor.py
形態素解析 + TF-IDF でキーワード・共起ペアを抽出するモジュール
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from loguru import logger

try:
    from janome.tokenizer import Tokenizer
    JANOME_AVAILABLE = True
except ImportError:
    JANOME_AVAILABLE = False
    logger.warning("janome が見つかりません。シンプルな分割にフォールバックします。")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn が見つかりません。TF-IDFをスキップします。")


@dataclass
class KeywordResult:
    """キーワード抽出結果"""
    url: str
    domain: str
    keywords_freq: list[tuple[str, int]] = field(default_factory=list)   # (キーワード, 頻度)
    keywords_tfidf: list[tuple[str, float]] = field(default_factory=list) # (キーワード, TF-IDFスコア)
    cooccurrence_pairs: list[tuple[str, str, int]] = field(default_factory=list)  # (w1, w2, 共起数)
    nouns: list[str] = field(default_factory=list)  # 抽出した全名詞リスト


class KeywordExtractor:
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.max_keywords = cfg.get("max_keywords", 30)
        self.min_length = cfg.get("min_keyword_length", 2)
        self.cooccurrence_window = cfg.get("cooccurrence_window", 5)
        self.top_pairs = cfg.get("top_cooccurrence_pairs", 20)
        self._tokenizer = Tokenizer() if JANOME_AVAILABLE else None

        # ストップワード（一般的すぎる語）
        self.stopwords = {
            "こと", "もの", "ため", "あと", "さん", "それ", "これ", "あれ",
            "その", "この", "あの", "とき", "ところ", "よう", "わけ", "はず",
            "ほう", "なか", "まま", "たち", "ので", "から", "ない", "ある",
            "する", "なる", "いる", "れる", "れ", "られる", "させる"
        }

    def extract(self, url: str, domain: str, text: str) -> KeywordResult:
        result = KeywordResult(url=url, domain=domain)

        if not text.strip():
            return result

        nouns = self._tokenize_nouns(text)
        result.nouns = nouns

        if not nouns:
            return result

        # 頻度ランキング
        freq = Counter(nouns)
        result.keywords_freq = freq.most_common(self.max_keywords)

        # 共起ペア
        result.cooccurrence_pairs = self._extract_cooccurrence(nouns)

        logger.debug(f"キーワード抽出完了 ({len(nouns)}語): {url}")
        return result

    def extract_tfidf(self, results: list[KeywordResult]) -> list[KeywordResult]:
        """
        複数記事のTF-IDFを一括計算して各KeywordResultに追記する
        """
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn未インストールのためTF-IDFをスキップ")
            return results

        valid = [r for r in results if r.nouns]
        if len(valid) < 2:
            logger.warning("TF-IDF計算には2記事以上必要です")
            return results

        # 各記事の名詞をスペース区切りテキストに変換
        corpus = [" ".join(r.nouns) for r in valid]

        try:
            vectorizer = TfidfVectorizer(
                analyzer="word",
                token_pattern=r"(?u)\b\w+\b",
                max_features=200
            )
            tfidf_matrix = vectorizer.fit_transform(corpus)
            feature_names = vectorizer.get_feature_names_out()

            for i, result in enumerate(valid):
                scores = tfidf_matrix[i].toarray()[0]
                # スコア上位をソート
                ranked = sorted(
                    zip(feature_names, scores),
                    key=lambda x: x[1],
                    reverse=True
                )
                result.keywords_tfidf = [
                    (word, round(score, 4))
                    for word, score in ranked[:self.max_keywords]
                    if score > 0
                ]
        except Exception as e:
            logger.error(f"TF-IDF計算エラー: {e}")

        return results

    def _tokenize_nouns(self, text: str) -> list[str]:
        """名詞を抽出（janome利用可能な場合）"""
        if not self._tokenizer:
            # フォールバック: 2文字以上の連続した文字列（雑な近似）
            import re
            tokens = re.findall(r"[ぁ-んァ-ヶ一-龥]{2,}", text)
            return [t for t in tokens if t not in self.stopwords]

        nouns = []
        try:
            for token in self._tokenizer.tokenize(text):
                part = token.part_of_speech.split(",")[0]
                surface = token.surface
                if (
                    part == "名詞"
                    and len(surface) >= self.min_length
                    and surface not in self.stopwords
                    and not surface.isdigit()
                ):
                    nouns.append(surface)
        except Exception as e:
            logger.error(f"形態素解析エラー: {e}")

        return nouns

    def _extract_cooccurrence(self, nouns: list[str]) -> list[tuple[str, str, int]]:
        """スライディングウィンドウで共起ペアを抽出"""
        pair_count: Counter = Counter()
        w = self.cooccurrence_window

        for i in range(len(nouns)):
            window = nouns[i + 1 : i + w + 1]
            for other in window:
                if nouns[i] != other:
                    pair = tuple(sorted([nouns[i], other]))
                    pair_count[pair] += 1

        top = pair_count.most_common(self.top_pairs)
        return [(w1, w2, count) for (w1, w2), count in top]
