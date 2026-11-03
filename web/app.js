"use strict";
let articles = [];
let policy;
let filter = "すべて";
const $ = (id) => document.getElementById(id);
const display = OkinawaDisplay;
function dateLabel(value) {
  const day = display.day(value);
  return day ? day.replaceAll("-", "/") : "未確認";
}
function element(tag, content, className) {
  const node = document.createElement(tag);
  if (content) node.textContent = content;
  if (className) node.className = className;
  return node;
}
function originalLink(article) {
  try {
    const url = new URL(article.url);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return null;
    const link = element("a", article.title);
    link.href = url.href;
    return link;
  } catch { return null; }
}
function hiddenReason(state) {
  if (state.hidden_reason === "confirmed_ended") return "確認できた終了日を経過";
  if (state.hidden_reason === "freshness_unknown") return "公開日・初回取得日が不明で、掲載の新しさを確認できない";
  const basis = state.reference_kind === "published" ? "公開日" : "初回取得日";
  return `${basis} ${dateLabel(state.reference_date)} から${state.age_days}日経過（通常表示は${policy.unverified_max_age_days}日以内）。開催日・期限は未確認`;
}
function cardFor({ article, state }) {
  const link = originalLink(article);
  if (!link) return null;
  const li = element("li");
  const card = element("article", null, state.status === "ended" ? "ended" : "");
  const meta = element("div", null, "meta");
  article.labels.forEach(label => meta.append(element("span", label, `tag ${label === "お得" ? "deal" : ""}`)));
  meta.append(element("span", article.topic), element("span", article.region || "地域未特定"));
  const states = {
    unverified_event: "開催日未確認", unverified_deadline: "期限未確認",
    upcoming: "開催・開始予定（日付確認済み）", confirmed: "開催日・期限確認済み", ended: "終了日経過"
  };
  if (states[state.status]) meta.append(element("span", states[state.status], `tag ${state.unverified ? "unverified" : "verified"}`));
  const h3 = element("h3");
  h3.append(link);
  const source = element("div", null, "meta");
  source.append(element("span", article.source_name));
  if (article.published_at) {
    const time = element("time", `公開 ${dateLabel(article.published_at)}`);
    time.dateTime = article.published_at;
    source.append(time);
  } else source.append(element("span", "公開日不明"));
  const collected = element("time", `初回取得 ${dateLabel(article.collected_at)}`);
  if (article.collected_at) collected.dateTime = article.collected_at;
  source.append(collected);
  card.append(meta, h3, source);
  if (state.unverified) card.append(element("p", `${state.event ? "開催日" : "期限"}は未確認です。公開日・初回取得日は${state.event ? "開催日" : "期限"}を示しません。最新情報は元記事でご確認ください。`, "freshness"));
  if (article.timing) {
    const start = article.timing.start;
    const end = article.timing.end;
    const period = start === end ? dateLabel(end) : start ? `${dateLabel(start)}〜${dateLabel(end)}` : `${dateLabel(end)}まで`;
    card.append(element("p", `${period} · 開催日・期限（タイトルで確認）`, "deadline"));
  }
  if (state.hidden_reason && state.hidden_reason !== "confirmed_ended") card.append(element("p", `過去掲載・鮮度未確認：${hiddenReason(state)}`, "freshness"));
  if (article.provenance === "manual_research") card.append(element("span", "手動調査サンプル", "sample-label"));
  li.append(card);
  return li;
}
function selectFilter(value) {
  filter = value;
  document.querySelectorAll("[data-filter]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.filter === value)));
  render();
}
function render() {
  const entries = display.entries(articles, policy);
  const visible = entries.filter(entry => display.visible(entry, {
    filter, topic: $("topic").value, includeEnded: $("expired").checked, includeOlder: $("older").checked
  }));
  $("count").textContent = `${visible.length}件`;
  $("empty").hidden = visible.length > 0;
  $("empty").textContent = !articles.length ? "収集できた記事はまだありません。取得先の確認・収集が完了すると、ここに表示されます。"
    : filter === "今だけ" ? "この条件に合う日付確認済みの情報はありません。開催日未確認の催しは、別の入口から探せます。"
    : "この条件に合う情報はありません。分類や分野、過去掲載の表示を変えてみてください。";
  $("empty-events").hidden = !articles.length || filter !== "今だけ" || visible.length > 0;
  $("filter-help").textContent = filter === "催し（日付未確認）"
    ? `開催日は未確認の催しです。通常は公開日（不明なら初回取得日）から${policy.unverified_max_age_days}日以内を表示します。開催中を保証しません。`
    : "「今だけ」は日付確認済み。「催し（日付未確認）」では、年などを補わずに掲載の新しい催しを探せます。";
  $("articles").replaceChildren(...visible.map(cardFor).filter(Boolean));
  const hidden = entries.filter(entry => entry.state.hidden_reason);
  $("visibility-summary").textContent = `通常表示から外す情報・理由（${hidden.length}件）`;
  $("visibility-log").replaceChildren(...hidden.map(({ article, state }) => {
    const li = element("li");
    const link = originalLink(article);
    if (link) li.append(link);
    li.append(element("p", hiddenReason(state), "freshness"));
    return li;
  }));
}
async function init() {
  try {
    const response = await fetch("articles.json", { cache: "no-store" });
    if (!response.ok) throw new Error("data_unavailable");
    const data = await response.json();
    articles = data.articles;
    policy = data.display_policy;
    $("freshness-help").textContent = `日付未確認の催しや期間限定の話題は、公開日（不明なら初回取得日）から${policy.unverified_max_age_days}日以内を通常表示します。古い・掲載日不明の情報はチェックで表示でき、理由も確認できます。表示を増やすと、過去掲載の情報は通常の情報より後に並びます。`;
    $("updated").textContent = data.updated_at ? `一覧更新 ${dateLabel(data.updated_at)}（日本時間） · 表示区分ごとの新着順` : "自動収集はまだ完了していません。";
    if (data.sample_mode) {
      $("notice").hidden = false;
      $("notice").textContent = "手動で公開ページを確認した調査サンプルです。自動収集の成功を示すものではありません。掲載日と開催日は異なります。";
    }
    [...new Set(articles.map(a => a.topic))].sort().forEach(topic => {
      const option = element("option", topic); option.value = topic; $("topic").append(option);
    });
    document.querySelectorAll("[data-filter]").forEach(button => button.addEventListener("click", () => selectFilter(button.dataset.filter)));
    $("empty-events").addEventListener("click", () => { $("topic").value = ""; selectFilter("催し（日付未確認）"); });
    ["topic", "expired", "older"].forEach(id => $(id).addEventListener("change", render));
    render();
    setInterval(render, 60_000);
    try {
      const statusResponse = await fetch("status.json", { cache: "no-store" });
      if (statusResponse.ok) {
        const status = await statusResponse.json();
        const failed = status.sources?.filter(s => ["failed", "blocked"].includes(s.status)) || [];
        if (failed.length && !data.sample_mode) {
          $("notice").hidden = false;
          $("notice").textContent = `${failed.length}件の情報源を取得できませんでした。以前の収集結果を表示しています。詳しくは取得ログをご確認ください。`;
        }
      }
    } catch { /* Articles remain usable if status is unavailable. */ }
  } catch {
    $("updated").textContent = "情報を読み込めませんでした。";
    $("empty").hidden = false;
    $("empty").textContent = "通信状況を確認して、ページを再読み込みしてください。";
  }
}
init();
