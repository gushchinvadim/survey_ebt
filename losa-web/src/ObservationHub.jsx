import { useEffect, useRef, useState } from "react";
import {
  emptyJournal, newObservation, observationProblem, needsDetails,
  putObservation, removeObservation, searchMistakes, searchThreats, toLocalTime,
} from "./observation-data";

function Choice({ label, value, choices, onChange }) {
  return <label className="field"><span>{label}</span>
    <select value={value ?? ""} onChange={e => onChange(e.target.value || null)}>
      <option value="">Не указано</option>
      {choices.map(([code, text]) => <option value={code} key={code}>{text}</option>)}
    </select>
  </label>;
}
function YesNo(props) {
  return <Choice {...props} value={props.value === null || props.value === undefined ? null : props.value ? "yes" : "no"}
    choices={[["yes", "Да"], ["no", "Нет"]]}
    onChange={value => props.onChange(value === null ? null : value === "yes")} />;
}

export default function ObservationHub({
  journal: supplied, catalog, scratch = {}, onJournalChange, onScratchChange,
  saving, localError, dirty, online, readOnly = false,
}) {
  const journal = supplied || emptyJournal();
  const [modal, setModal] = useState(null);
  const [viewItem, setViewItem] = useState(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const [section, setSection] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [phaseFilter, setPhaseFilter] = useState("");
  const phaseRef = useRef("preflight");
  const dialogRef = useRef(null);

  useEffect(() => {
    function update() {
      if (dialogRef.current?.open) return;
      const elements = [...document.querySelectorAll("[data-observation-phase]")];
      const active = elements.filter(el => {
        const rect = el.getBoundingClientRect();
        return rect.top < window.innerHeight * .55 && rect.bottom > 120;
      }).at(-1);
      if (active) phaseRef.current = active.dataset.observationPhase;
    }
    function focus(e) {
      const code = e.target.closest("[data-observation-phase]")?.dataset.observationPhase;
      if (code) phaseRef.current = code;
    }
    update();
    window.addEventListener("scroll", update, { passive: true });
    document.addEventListener("focusin", focus);
    return () => {
      window.removeEventListener("scroll", update);
      document.removeEventListener("focusin", focus);
    };
  }, []);

  useEffect(() => {
    if (modal && dialogRef.current && !dialogRef.current.open) dialogRef.current.showModal();
    if (!modal && dialogRef.current?.open) dialogRef.current.close();
  }, [modal]);

  useEffect(() => {
    if (!modal) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, [!!modal]);

  const item = readOnly ? viewItem : modal?.id ? scratch[modal.id] : null;
  const event = item?.event;
  const isMistake = item?.kind === "mistake";

  function close() { if (dialogRef.current?.open) dialogRef.current.close(); setModal(null); setViewItem(null); setError(""); }
  function openEditor(kind, existing = null) {
    if (readOnly && !existing) return;
    setError(""); setQuery(""); setType(""); setSection("");
    let id = existing?.id;
    if (!existing) id = Object.keys(scratch).find(key => scratch[key].kind === kind &&
      !journal[kind === "mistake" ? "mistakes" : "threats"].some(row => row.id === key));
    if (!id) {
      try {
        const phase = catalog?.phases.find(p => p.code === phaseRef.current)?.id ?? null;
        existing = newObservation(kind, phase);
        id = existing.id;
      } catch(e) { setError(e.message); return; }
    }
    const current = readOnly ? { kind, event: structuredClone(existing) } : scratch[id] || { kind, event: structuredClone(existing) };
    if (readOnly) setViewItem(current);
    else if (!scratch[id]) onScratchChange({ ...scratch, [id]: current });
    const selected = kind === "mistake" ? catalog?.mistakes.find(row => row.id === current.event.mistake) : catalog?.threats.find(row => row.id === current.event.threat);
    setType(String(kind === "mistake" ? selected?.type_id ?? "" : selected?.type ?? ""));
    setSection(kind === "mistake" && selected ? String(selected.section_id ?? "none") : "");
    setModal({ mode: "edit", id });
  }
  function update(field, value) {
    onScratchChange({ ...scratch, [modal.id]: { ...item, event: { ...event, [field]: value } } });
    setError("");
  }
  function commit(e) {
    e.preventDefault();
    if (readOnly) return;
    const problem = observationProblem(item.kind, event, journal, catalog);
    if (problem) { setError(problem); return; }
    onJournalChange(putObservation(journal, item.kind, event));
    const next = { ...scratch };
    delete next[modal.id];
    onScratchChange(next);
    close();
  }
  function discard() {
    if (!window.confirm("Удалить этот набросок? Зафиксированная запись в журнале останется без изменений.")) return;
    const next = { ...scratch }; delete next[modal.id]; onScratchChange(next); close();
  }
  function remove(kind, row) {
    if (!window.confirm("Удалить наблюдение из журнала? На сервере удаление применится после отправки.")) return;
    try {
      onJournalChange(removeObservation(journal, kind, row.id));
      const next = { ...scratch }; delete next[row.id]; onScratchChange(next);
      setError("");
    } catch(e) { setError(e.message); }
  }
  const name = (kind, row) => {
    const selected = kind === "mistake" ? catalog?.mistakes.find(v => v.id === row.mistake) : catalog?.threats.find(v => v.id === row.threat);
    return selected ? `${selected.code} — ${selected.name || selected.describe}` : "Не выбран справочник";
  };
  const phases = catalog?.phases || [];
  const allRows = [
    ...journal.mistakes.map(row => ({ kind: "mistake", row })),
    ...journal.threats.map(row => ({ kind: "threat", row })),
  ].sort((a,b) => (b.row.observed_at ? Date.parse(b.row.observed_at) : 0) - (a.row.observed_at ? Date.parse(a.row.observed_at) : 0));
  const rows = allRows.filter(({kind,row}) => (!kindFilter || kindFilter === kind) &&
    (!phaseFilter || row.flight_phase === Number(phaseFilter)) &&
    (!query || `${name(kind,row)} ${row.comment}`.toLocaleLowerCase("ru").includes(query.toLocaleLowerCase("ru"))));
  const unsentCount = Object.keys(scratch).length;
  const chosen = event && (isMistake ? catalog?.mistakes.find(row => row.id === event.mistake) : catalog?.threats.find(row => row.id === event.threat));
  const matches = item && catalog ? isMistake
    ? searchMistakes(catalog,query,type,section) : searchThreats(catalog,query,type) : [];
  const typeDescription = isMistake && catalog?.mistake_types.find(row => row.id === Number(type))?.describe;

  return <>
    {error && !modal && <p className="notice error" role="alert">{error}</p>}
    <nav className="observation-toolbar" aria-label="Наблюдения LOSA">
      <div className="observation-toolbar-status" role="status">
        {localError ? "Не сохранено на устройстве" : dirty || unsentCount ? "Есть данные на устройстве" : "Данные получены с сервера"}
        <small>{online ? "Отправка — кнопкой «Сохранить на сервере»" : "Офлайн · данные остаются на устройстве"}</small>
      </div>
      <button type="button" className="observation-add-mistake" disabled={saving || readOnly || !catalog}
        onClick={() => openEditor("mistake")}>+ Ошибка</button>
      <button type="button" className="observation-add-threat" disabled={saving || readOnly || !catalog}
        onClick={() => openEditor("threat")}>+ Фактор угрозы</button>
      <button type="button" className="observation-open-journal" disabled={saving}
        onClick={() => { setQuery(""); setKindFilter(""); setPhaseFilter(""); setError(""); setModal({mode:"journal"}); }}>
        Журнал · {allRows.length}{unsentCount ? ` + ${unsentCount}` : ""}
      </button>
    </nav>

    {modal && <dialog ref={dialogRef} className="observation-dialog" aria-labelledby="observation-dialog-title"
      onCancel={e => { e.preventDefault(); close(); }} onClose={close}>
      <div className="observation-dialog-heading">
        <div><p className="eyebrow">Лист аудита · наблюдения</p>
          <h2 id="observation-dialog-title">{modal.mode === "journal" ? "Журнал наблюдений" : isMistake ? "Ошибка" : "Фактор угрозы"}</h2></div>
        <button type="button" className="observation-close" aria-label="Закрыть, сохранив набросок" onClick={close}>×</button>
      </div>
      {error && <p className="notice error" role="alert">{error}</p>}
      {localError && <p className="notice error" role="alert">{localError}</p>}
      {modal.mode === "journal" ? <>
        <p className="observation-help">Ошибки: {journal.mistakes.length} · Факторы угрозы: {journal.threats.length}.
          Наблюдения можно дополнить позже.</p>
        {!!unsentCount && <section className="observation-scratch-list">
          <h3>Наброски на устройстве</h3>
          {Object.entries(scratch).map(([id, draft]) => <button type="button" key={id}
            onClick={() => openEditor(draft.kind, draft.event)}>
            {draft.kind === "mistake" ? "Ошибка" : "Фактор угрозы"} · {name(draft.kind,draft.event)} · продолжить
          </button>)}
        </section>}
        <div className="observation-filter-grid">
          <label className="field"><span>Поиск</span><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Код, название, комментарий" /></label>
          <Choice label="Вид наблюдения" value={kindFilter} choices={[["mistake","Ошибка"],["threat","Фактор угрозы"]]} onChange={v=>setKindFilter(v||"")} />
          <Choice label="Фаза полёта" value={phaseFilter} choices={phases.map(p=>[p.id,p.label])} onChange={v=>setPhaseFilter(v||"")} />
        </div>
        <div className="observation-journal-list">
          {!rows.length && <p className="observation-empty">Наблюдений пока нет или они не подходят под фильтры.</p>}
          {rows.map(({kind,row}) => <article className={`observation-entry ${kind}`} key={row.id}>
            <div className="observation-entry-meta">
              <span>{kind === "mistake" ? "Ошибка" : "Фактор угрозы"}</span>
              <span>{phases.find(p=>p.id===row.flight_phase)?.label || "Фаза не указана"}</span>
              <time>{row.observed_at ? new Date(row.observed_at).toLocaleString("ru-RU") : "Без времени"}</time>
            </div>
            <h3>{name(kind,row)}</h3>
            {row.comment && <p className="observation-entry-comment">{row.comment}</p>}
            <div className="observation-entry-footer">
              <span className={needsDetails(kind,row) ? "observation-incomplete" : "observation-complete"}>{needsDetails(kind,row) ? "Нужно дополнить" : "Контроль заполнен"}</span>
              {row.threat_id && <small>Связано с угрозой</small>}
              <button type="button" onClick={()=>openEditor(kind,row)}>{readOnly ? "Просмотреть" : "Открыть"}</button>
              {!readOnly && <button type="button" className="observation-delete" onClick={()=>remove(kind,row)}>Удалить</button>}
            </div>
          </article>)}
        </div>
      </> : event && catalog ? <form onSubmit={commit} className="observation-editor">
        <fieldset disabled={readOnly} className="observation-readonly-fieldset">
        <p className="observation-help">Для быстрой фиксации выберите фазу и запись справочника. Подробности контроля можно заполнить позже.
          Изменения в этой форме сохраняются как набросок на устройстве.</p>
        <div className="observation-two-columns">
          <Choice label="Фаза полёта *" value={event.flight_phase}
            choices={phases.map(p=>[p.id,p.label])} onChange={v=>update("flight_phase",v ? Number(v) : null)} />
          <label className="field"><span>Время наблюдения (часовой пояс устройства)</span>
            <input type="datetime-local" value={toLocalTime(event.observed_at)}
              onChange={e=>update("observed_at",e.target.value ? new Date(e.target.value).toISOString() : null)} />
          </label>
        </div>
        <small className="observation-help">Фаза предварительно выбрана по текущему блоку листа — уточните её при необходимости.</small>

        <section className="observation-catalog-section">
          <h3>{isMistake ? "Выбор ошибки" : "Выбор фактора угрозы"}</h3>
          <div className="observation-two-columns">
            <Choice label={isMistake ? "Тип ошибки" : "Категория угрозы"} value={type}
              choices={isMistake ? catalog.mistake_types.map(v=>[v.id,`${v.code} — ${v.name}`]) : catalog.threat_types}
              onChange={v=>{ setType(v||""); setSection(""); setQuery(""); update(isMistake?"mistake":"threat",null); }} />
            {isMistake && <Choice label="Раздел" value={section}
              choices={[...catalog.mistake_sections.filter(s=>!type||s.type_id===Number(type)).map(s=>[s.id,s.name]),["none","Без раздела"]]}
              onChange={v=>{ setSection(v||""); update("mistake",null); }} />}
          </div>
          {typeDescription && <details className="observation-type-help"><summary>Пояснение к типу ошибки</summary><p>{typeDescription}</p></details>}
          <label className="field"><span>Поиск по коду или названию</span><input type="search" value={query}
            onChange={e=>setQuery(e.target.value)} placeholder={isMistake ? "Например: 111 или связь" : "Код или описание фактора угрозы"} /></label>
          <div className="observation-catalog-list" role="radiogroup" aria-label={isMistake ? "Конкретная ошибка" : "Конкретный фактор угрозы"}>
            {matches.slice(0,100).map(row => <label key={row.id} className={chosen?.id===row.id ? "selected" : ""}>
              <input type="radio" name="observation-catalog" checked={chosen?.id===row.id}
                onChange={()=>update(isMistake?"mistake":"threat",row.id)} />
              <span><strong>{row.code}</strong> {row.name || row.describe}</span>
            </label>)}
            {!matches.length && <p>Нет подходящих записей. Измените поиск или фильтры.</p>}
          </div>
          {matches.length>100 && <small className="observation-help">Показаны первые 100 из {matches.length}. Уточните поиск.</small>}
          {chosen && <p className="observation-chosen"><strong>Выбрано:</strong> {chosen.code} — {chosen.name || chosen.describe}</p>}
        </section>

        <label className="field"><span>Краткий комментарий</span><textarea rows={3} value={event.comment}
          onChange={e=>update("comment",e.target.value)} placeholder="Что произошло?" /></label>

        <details className="observation-control-details">
          <summary>Подробности контроля · можно заполнить позже</summary>
          <div className="observation-control-fields">
            {isMistake ? <>
              <div className="observation-two-columns">
                <Choice label="Кто допустил ошибку?" choices={catalog.people} value={event.who_made} onChange={v=>update("who_made",v)} />
                <Choice label="Кто заметил ошибку?" choices={catalog.people} value={event.who_noticed} onChange={v=>update("who_noticed",v)} />
                <Choice label="Реакция экипажа" choices={catalog.reactions} value={event.reaction} onChange={v=>update("reaction",v)} />
                <Choice label="Результат ошибки" choices={catalog.results} value={event.error_result} onChange={v=>update("error_result",v)} />
              </div>
              <YesNo label="Были ли действия экипажа удачными?" value={event.is_action_ok} onChange={v=>update("is_action_ok",v)} />
              <Choice label="Наблюдаемая угроза, повлиявшая на ошибку" value={event.threat_id}
                choices={journal.threats.map(row=>[row.id,name("threat",row)])} onChange={v=>update("threat_id",v)} />
              {!journal.threats.length && <small className="observation-help">Сначала добавьте фактор угрозы в журнал, затем свяжите его с ошибкой.</small>}
              {!!catalog.safety_conditions.length && <fieldset className="observation-safety-links">
                <legend>Связанные изменения состояния безопасности</legend>
                {catalog.safety_conditions.map(row=><label key={row.id}>
                  <input type="checkbox" checked={event.safety_condition_ids.includes(row.id)}
                    onChange={e=>update("safety_condition_ids",e.target.checked
                      ? [...event.safety_condition_ids,row.id] : event.safety_condition_ids.filter(id=>id!==row.id))} />
                  <span>{row.label}</span>
                </label>)}
              </fieldset>}
            </> : <>
              <YesNo label="Был ли контроль за фактором угрозы эффективным?" value={event.was_control_effective} onChange={v=>update("was_control_effective",v)} />
              <YesNo label="Были ли действия экипажа по контролю за фактором угрозы правильными?" value={event.correct_actions} onChange={v=>update("correct_actions",v)} />
            </>}
          </div>
        </details>
        <div className="observation-editor-actions">
          <button type="button" className="observation-discard" onClick={discard}>Удалить набросок</button>
          <button type="button" className="outline" onClick={close}>Дополнить позже</button>
          <button type="submit" className="primary">Зафиксировать в журнале</button>
        </div>
        <p className="observation-help">{readOnly ? "Завершённая проверка: просмотр без изменений."
          : "Фиксация сохраняет запись на устройстве. Для отправки используйте общую кнопку «Сохранить на сервере»."}</p>
        </fieldset>
        {readOnly && <button type="button" className="outline" onClick={close}>Закрыть просмотр</button>}
      </form> : <p>Для справочников подключитесь к серверу и обновите страницу.</p>}
    </dialog>}
  </>;
}
