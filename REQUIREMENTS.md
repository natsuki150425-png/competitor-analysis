# 競合分析ツール 要件定義書

## 1. プロジェクト概要

競合サイトのブログ記事を自動収集・分析し、記事構成・見出し・キーワード・SEO要素を
CSV/Excelレポートとして出力するPythonツール。

---

## 2. 機能要件

### 2-1. データ収集
- 競合サイトのURLリストを入力として受け取る
- 各URLの記事をスクレイピングで取得
- robots.txt を尊重し、リクエスト間隔を設ける（デフォルト1秒）

### 2-2. 記事構成・見出し分析
- H1〜H4タグを抽出し、見出し階層ツリーを構造化
- 記事内の段落数・文字数・画像数をカウント
- 見出しの平均文字数・深さを集計

### 2-3. キーワード・トピック抽出
- 本文テキストから形態素解析（janome）で名詞を抽出
- TF-IDF スコアで上位キーワードをランキング
- 共起キーワードペアを抽出

### 2-4. SEOスコア・パフォーマンス分析
- titleタグ・descriptionメタタグの有無と文字数チェック
- OGP（og:title, og:description, og:image）の有無
- canonical URL の有無
- 構造化データ（JSON-LD）の有無
- 内部リンク数・外部リンク数カウント
- ページロード時間の計測（requestsのレスポンスタイム）

### 2-5. レポート出力
- 分析結果をCSV（詳細）＋Excelファイル（サマリー＋詳細シート）で出力
- Excelは複数シートで構成：
  - `summary` : 競合サイト間の比較サマリー
  - `articles` : 記事単位の詳細データ
  - `keywords` : キーワードランキング
  - `headings` : 見出し一覧

---

## 3. 非機能要件

| 項目 | 内容 |
|------|------|
| 言語 | Python 3.10+ |
| 対象OS | Linux / macOS / Windows |
| 並列処理 | ThreadPoolExecutor（デフォルト3スレッド） |
| エラー処理 | スクレイピング失敗時はスキップしてログ記録 |
| ログ | loguru でファイル＆コンソール出力 |
| 設定 | config.yaml で全パラメータ管理 |

---

## 4. ディレクトリ構成

```
competitor_analysis/
├── README.md
├── REQUIREMENTS.md
├── requirements.txt
├── config.yaml              # 設定ファイル
├── src/
│   ├── __init__.py
│   ├── scraper.py           # スクレイピング
│   ├── analyzer.py          # 分析ロジック
│   ├── seo_checker.py       # SEO要素チェック
│   ├── keyword_extractor.py # キーワード抽出
│   └── reporter.py          # CSV/Excel出力
├── tests/
│   ├── test_analyzer.py
│   ├── test_seo_checker.py
│   └── test_keyword_extractor.py
├── main.py                  # エントリーポイント
└── output/                  # 出力ファイル保存先
```

---

## 5. 入力仕様

### URLリストファイル（urls.txt）
```
https://example-competitor1.com/blog/article1
https://example-competitor2.com/blog/article2
```

### コマンドライン
```bash
python main.py --urls urls.txt --output output/ --workers 3
```

---

## 6. 出力仕様

### Excel（competitor_analysis_YYYYMMDD_HHMMSS.xlsx）

**summary シート**
| カラム | 説明 |
|--------|------|
| domain | ドメイン名 |
| article_count | 取得記事数 |
| avg_word_count | 平均文字数 |
| avg_heading_count | 平均見出し数 |
| seo_score_avg | SEOスコア平均 |
| top_keyword | 最頻出キーワード |

**articles シート**
| カラム | 説明 |
|--------|------|
| url | 記事URL |
| title | タイトル |
| word_count | 文字数 |
| h1〜h4_count | 各見出しレベル数 |
| image_count | 画像数 |
| internal_links | 内部リンク数 |
| external_links | 外部リンク数 |
| seo_score | SEOスコア（0〜100） |
| load_time_ms | ロード時間(ms) |
| has_og | OGP有無 |
| has_canonical | canonical有無 |
| has_structured_data | 構造化データ有無 |
