/* Calendar-day display decisions shared by the browser and audit/tests. */
(function (root) {
  "use strict";
  const formatter = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Tokyo" });
  function day(value) {
    if (!value) return null;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return date.toISOString().slice(0, 10) === value ? value : null;
    return formatter.format(date);
  }
  function describe(article, policy, today) {
    const end = day(article.timing?.end);
    const start = day(article.timing?.start);
    const event = policy.event_topics.includes(article.topic) || policy.event_keywords.some(k => k && article.title.includes(k));
    const sensitive = event || policy.deadline_keywords.some(k => k && article.title.includes(k));
    const published = day(article.published_at);
    const collected = day(article.collected_at);
    const referenceDate = published || collected;
    const age = referenceDate ? Math.floor((Date.parse(today) - Date.parse(referenceDate)) / 86400000) : null;
    // Publication/collection dates only measure freshness. They never establish event dates.
    let status = "discovery";
    if (end) status = end < today ? "ended" : start && start > today ? "upcoming" : "confirmed";
    else if (event) status = "unverified_event";
    else if (sensitive) status = "unverified_deadline";
    const unverified = status.startsWith("unverified_");
    let hiddenReason = null;
    if (status === "ended") hiddenReason = "confirmed_ended";
    else if (unverified && age === null) hiddenReason = "freshness_unknown";
    else if (unverified && age > policy.unverified_max_age_days) hiddenReason = "old_unverified";
    return {
      status, event, unverified, hidden_reason: hiddenReason,
      reference_date: referenceDate, reference_kind: published ? "published" : collected ? "collected" : null,
      age_days: age
    };
  }
  function rank(state) {
    return state.hidden_reason === "confirmed_ended" ? 2 : state.hidden_reason ? 1 : 0;
  }
  function timestamp(article) {
    const value = article.published_at || article.collected_at;
    return Date.parse(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00+09:00` : value) || 0;
  }
  function entries(articles, policy, today = formatter.format(new Date())) {
    return articles.map(article => ({ article, state: describe(article, policy, today) }))
      .sort((a, b) => rank(a.state) - rank(b.state) || timestamp(b.article) - timestamp(a.article) || a.article.url.localeCompare(b.article.url));
  }
  function visible(entry, options = {}) {
    const { article, state } = entry;
    if (state.hidden_reason === "confirmed_ended" && !options.includeEnded) return false;
    if (state.hidden_reason && state.hidden_reason !== "confirmed_ended" && !options.includeOlder) return false;
    if (options.topic && article.topic !== options.topic) return false;
    if (options.filter === "催し（日付未確認）") return state.status === "unverified_event";
    return !options.filter || options.filter === "すべて" || article.labels.includes(options.filter);
  }
  function report(articles, policy, today = formatter.format(new Date())) {
    const results = entries(articles, policy, today);
    const counts = {};
    for (const { state } of results) {
      const reason = state.hidden_reason || "visible";
      counts[reason] = (counts[reason] || 0) + 1;
    }
    return { evaluated_on_jst: today, policy, counts, articles: results.map(({ article, state }) => ({
      id: article.id, title: article.title, url: article.url, ...state
    })) };
  }
  const api = { day, describe, entries, visible, report };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.OkinawaDisplay = api;
})(globalThis);
