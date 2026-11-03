# okinawa-watch

沖縄の「今だけ・お得・発見」を元記事へのリンクで探す、APIキー不要の初期PoCです。政治・事件等は設定ルールで抑制し、本文・画像は保存・再配布しません。分類・要約に生成AIを使いません。

## 構成

- `config/sources.json`：情報源、RSS/Atom取得方法、採否と確認状況
- `config/rules.json`：除外ドメイン・キーワード・配信カテゴリ、分野・地域・保持期間
- `scripts/watch.py`：Python 3.12以上・標準ライブラリだけの収集／静的サイト生成
- `web/`：日本語・モバイル対応の一覧。すべて／今だけ／お得／発見、分野、終了日経過の切替
- `.github/workflows/`：テスト、1日2回と手動の収集、GitHub Pages配信

## ローカル実行

```sh
python3 -m unittest discover -s tests -v
python3 scripts/watch.py collect
python3 scripts/watch.py build
python3 -m http.server 8000 --directory work/site
```

`http://localhost:8000` で閲覧します。収集ログは `work/collection-report.json`、データは `data/articles.json`。一部の取得失敗でも続行し、全件失敗時は警告と前回データを残します。

実記事の**手動調査サンプル**を確認する場合：

```sh
python3 scripts/watch.py build --sample --output work/sample-site
python3 -m http.server 8001 --directory work/sample-site
```

自動収集の実測結果とは別です。架空記事は公開データに含めません。

## 設定

情報源は `enabled` で切替。追加時は公開フィードURL・robots・利用条件を確認します。HTML取得は未実装です。除外配列を空にすれば、その種類の除外を無効にできます。初期値の「辺野古」「県知事」「PFAS」等は自由に編集できます。

除外は記事タイトルと配信カテゴリに適用。過去の採用データにも次の収集時に再適用します。除外理由・タイトル・URLは監査ログに記録し、Pagesには公開しません。保持は90日・最大500件です。

分野は `topic_categories` に一致する配信カテゴリを優先し、該当しなければ `topics` のタイトルキーワードを使います。カテゴリは正規化した完全一致で判定し、複数の分野に一致する場合は設定内の順序を優先します。`topic_categories` を空にするとタイトルだけの分類に戻せます。

「今だけ」はタイトル中の年を含む日付と開催・期限表現が根拠。「お得」もタイトルのキーワードで判定します。年省略、相対日付、曖昧な期間は補完しません。分類精度の制約は[検証記録](docs/verification.md)を参照してください。

## Actions / Pages

1. このPRをレビューしてマージ後、リポジトリの **Settings → Pages → Source → GitHub Actions** を選択します。
2. **Actions → Collect and publish → Run workflow** で `main` を実行します。通常は日本時間09:23／21:23頃にも実行（GitHub側の遅延あり）。APIキー・手動Secrets登録は不要で、自動の `GITHUB_TOKEN` を使います。
3. 収集結果は専用の `collected-data` ブランチに保存し、次回に復元します。ワークフローに同ブランチへの書込権限が必要です。ソースコードの `main` にはデータ更新をコミットしません。
4. Actionsのジョブ要約で情報源別件数・失敗・分野分布を確認。`collection-audit-<run_id>` のartifactに除外詳細を30日保存します。

PRではテスト・少量の実取得・静的生成を行い、結果をartifactで確認できます。公開は行いません。既定ブランチのコードだけが配信対象です。Actions／Pagesの実行可否やリポジトリ設定は、初回実行で確認が必要です。

情報源の調査根拠・実取得の成否・受け入れ条件の状況は [docs/verification.md](docs/verification.md) にまとめています。
