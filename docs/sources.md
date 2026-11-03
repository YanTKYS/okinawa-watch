# 情報源の調査（2026-11-03）

公開ページはWeb取得ツールで確認。収集プログラムからのHTTP実測とは区別する。調査時点のタイトル・URL・公開日だけを `data/research-sample.json` に保存し、本文・画像は保存していない。

| 候補 | 確認した内容 | 取得判断 |
|---|---|---|
| [号外NET 沖縄エリア](https://goguynet.jp/okinawa/) | 那覇、沖縄市・うるま市、浦添市・宜野湾市の地域リンク。イベント・店舗等 | 那覇・沖縄市／うるま市の2地域を小規模RSS対象にする。同じ媒体なので媒体の多様性は不足 |
| [まいぷれ 那覇・浦添・豊見城](https://naha.mypl.net/) | 買い物、美容、学び、暮らし等の多分野 | RSS・robots・利用条件未確認のため無効。HTML取得を推測で実装しない |
| [沖縄食べ歩きアンテナ](https://tabearuki.okinawa/) | 個人ブログ等のグルメ記事を集約 | 配信・robots・利用条件未確認、グルメ偏重のため無効。リンク先ブログも巡回しない |
| [DEEokinawa](https://www.dee-okinawa.com/) | 文化、施設、街の小さな発見など。無断転載禁止表記あり | 自動取得は無効。フィード・robots確認未了。調査サンプルは短いタイトルとリンクだけ |

## フィード確認の範囲

- <https://naha.goguynet.jp/feed/>
- <https://okinawa-uruma.goguynet.jp/feed/>

Web取得ツールは両URLに対して `Unsupported content-type: application/rss+xml` を返した。この段階ではRSS形式のHTTP応答だけを確認。その後、[GitHub Actions run 41652745895](https://github.com/YanTKYS/okinawa-watch/actions/runs/41652745895)で両源のrobots検査とRSS解析に成功し、各10件を取得・採用した。継続稼働や利用許諾の確認とは区別する。`enabled: true` は収集時に検証を試みる設定。各オリジンのrobotsが取得不能・取得禁止なら、フィード取得まで進まない。404/410のみrobots無しとして扱う。

DEEokinawaの `/atom.xml` と `/index.xml`、食べ歩きアンテナの `/rss` はWebツールで取得不能だった。非公開・存在しないと断定できないため採用していない。まいぷれのRSSは確認できていない。全候補でrobotsのWebツール取得は失敗したが、号外NETの2地域はActionsからの取得と検査が成功した。

RSSは1回につき各源1リクエスト（別にrobotsを1回）、同一オリジン間2秒以上、15秒タイムアウト、2MB上限。robotsのCrawl-delay・Request-rateも反映し、30秒を超える待ち時間が必要な源は見送る。別オリジンへのリダイレクトは追わない。記事ページ・ページ送り・画像は取得しない。

利用条件変更や取得拒否が分かった場合は直ちに `enabled: false` にする。robotsが許可していることだけで転載許諾を意味しない。初期PoCはリンク紹介に限定する。

## 2026-11-04：別媒体・個人ブログ・店舗施設の追加調査

[候補の実取得監査](logs/source-audit-2026-11-04.json)は [Actions run 41662244605](https://github.com/YanTKYS/okinawa-watch/actions/runs/41662244605) で実行。本文・画像・要約は保存せず、RSSが配信したタイトル・URL・公開日・カテゴリだけを記録した。技術的に取得できることと、定期収集への採否を分ける。

| 候補・種別 | 配信・robotsの確認 | 利用条件・採否 |
|---|---|---|
| [ジャブログ](https://hiija.net/hiija-profile/)（個人ブログ） | [RSS](https://hiija.net/feed/)を実解析、robots取得・検査成功、10件 | [リンク方針・著作権](https://hiija.net/privacypolicy/)で公開ページへのリンク自由、iframe・画像直リンク禁止、本文・画像の無断転載禁止を確認。見出しとURLによるリンク紹介だけに限定して採用。県外2件を配信カテゴリで除外し沖縄8件を対象とする |
| [沖縄移住ライフハック](https://okinawa-iju.info/about)（個人ブログ） | [RSS](https://okinawa-iju.info/feed/)を実解析、robots取得・検査成功、10件 | [著作権等の規定](https://okinawa-iju.info/terms-disclaimer-privacypolicy)に商用・非商用を問わず転載・改編・再配布禁止。自然・暮らしの内容は適合するが、RSS見出しの公開一覧への再掲載条件が未確認のため定期収集は無効。現時点の代替はリンク紹介方針が確認できたジャブログ |
| [DEEokinawa](https://www.dee-okinawa.com/)（地域媒体） | robots取得成功。設定中の `/index.xml` はDTDを含む応答で安全なXML解析が拒否。RSSとして実取得成功とは扱わない | 無断転載禁止表記を確認。文化・街の発見に適合するが公開RSS URL未確認のため無効維持。XML保護を緩めたりHTML本文を取得したりして補わない |
| [沖縄こどもの国](https://www.okzm.jp/)（施設） | `/feed/` が `application/rss+xml` を返すことはWebツールで確認。収集プログラムによるrobots・RSS解析は未実測 | [免責事項](https://www.okzm.jp/immunity/)に無断コンテンツ使用禁止の記載。RSS見出しの一覧掲載条件を整理するまで採用保留。取得できたと断定しない |
| [市場の古本屋ウララ](https://urarabooks.stores.jp/about)（店舗） | 公式通販のABOUTから店舗ブログ `https://urarabooks.ti-da.net/` を確認。Web取得は403 | RSS URL・robots・利用条件は未確認。拒否を迂回せず保留。通販の商品・価格を記事として転用しない |
| [feliz](https://www.feliz-style.jp/hpgen/HPB/categories/1892.html)（店舗） | 公式リンク集にブログへの案内とRSSアイコンを確認したが、公開RSS URLとrobotsは未確認 | 公式リンク集のリンクフリー方針を確認。HTML自動取得は実装せず、配信確認まで保留。SNSページは取得しない |

採用元の `terms.checked_at`・`terms.url`・`verification` を `config/sources.json` に保存した。リンク自由やrobots許可は本文・画像の転載許諾を意味しない。既存方針と同様、見出しのリンク紹介を越える再利用はしない。

`config/source-candidates.json` は手動の再調査対象。`skip_reason` のある源は監査でも通信しない。利用条件やURLを確認してから設定を更新する。定期収集では `config/sources.json` の有効な源だけを使い、候補を推測で有効化しない。候補監査は通常CIから外し、採否が済んだ源への不要な反復アクセスを避けた。

追加前後の件数・住民にとっての有用性は [情報源の比較評価](source-diversity.md) を参照。
