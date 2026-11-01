import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import "./analytics.css";

const initial = { from: "", to: "", status: "completed", aircraft: "", route: "" };
const labels = { overview: "Обзор", threats: "Угрозы", errors: "Ошибки", ratings: "Работа экипажа" };

function Breakdown({ title, rows, onSelect, unit = "событий" }) {
  const max = Math.max(1, ...rows.map(r => r.count));
  return <section className="analytics-card"><h2>{title}</h2>
    {!rows.length ? <p className="muted">Нет данных в выбранной выборке.</p> :
      <div className="breakdown-list">{rows.map(r => <button key={r.label} className="breakdown-row" onClick={() => onSelect(r.label)}>
        <span>{r.label}</span><strong>{r.count} <small>{unit === "проверок" ? "проверок" : `событий · проверок: ${r.sheets}`}</small></strong>
        <span className="breakdown-track"><span style={{ width: `${r.count / max * 100}%` }} /></span>
      </button>)}</div>}
  </section>;
}
function Ratio({ title, rows }) {
  const yes = rows.find(r => r.label === "Да")?.count || 0;
  const no = rows.find(r => r.label === "Нет")?.count || 0;
  const missing = rows.find(r => r.label === "Не указано")?.count || 0;
  return <div className="analytics-ratio"><span>{title}</span><strong>{yes + no ? `${Math.round(100 * yes / (yes + no))}%` : "—"}</strong>
    <small>Да: {yes} из {yes + no} ответов · Нет: {no} · Не указано: {missing}</small></div>;
}
export default function Analytics() {
  const [filters, setFilters] = useState(initial);
  const [applied, setApplied] = useState(initial);
  const [tab, setTab] = useState("overview");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [selection, setSelection] = useState(null);
  const [page, setPage] = useState(0);
  const detailRef = useRef(null);
  useEffect(() => { if (selection) detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [selection]);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(""); setData(null); setSelection(null); setPage(0);
    api.analytics(applied).then(value => { if (active) setData(value); })
      .catch(e => { if (active) setError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [applied, refresh]);
  function select(kind, field, value, title) {
    setSelection({ kind, field, value, title }); setPage(0);
  }
  const base = selection ? data?.[selection.kind] || [] : [];
  const details = selection ? base.filter(r => selection.field == null || String(r[selection.field]) === String(selection.value)) : [];
  const sheetMap = new Map((data?.sheets || []).map(s => [s.id, s]));
  const breakdown = (title, group, kind, field, unit) => <Breakdown title={title} rows={data.groups[group]} unit={unit}
    onSelect={value => select(kind, field, value, `${title}: ${value}`)} />;
  return <section className="page workspace analytics-page">
    <a className="back-link" href="#coordinator">← Расписание проверок</a>
    <div className="page-heading"><div><p className="eyebrow">Координатор программы · LOSA</p><h1>Аналитика наблюдений</h1>
      <p className="muted">Угрозы, ошибки и работа экипажа. Период определяется фактической датой проверки.</p></div>
      <button className="outline" onClick={() => setRefresh(r => r + 1)} disabled={loading}>Обновить</button></div>
    <form className="analytics-filters" onSubmit={e => { e.preventDefault(); setApplied({ ...filters }); }}>
      <label className="field"><span>Начало периода</span><input type="date" value={filters.from} onChange={e => setFilters({ ...filters, from: e.target.value })} /></label>
      <label className="field"><span>Конец периода</span><input type="date" value={filters.to} min={filters.from || undefined} onChange={e => setFilters({ ...filters, to: e.target.value })} /></label>
      <label className="field"><span>Статус</span><select value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })}>
        <option value="completed">Завершённые</option><option value="draft">В работе</option><option value="all">Все с сохранённым листом</option></select></label>
      <label className="field"><span>Тип ВС</span><select value={filters.aircraft} onChange={e => setFilters({ ...filters, aircraft: e.target.value, route: "" })}>
        <option value="">Все типы</option>{data?.options.aircraft.map(a => <option key={a.id} value={a.id}>{a.label}</option>)}</select></label>
      <label className="field"><span>Маршрут</span><input placeholder="Например, KJA → DME" list="analytics-routes" value={filters.route} onChange={e => setFilters({ ...filters, route: e.target.value })} />
        <datalist id="analytics-routes">{data?.options.routes.map(r => <option key={r} value={r} />)}</datalist></label>
      <div className="analytics-filter-actions"><button className="primary" disabled={loading}>Применить</button><button type="button" className="outline" onClick={() => { setFilters(initial); setApplied({ ...initial }); }}>Сбросить</button></div>
    </form>
    {loading && <p role="status">Загружаем аналитику…</p>}
    {error && <div className="notice error" role="alert">{error} <button className="text-button" onClick={() => setRefresh(r => r + 1)}>Повторить</button></div>}
    {data && <>
      <div className="stats-grid analytics-stats">{[["Проверок", data.summary.sheets, "sheets"], ["Угроз", data.summary.threats, "threats"], ["Ошибок", data.summary.errors, "errors"], ["Выставленных оценок", data.summary.scores, "ratings"]].map(([label, count, kind]) =>
        <button className="analytics-stat" key={kind} onClick={() => select(kind, null, null, label)}><span>{label}</span><strong>{count}</strong>
          <small>{kind === "threats" ? `В ${data.summary.sheets_with_threats} проверках` : kind === "errors" ? `В ${data.summary.sheets_with_errors} проверках` : "Просмотреть записи →"}</small></button>)}</div>
      <div className="analytics-tabs" role="tablist" aria-label="Разделы аналитики">{Object.entries(labels).map(([key, label]) =>
        <button key={key} id={`tab-${key}`} role="tab" aria-selected={tab === key} aria-controls="analytics-panel" className={tab === key ? "active" : ""} onClick={() => { setTab(key); setSelection(null); }}>{label}</button>)}</div>
      {!data.summary.sheets && <div className="notice">Нет сохранённых проверок по выбранным условиям. Измените период, тип ВС или статус.</div>}
      <div id="analytics-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
      {tab === "overview" && <div className="analytics-grid">
        {breakdown("Типы ВС", "aircraft", "sheets", "aircraft", "проверок")}
        {breakdown("Маршруты", "routes", "sheets", "route", "проверок")}
        <section className="analytics-card"><h2>Управление угрозами</h2><Ratio title="Эффективный контроль" rows={data.groups.effective} /><Ratio title="Правильные действия" rows={data.groups.correct} /></section>
        <section className="analytics-card"><h2>Качество и состав данных</h2><p>Одна проверка — один сохранённый лист. Участки одного задания не объединяются в число уникальных экипажей.</p>
          <p>Не включены листы без назначения: <strong>{data.quality.unassigned_sheets}</strong> — у них нет подтверждённого статуса завершения.</p>
          <p>Этапы без критериев в текущих шаблонах: <strong>{data.quality.stages_without_criteria.join("; ") || "нет"}</strong>.</p>
          <p className="muted">Отсутствие записи в журнале не подтверждает отсутствие события. Показатели описывают внесённые наблюдения.</p></section>
      </div>}
      {tab === "threats" && <><div className="analytics-ratios"><Ratio title="Эффективный контроль" rows={data.groups.effective} /><Ratio title="Правильные действия" rows={data.groups.correct} /></div><div className="analytics-grid">
        {breakdown("Угрозы по кодам", "threat_codes", "threats", "label")}
        {breakdown("Категории угроз", "threat_categories", "threats", "category")}
        {breakdown("Фазы возникновения угроз", "threat_phases", "threats", "phase")}
        {breakdown("Эффективность контроля", "effective", "threats", "effective")}</div></>}
      {tab === "errors" && <><div className="analytics-ratios"><Ratio title="Удачные действия экипажа" rows={data.groups.successful} /></div><div className="analytics-grid">
        {breakdown("Ошибки по кодам", "error_codes", "errors", "label")}
        {breakdown("Типы ошибок", "error_categories", "errors", "category")}
        {breakdown("Фазы возникновения ошибок", "error_phases", "errors", "phase")}
        {breakdown("Кто обнаружил ошибку", "noticed", "errors", "noticed")}
        {breakdown("Реакция экипажа", "reaction", "errors", "reaction")}
        {breakdown("Последствия ошибок", "result", "errors", "result")}</div></>}
      {tab === "ratings" && <section className="analytics-card"><h2>Оценки по этапам и критериям</h2><p className="muted">Каждый критерий показан в своём этапе и версии шаблона. Нажмите строку для просмотра фактов. Автоматического объединения похожих критериев нет.</p>
        <div className="analytics-table-wrap"><table className="analytics-table"><thead><tr><th>Этап / критерий</th>{[1, 2, 3, 4].map(n => <th key={n}>{n}</th>)}<th>Сохранено без оценки</th></tr></thead>
          <tbody>{data.rating_groups.map(g => <tr key={g.key}><td><button className="text-button" onClick={() => select("ratings", "key", g.key, `${g.stage}: ${g.label}`)}>{g.label}</button><small>{g.stage} · {g.template}</small></td>{g.scores.map((n, i) => <td key={i}><span className={`score-chip score-${i + 1}`}>{n}</span></td>)}<td>{g.missing_saved}</td></tr>)}</tbody></table></div>
        {!data.rating_groups.length && <p>Нет сохранённых оценок.</p>}
        <p className="muted">«Сохранено без оценки» учитывает существующие пустые записи. Отсутствующие записи и незаполненные текущие шаблоны не считаются оценкой 0 и не используются для расчёта полноты исторического листа.</p></section>}
      </div>
      {selection && <section ref={detailRef} className="analytics-card analytics-details" aria-label="Исходные записи"><div className="page-heading"><div><h2>{selection.title}</h2><p className="muted">Записей: {details.length}</p></div><button className="outline" onClick={() => setSelection(null)}>Закрыть</button></div>
        <div className="analytics-table-wrap"><table className="analytics-table"><thead><tr><th>Проверка</th><th>Наблюдение</th><th>Подробности</th></tr></thead><tbody>{details.slice(page * 25, (page + 1) * 25).map((r, i) => {
          const s = sheetMap.get(r.sheet_id); return <tr key={`${page}-${i}`}><td>{s?.number}<small>{s?.date} · {s?.aircraft}<br />{s?.route}</small></td>
            <td>{r.label || "Сохранённый лист"}<small>{r.phase || r.stage || (s?.status === "completed" ? "Завершена" : "В работе")}</small></td>
            <td>{selection.kind === "threats" && <><p>Эффективный контроль: {r.effective}. Правильные действия: {r.correct}.</p><p>{r.comment || "Комментарий не указан"}</p></>}
              {selection.kind === "errors" && <><p>Допустил: {r.who_made}. Обнаружил: {r.noticed}.</p><p>Реакция: {r.reaction}. Результат: {r.result}. Удачные действия: {r.successful}.</p><p>Связанная угроза: {r.threat}. Изменение состояния: {r.condition}.</p><p>{r.comment || "Комментарий не указан"}</p></>}
              {selection.kind === "ratings" && <><p>Оценка: {r.score ?? "Не указана"} · {r.template}</p><p>{r.facts || "Изложение фактов не заполнено"}</p>{r.comment && <p>{r.comment}</p>}</>}
              {selection.kind === "sheets" && <p>Активное управление: {r.pilot_flying}</p>}</td></tr>;
        })}</tbody></table></div>
        {!details.length && <p>Нет записей.</p>}
        {details.length > 25 && <div className="analytics-pagination"><button className="outline" disabled={!page} onClick={() => setPage(p => p - 1)}>Назад</button><span>{page + 1} / {Math.ceil(details.length / 25)}</span><button className="outline" disabled={(page + 1) * 25 >= details.length} onClick={() => setPage(p => p + 1)}>Далее</button></div>}
      </section>}
      <p className="muted analytics-footnote">Данные получены с сервера. «Не указано» учитывается отдельно. Отсутствие связи ошибки с угрозой не означает доказанного отсутствия влияния. Число событий и число проверок имеют разные основания подсчёта.</p>
    </>}
  </section>;
}
