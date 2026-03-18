"""
main.py
競合記事分析ツール エントリーポイント

Usage:
  python main.py --urls urls.txt
  python main.py --urls urls.txt --output output/ --workers 3 --delay 1.5
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml
from loguru import logger
from tqdm import tqdm

from src.scraper import Scraper, ScraperConfig
from src.analyzer import ArticleAnalyzer
from src.seo_checker import SeoChecker
from src.keyword_extractor import KeywordExtractor
from src.reporter import Reporter


# ── ログ設定 ────────────────────────────────────────────────
logger.remove()
logger.add(sys.stderr, level="INFO", colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
logger.add("output/analysis.log", level="DEBUG", rotation="10 MB", encoding="utf-8")


def load_config(config_path: str = "config.yaml") -> dict:
    try:
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning(f"{config_path} が見つかりません。デフォルト設定を使用します。")
        return {}


def load_urls(filepath: str) -> list[str]:
    path = Path(filepath)
    if not path.exists():
        logger.error(f"URLファイルが見つかりません: {filepath}")
        sys.exit(1)
    urls = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    logger.info(f"{len(urls)} 件のURLを読み込みました")
    return urls


def analyze_articles(
    urls: list[str],
    config: dict,
    workers: int,
    delay: float,
):
    # インスタンス生成
    scraper_cfg = ScraperConfig(
        request_delay_sec=delay,
        timeout_sec=config.get("scraping", {}).get("timeout_sec", 15),
        max_retries=config.get("scraping", {}).get("max_retries", 3),
        user_agent=config.get("scraping", {}).get("user_agent", "CompetitorAnalysisBot/1.0"),
        respect_robots_txt=config.get("scraping", {}).get("respect_robots_txt", True),
    )
    scraper   = Scraper(scraper_cfg)
    analyzer  = ArticleAnalyzer()
    seo       = SeoChecker(config.get("seo", {}))
    extractor = KeywordExtractor(config.get("analysis", {}))

    structures = []
    seo_results = []
    kw_results = []

    logger.info(f"スクレイピング開始（{workers}スレッド）...")

    # スクレイピングは並列、分析はスレッドセーフ
    raw_articles = [None] * len(urls)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(scraper.fetch, url): i for i, url in enumerate(urls)}
        with tqdm(total=len(urls), desc="スクレイピング中", unit="記事") as pbar:
            for future in as_completed(future_map):
                idx = future_map[future]
                raw_articles[idx] = future.result()
                pbar.update(1)

    logger.info("分析処理を開始...")
    for raw in tqdm(raw_articles, desc="分析中", unit="記事"):
        if raw is None:
            continue
        structure = analyzer.analyze(raw)
        seo_r     = seo.check(raw)
        kw_r      = extractor.extract(raw.url, raw.domain, structure.body_text)

        structures.append(structure)
        seo_results.append(seo_r)
        kw_results.append(kw_r)

    # TF-IDFは全記事まとめて計算
    logger.info("TF-IDF計算中...")
    kw_results = extractor.extract_tfidf(kw_results)

    return structures, seo_results, kw_results


def main():
    parser = argparse.ArgumentParser(description="競合記事分析ツール")
    parser.add_argument("--urls",    required=True, help="URLリストファイル（1行1URL）")
    parser.add_argument("--config",  default="config.yaml", help="設定ファイルパス")
    parser.add_argument("--output",  default="output", help="出力ディレクトリ")
    parser.add_argument("--workers", type=int, default=None, help="並列スレッド数")
    parser.add_argument("--delay",   type=float, default=None, help="リクエスト間隔（秒）")
    args = parser.parse_args()

    config  = load_config(args.config)
    urls    = load_urls(args.urls)
    workers = args.workers or config.get("scraping", {}).get("workers", 3)
    delay   = args.delay   or config.get("scraping", {}).get("request_delay_sec", 1.0)

    structures, seo_results, kw_results = analyze_articles(urls, config, workers, delay)

    # レポート出力
    reporter = Reporter(
        output_dir=args.output,
        config=config.get("output", {})
    )
    output_files = reporter.generate(structures, seo_results, kw_results)

    logger.success("✅ 分析完了！出力ファイル:")
    for name, path in output_files.items():
        logger.success(f"  {name}: {path}")


if __name__ == "__main__":
    main()
