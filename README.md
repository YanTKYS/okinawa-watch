# okinawa-watch

沖縄の「今だけ・お得・発見」を元記事へのリンクで探す、APIキー不要の初期PoCです。政治・事件等は設定ルールで抑制し、本文・画像は保存・再配布しません。分類・要約に生成AIを使いません。

## 構成

- `config/sources.json`：情報源、RSS/Atom取得方法、採否と確認状況
- `config/rules.json`：除外ドメイン・キーワード・配信カテゴリ、分野・地域・保持期間
- `scripts/watch.py`：Python 3.12以上・標準ライブラリだけの収集／静的サイト生成
- `web/`：日本語・モバイル対応の一覧。すべて／今だけ／お得／発見、日付未確認の催し、分野、終了日経過・古い掲載情報の切替
- `.github/workflows/`：テスト、1日2回と手動の収集、GitHub Pages配信

## デザインとfavicon

- 見た目は [Microsoft Fluent 2](https://fluent2.microsoft.design/) の考え方を**部分的に参考**にした独自実装です。フラットな白〜淡灰のサーフェス、控えめな境界線、カード・タブ・コマンドバー（絞り込み操作エリア）の階層を取り入れ、色と文言はサイト独自のものを維持しています。Fluent 2準拠・公式コンポーネントではなく、外部CDN・Webフォント・ライブラリも使いません。参考にした比較は [design-lab](https://github.com/YanTKYS/design-lab/blob/main/docs/comparison-guide.md) です。
- 開催日未確認・過去掲載・終了日経過に関する注意表示は、デザイン変更でも削除・弱体化しません。表示判定（`display.js`／`app.js`）はデザインと切り離して扱います。
- `web/favicon.svg` は位置ピンと発見の点だけのオリジナルSVGです（外部ロゴ・公式シンボル不使用）。白い縁取りで明暗どちらのブラウザテーマでも判別でき、`index.html` から相対パスで参照するため、`/okinawa-watch/` のサブパスでも取得できます。`watch.py build` が `web/` 内の全ファイルをコピーするため追加設定は不要です。

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

情報源の `publisher` は地域別フィードをまとめる媒体名です。`include_categories`（空なら制限なし）・`exclude_categories` で源固有の配信カテゴリも正規化した完全一致で制御できます。これは全体の除外ルールに追加され、既存記事にも再適用されます。

除外は記事タイトルと配信カテゴリに適用。過去の採用データにも次の収集時に再適用します。除外理由・タイトル・URLは監査ログに記録し、Pagesには公開しません。保持は90日・最大500件です。

分野は `topic_categories` に一致する配信カテゴリを優先し、該当しなければ `topics` のタイトルキーワードを使います。カテゴリは正規化した完全一致で判定し、複数の分野に一致する場合は設定内の順序を優先します。`topic_categories` を空にするとタイトルだけの分類に戻せます。

「今だけ」はタイトル中の年を含む日付と開催・期限表現が根拠。「お得」もタイトルのキーワードで判定します。年省略、相対日付、曖昧な期間は補完しません。分類精度の制約は[検証記録](docs/verification.md)を参照してください。

## 日付と掲載の新しさ

- 「今だけ」は開催日・期限を確認できるものだけ。「催し（日付未確認）」では年を推測せずに催しを探せます。各記事に開催日未確認・期限未確認・日付確認済み等を表示します。
- 未確認の催し・期間限定の話題は、公開日（不明なら初回取得日）から14日以内を通常表示します。`config/rules.json` の `display.unverified_max_age_days` で変更でき、0は当日分だけです。初回取得日を再収集日で更新しないため、再取得だけで掲載が新しくなることはありません。
- 古い・掲載日不明の未確認情報、確認できた終了日の翌日以降の情報は、それぞれチェックで表示できます。戻した情報は通常の記事より後に並びます。古さから終了済みとは判定しません。
- 公開日・初回取得日・開催日を区別して表示します。「通常表示から外す情報・理由」でタイトル・元記事URL・非表示理由を確認できます。`display.event_topics`・`event_keywords`・`deadline_keywords` で未確認情報を探す手掛かりも変更できます。

表示判定は閲覧時の日本時間で更新します。静的生成時の設定を変更したら再ビルドしてください。ブラウザと同じ判定の監査ログを、Node.js（Actionsには用意済み）でも生成できます。本番の収集・静的生成には追加パッケージは不要です。

```sh
node scripts/display-report.cjs data/articles.json > work/display-report.json
node --test tests/display.test.cjs
```

第2引数に `2026-11-03` 等を渡すと評価日を固定できます。PRのCI artifactには実取得データの `display-report.json` も含まれます。

## Actions / Pages

1. このPRをレビューしてマージ後、リポジトリの **Settings → Pages → Source → GitHub Actions** を選択します。
2. **Actions → Collect and publish → Run workflow** で `main` を実行します。通常は日本時間09:23／21:23頃にも実行（GitHub側の遅延あり）。APIキー・手動Secrets登録は不要で、自動の `GITHUB_TOKEN` を使います。
3. 収集結果は専用の `collected-data` ブランチに保存し、次回に復元します。ワークフローに同ブランチへの書込権限が必要です。ソースコードの `main` にはデータ更新をコミットしません。
4. Actionsのジョブ要約で情報源別件数・失敗・分野分布を確認。`collection-audit-<run_id>` のartifactに除外詳細を30日保存します。

PRではテスト・少量の実取得・静的生成を行い、結果をartifactで確認できます。公開は行いません。既定ブランチのコードだけが配信対象です。Actions／Pagesの実行可否やリポジトリ設定は、初回実行で確認が必要です。

情報源の調査根拠・実取得の成否・受け入れ条件の状況は [docs/verification.md](docs/verification.md) にまとめています。

別媒体の取得・条件確認と追加前後の評価は [docs/source-diversity.md](docs/source-diversity.md)。CIの `source-comparison.json` では、号外NETの2地域を1媒体として、採用全件と通常表示それぞれの媒体・分野の比率を確認できます。
