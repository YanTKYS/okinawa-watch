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

Web取得ツールは両URLに対して `Unsupported content-type: application/rss+xml` を返した。これはRSS形式のHTTP応答の確認であり、フィードXMLの正常解析・継続的自動取得・利用許諾の確認ではない。`enabled: true` は収集時に検証を試みる設定。各オリジンのrobotsが取得不能・取得禁止なら、フィード取得まで進まない。404/410のみrobots無しとして扱う。

DEEokinawaの `/atom.xml` と `/index.xml`、食べ歩きアンテナの `/rss` はWebツールで取得不能だった。非公開・存在しないと断定できないため採用していない。まいぷれのRSSは確認できていない。全候補でrobotsのWeb取得は失敗した。

RSSは1回につき各源1リクエスト（別にrobotsを1回）、同一オリジン間2秒以上、15秒タイムアウト、2MB上限。robotsのCrawl-delay・Request-rateも反映し、30秒を超える待ち時間が必要な源は見送る。別オリジンへのリダイレクトは追わない。記事ページ・ページ送り・画像は取得しない。

利用条件変更や取得拒否が分かった場合は直ちに `enabled: false` にする。robotsが許可していることだけで転載許諾を意味しない。初期PoCはリンク紹介に限定する。
