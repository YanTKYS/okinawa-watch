"use strict";
let articles = [];
let filter = "すべて";
const $ = (id) => document.getElementById(id);
const todayJst = () => new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Tokyo" }).format(new Date());
function dateLabel(value) {
  if (!value) return "未確認";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value.replaceAll("-", "/");
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "未確認" : new Intl.DateTimeFormat("ja-JP", { timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}
function element(tag, content, className) {
  const node = document.createElement(tag);
  if (content) node.textContent = content;
  if (className) node.className = className;
  return node;
}
function isEnded(article) { return !!article.timing?.end && article.timing.end < todayJst(); }
function render() {
  const visible = articles.filter(a => ($("expired").checked || !isEnded(a)) && (filter === "すべて" || a.labels.includes(filter)) && (!$('topic').value || a.topic === $('topic').value));
  $("count").textContent = `${visible.length}件`;
  $("empty").hidden = visible.length > 0;
  $("empty").textContent = articles.length ? "この条件に合う情報はありません。分類や分野を変えてみてください。" : "収集できた記事はまだありません。取得先の確認・収集が完了すると、ここに表示されます。";
  $("articles").replaceChildren(...visible.map(a => {
    const li = element("li");
    const card = element("article", null, isEnded(a) ? "ended" : "");
    const meta = element("div", null, "meta");
    a.labels.forEach(label => meta.append(element("span", label, `tag ${label === "お得" ? "deal" : ""}`)));
    meta.append(element("span", a.topic), element("span", a.region || "地域未特定"));
    const h3 = element("h3");
    const link = element("a", a.title);
    // Guard even edited JSON; textContent keeps all feed titles inert.
    let url;
    try { url = new URL(a.url); } catch { return li; }
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return li;
    link.href = url.href;
    h3.append(link);
    const source = element("div", null, "meta");
    source.append(element("span", a.source_name));
    const time = element("time", `${a.published_at ? "公開" : "取得"} ${dateLabel(a.published_at || a.collected_at)}`);
    time.dateTime = a.published_at || a.collected_at;
    source.append(time);
    card.append(meta, h3, source);
    if (a.timing) {
      const start = a.timing.start ? `${dateLabel(a.timing.start)}${a.timing.start === a.timing.end ? "" : "〜"}` : "";
      card.append(element("p", `${isEnded(a) ? "終了日経過 · " : ""}${start}${a.timing.start === a.timing.end ? "" : dateLabel(a.timing.end)}${a.timing.start ? " 開催・期限（タイトルで確認）" : " まで（タイトルで確認）"}`, "deadline"));
    }
    if (a.provenance === "manual_research") card.append(element("span", "手動調査サンプル", "sample-label"));
    li.append(card);
    return li;
  }));
}
async function init() {
  try {
    const response = await fetch("articles.json", { cache: "no-store" });
    if (!response.ok) throw new Error("data_unavailable");
    const data = await response.json();
    articles = data.articles.sort((a,b) => (b.published_at || b.collected_at).localeCompare(a.published_at || a.collected_at));
    $("updated").textContent = data.updated_at ? `一覧更新 ${dateLabel(data.updated_at)}（日本時間） · 新着順` : "自動収集はまだ完了していません。";
    if (data.sample_mode) {
      $("notice").hidden = false;
      $("notice").textContent = "手動で公開ページを確認した調査サンプルです。自動収集の成功を示すものではありません。掲載日と開催日は異なります。";
    }
    [...new Set(articles.map(a => a.topic))].sort().forEach(topic => {
      const option = element("option", topic); option.value = topic; $("topic").append(option);
    });
    document.querySelectorAll("[data-filter]").forEach(button => button.addEventListener("click", () => {
      filter = button.dataset.filter;
      document.querySelectorAll("[data-filter]").forEach(b => b.setAttribute("aria-pressed", String(b === button)));
      render();
    }));
    $("topic").addEventListener("change", render);
    $("expired").addEventListener("change", render);
    render();
    // Refresh date-dependent visibility if a tab stays open past midnight.
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
