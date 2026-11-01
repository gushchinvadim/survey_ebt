import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import StageAssessment from "./StageAssessment";
import { mergeStageAssessmentDraft } from "./stage-assessment-data";
import DescentApproachBlock from "./DescentApproachBlock";
import FinalCrewAssessment from "./FinalCrewAssessment";
import ObservationHub from "./ObservationHub";
import CompletionDialog from "./CompletionDialog";
import { completionRequest, scratchCount } from "./completion-data";
import { loadDraft, storeDraft, prepareDemography } from "./draft-store";

function Field({ label, children, hint }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

export default function DemographyForm({ assignmentId, user }) {
  const [draft, setDraft] = useState(null);
  const current = useRef(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [online, setOnline] = useState(navigator.onLine);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [localError, setLocalError] = useState("");
  const [serverVersion, setServerVersion] = useState(null);
  const [completionReview, setCompletionReview] = useState(null);
  const completed = draft?.status === "completed";

  function commit(value) {
    current.current = value;
    setDraft(value);
    try {
      const stored = storeDraft(localStorage, user.id, assignmentId, value);
      current.current = stored;
      setDraft(stored);
      setLocalError("");
    } catch {
      setLocalError(
        "Не удалось сохранить на устройстве. Не закрывайте страницу; проверьте доступное место и настройки браузера.",
      );
    }
  }

  useEffect(() => {
    let active = true;
    let invalidLocal = false;
    current.current = null;
    try {
      const saved = loadDraft(localStorage, user.id, assignmentId);
      if (saved) {
        current.current = saved;
        setDraft(saved);
        setLoading(false);
      }
    } catch (e) {
      invalidLocal = true;
      setError(e.message);
    }
    api
      .openDemography(assignmentId)
      .then((payload) => {
        if (!active) return;
        if (invalidLocal) {
          setServerVersion(payload);
          return;
        }
        if (current.current?.dirty) {
          if (current.current.revision !== payload.revision || payload.status === "completed")
            setServerVersion(payload);
          const migrated = mergeStageAssessmentDraft(current.current.form, payload.form, payload.meta.stage_assessments);
          commit({
            ...current.current,
            status: payload.status,
            assessment_migration_errors: migrated.unmapped,
            form: { ...payload.form, ...current.current.form, stage_assessments: migrated.values },
            meta: payload.meta,
            audit_number: payload.audit_number,
          });
        } else {
          commit({ ...payload, dirty: false, observation_scratch: current.current?.observation_scratch || {} });
        }
      })
      .catch((e) => {
        if (!active) return;
        setError(
          current.current
            ? `Не удалось получить серверный вариант: ${e.message} Локальный черновик сохранён. Отправка потребует действующей сессии и назначения.`
            : e.message,
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [assignmentId, user.id]);

  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  function change(field, value) {
    const form = { ...current.current.form, [field]: value };
    if (field === "is_delay" && !value) form.delay = null;
    commit({ ...current.current, form, dirty: true });
    setNotice("");
  }

  function changeStage(code, value) {
    change("stage_assessments", { ...current.current.form.stage_assessments, [code]: value });
  }

  async function send(e) {
    e.preventDefault();
    if (completed) return;
    setError("");
    setNotice("");
    let data;
    try {
      data = prepareDemography(current.current);
    } catch (e) {
      setError(e.message);
      return;
    }
    if (!online) {
      setNotice(
        "Нет соединения. Изменения остаются на устройстве; отправьте их после подключения.",
      );
      return;
    }
    setSaving(true);
    try {
      const payload = await api.saveDemography(assignmentId, data);
      commit({ ...payload, dirty: false, observation_scratch: current.current?.observation_scratch || {} });
      setServerVersion(null);
      setNotice(Object.keys(current.current?.observation_scratch || {}).length
        ? "Лист сохранён на сервере. Наброски наблюдений остаются только на устройстве — зафиксируйте их в журнале перед отправкой."
        : "Данные листа сохранены на сервере. Проверка остаётся незавершённой.");
    } catch (e) {
      setError(e.message);
      if (e.status === 409) {
        try {
          setServerVersion(await api.openDemography(assignmentId));
        } catch {
          /* Local copy remains untouched. */
        }
      }
    } finally {
      setSaving(false);
    }
  }

  async function beginCompletion() {
    setError(""); setNotice("");
    if (!online) {
      setNotice("Для завершения нужно соединение с сервером. Данные остаются на устройстве.");
      return;
    }
    if (scratchCount(current.current)) {
      setCompletionReview({ blocked: true, scratch_count: scratchCount(current.current) });
      return;
    }
    let data;
    try { data = prepareDemography(current.current); }
    catch (error) { setError(error.message); return; }
    setSaving(true);
    try {
      const review = await api.previewCompletion(assignmentId, completionRequest(data, current.current));
      setCompletionReview({ ...review, data, acknowledged: false });
    } catch(error) {
      setError(error.message);
      if (error.status === 409) {
        try { setServerVersion(await api.openDemography(assignmentId)); } catch {}
      }
    } finally { setSaving(false); }
  }

  async function confirmCompletion() {
    if (!completionReview || completionReview.blocked) return;
    if (!online) { setError("Нет соединения. Подключитесь и повторите завершение."); return; }
    setSaving(true); setError("");
    try {
      const payload = await api.completeAssignment(
        assignmentId, completionRequest(completionReview.data, current.current, completionReview),
      );
      commit({ ...payload, dirty: false, observation_scratch: current.current.observation_scratch || {} });
      setCompletionReview(null); setServerVersion(null);
      setNotice("Проверка сохранена на сервере и завершена. Для уточнений можно вернуть её в работу.");
    } catch(error) {
      setError(error.message);
      if (error.status === 409) {
        setCompletionReview(null);
        try { setServerVersion(await api.openDemography(assignmentId)); } catch {}
      }
    } finally { setSaving(false); }
  }

  async function reopen() {
    if (!online) { setNotice("Для возврата в работу нужно соединение с сервером."); return; }
    setSaving(true); setError("");
    try {
      const previous = current.current;
      const payload = await api.reopenAssignment(assignmentId, serverVersion?.revision ?? previous.revision);
      const next = { ...payload, dirty: previous.dirty || false, observation_scratch: previous.observation_scratch || {} };
      if (previous.dirty) {
        const migrated = mergeStageAssessmentDraft(previous.form, payload.form, payload.meta.stage_assessments);
        next.form = { ...payload.form, ...previous.form, stage_assessments: migrated.values };
        next.assessment_migration_errors = migrated.unmapped;
      }
      const staleLocal = previous.dirty && previous.revision !== payload.revision - 1;
      if (staleLocal) next.revision = previous.revision;
      commit(next); setServerVersion(staleLocal ? payload : null);
      setNotice(staleLocal
        ? "Проверка возвращена в работу. Локальная копия относится к другой версии; сверьте её с серверной перед сохранением."
        : "Проверка возвращена в работу. Существующие данные сохранены; можно внести уточнения.");
    } catch(error) {
      setError(error.message);
      if (error.status === 409) {
        try { setServerVersion(await api.openDemography(assignmentId)); } catch {}
      }
    } finally { setSaving(false); }
  }

  function useServer() {
    if (
      !serverVersion ||
      !window.confirm(
        "Заменить локальный черновик серверным вариантом? Несинхронизированные изменения этого блока будут потеряны.",
      )
    )
      return;
    commit({ ...serverVersion, dirty: false, observation_scratch: current.current?.observation_scratch || {} });
    setServerVersion(null);
    setError("");
    setNotice("Загружен серверный вариант.");
  }

  if (loading && !draft)
    return (
      <div className="loading" role="status">
        Подготавливаем лист аудита…
      </div>
    );
  if (!draft)
    return (
      <section className="page narrow">
        <a href="#auditor" className="back-link">
          ← Мои проверки
        </a>
        <h1>Не удалось открыть форму</h1>
        <p className="notice error" role="alert">
          {error || "Нет данных назначения."}
        </p>
        {serverVersion && (
          <button className="primary" onClick={useServer}>
            Загрузить серверный вариант
          </button>
        )}
      </section>
    );
  const { form, meta } = draft;
  const number = (field, label) => (
    <Field label={label} hint="Полных лет; 0 — менее года, пусто — не указано">
      <input
        type="number"
        inputMode="numeric"
        min="0"
        step="1"
        value={form[field] ?? ""}
        onChange={(e) => change(field, e.target.value)}
      />
    </Field>
  );
  return (
    <section className="page demographic-page with-observation-toolbar">
      <a href="#auditor" className="back-link">
        ← Мои проверки
      </a>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Лист аудита · {draft.audit_number}</p>
          <h1>
            Лист аудита
          </h1>
          <p className="muted">
            {meta.flight_number} · {meta.aircraft} · Назначено на{" "}
            {meta.planned_date}
          </p>
        </div>
        <span className={`badge ${online ? "today" : ""}`}>
          {online ? "Есть подключение" : "Офлайн"}
        </span>
      </div>
      <div className="demographic-progress">
        <span>01</span>
        <div>
          <strong>Лист аудита</strong>
          <small>Общие данные и наблюдения по этапам полёта</small>
        </div>
        <p>{completed ? "Завершена" : "Черновик"}</p>
      </div>
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      {!!draft.assessment_migration_errors?.length && (
        <p className="notice error" role="alert">
          Не удалось сопоставить критерии старого черновика: {draft.assessment_migration_errors.join(", ")}.
          Исходные данные сохранены на устройстве. Перед отправкой проверьте шаблон этапа в админке.
        </p>
      )}
      {localError && (
        <div className="notice error" role="alert">
          {localError}
        </div>
      )}
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      {serverVersion && (
        <div className="notice error">
          На сервере есть другая версия. Она не перезаписала ваши изменения.
          <button type="button" className="text-button" onClick={useServer}>
            Загрузить серверный вариант
          </button>
        </div>
      )}
      {completed && <p className="notice">
        Проверка завершена и открыта для просмотра.
        {draft.dirty && " На устройстве остались изменения, не включённые в завершённую версию."}
        Для уточнений нажмите «Вернуть в работу».
      </p>}
      <form onSubmit={send}>
        <fieldset disabled={saving || completed || !!completionReview} className="demographic-fieldset">
          <section className="demographic-card" data-observation-phase="preflight">
            <div className="demographic-section-title">
              <span>01</span>
              <div>
                <h2>Проверка и маршрут</h2>
                <p>
                  Из назначения координатора. Уточните фактические данные при
                  необходимости.
                </p>
              </div>
            </div>
            <div className="demographic-grid">
              <Field
                label="Номер проверки"
                hint="Присвоен автоматически координатором"
              >
                <input readOnly value={draft.audit_number} />
              </Field>
              <Field
                label="Фактическая дата"
                hint={`Дата по расписанию: ${meta.planned_date}`}
              >
                <input
                  type="date"
                  required
                  value={form.date || ""}
                  onChange={(e) => change("date", e.target.value)}
                />
              </Field>
              <Field
                label="Аэропорт вылета"
                hint={`По расписанию: ${meta.planned_departure}`}
              >
                <input
                  list="demography-airports"
                  maxLength={100}
                  value={form.actual_departure}
                  onChange={(e) => change("actual_departure", e.target.value)}
                  placeholder="Код или название аэропорта"
                />
              </Field>
              <Field
                label="Аэропорт прилёта / запасной"
                hint={`По расписанию: ${meta.planned_arrival}. Можно ввести вручную.`}
              >
                <input
                  list="demography-airports"
                  maxLength={100}
                  value={form.actual_arrival}
                  onChange={(e) => change("actual_arrival", e.target.value)}
                  placeholder="Код или название аэропорта"
                />
              </Field>
              <Field label="Активное управление выполняет">
                <select
                  value={form.pilot_flying || ""}
                  onChange={(e) => change("pilot_flying", e.target.value)}
                >
                  <option value="">Выберите</option>
                  {(meta.pilot_flying_choices || [
                    ["1", "Командир ВС"],
                    ["2", "Второй пилот"],
                    ["3", "Пилот-инструктор"],
                  ]).map(([code, label]) => (
                    <option key={code} value={code}>{label}</option>
                  ))}
                </select>
              </Field>
            </div>
            <datalist id="demography-airports">
              {meta.airports?.map((a, i) => (
                <option key={`${a.airport_code}-${i}`} value={a.airport_code}>
                  {a.airport_name}
                </option>
              ))}
            </datalist>
          </section>
          <section className="demographic-card" data-observation-phase="preflight">
            <div className="demographic-section-title">
              <span>02</span>
              <div>
                <h2>Стаж экипажа</h2>
                <p>
                  Данные сохраняются для этой проверки. Справочник пилотов не
                  изменяется.
                </p>
              </div>
            </div>
            <div className="crew-pair">
              <div className="crew-person">
                <div className="crew-title">
                  <span className="crew-monogram">КВС</span>
                  <div>
                    <h3>Командир ВС</h3>
                    <p>{meta.captain_label}</p>
                  </div>
                </div>
                {number("captain_experience", "Общий стаж лётной работы")}
                {number("captain_type_experience", "Стаж на данном типе ВС")}
              </div>
              <div className="crew-person">
                <div className="crew-title">
                  <span className="crew-monogram">2П</span>
                  <div>
                    <h3>Второй пилот</h3>
                    <p>{meta.officer_label}</p>
                  </div>
                </div>
                {number("first_officer_experience", "Общий стаж лётной работы")}
                {number(
                  "first_officer_type_experience",
                  "Стаж на данном типе ВС",
                )}
              </div>
            </div>
          </section>
          <section className="demographic-card" data-observation-phase="preflight">
            <div className="demographic-section-title">
              <span>03</span>
              <div>
                <h2>Совместная работа и задержка</h2>
                <p>Условия выполнения полётного задания.</p>
              </div>
            </div>
            <div className="demographic-grid">
              <Field label="Работа в экипаже">
                <select
                  value={form.working_together || ""}
                  onChange={(e) => change("working_together", e.target.value)}
                >
                  <option value="">Выберите вариант</option>
                  {meta.working_together_choices.map(([code, label]) => (
                    <option key={code} value={code}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Участок полётного задания">
                <select
                  value={form.leg_number || ""}
                  onChange={(e) => change("leg_number", e.target.value)}
                >
                  <option value="">Выберите вариант</option>
                  {(meta.leg_number_choices || [
                    ["1 из 1", "1 из 1"],
                    ["1 из 2", "1 из 2"],
                    ["2 из 2", "2 из 2"],
                    ["1 из 3", "1 из 3"],
                    ["2 из 3", "2 из 3"],
                    ["3 из 3", "3 из 3"],
                  ]).map(([code, label]) => (
                    <option key={code} value={code}>{label}</option>
                  ))}
                </select>
              </Field>
              <div className="delay-box">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={form.is_delay}
                    onChange={(e) => change("is_delay", e.target.checked)}
                  />
                  <span>Задержка вылета</span>
                </label>
                {form.is_delay && (
                  <Field label="Время задержки, минут">
                    <input
                      type="number"
                      inputMode="numeric"
                      min="1"
                      step="1"
                      value={form.delay ?? ""}
                      onChange={(e) => change("delay", e.target.value)}
                      placeholder="Укажите длительность"
                    />
                  </Field>
                )}
              </div>
            </div>
          </section>
          <StageAssessment
            code="preflight"
            definition={meta.stage_assessments?.preflight}
            value={form.stage_assessments?.preflight}
            onChange={value => changeStage("preflight", value)}
            number="04"
            phase="preflight"
          />
          <StageAssessment
            code="takeoff_climb"
            definition={meta.stage_assessments?.takeoff_climb}
            value={form.stage_assessments?.takeoff_climb}
            onChange={value => changeStage("takeoff_climb", value)}
            number="05"
            phase="takeoff"
          />
          <StageAssessment
            code="cruise"
            definition={meta.stage_assessments?.cruise}
            value={form.stage_assessments?.cruise}
            onChange={value => changeStage("cruise", value)}
            number="06"
            phase="cruise"
          />
          <DescentApproachBlock
            value={form.approach}
            catalog={meta.approach}
            onChange={value => change("approach", value)}
          />
          <StageAssessment
            code="descent_landing"
            definition={meta.stage_assessments?.descent_landing}
            value={form.stage_assessments?.descent_landing}
            onChange={value => changeStage("descent_landing", value)}
            phase="descent"
          />
          <FinalCrewAssessment
            value={form.final_crew_mark}
            catalog={meta.final_crew_mark}
            onChange={value => change("final_crew_mark", value)}
          />
        </fieldset>
        <div className="demographic-savebar">
          <div>
            <strong>
              {localError
                ? "Локальное сохранение недоступно"
                : "Автосохранение на устройстве"}
            </strong>
            <small>
              {draft.localSavedAt && !localError
                ? `Последнее сохранение: ${new Date(draft.localSavedAt).toLocaleTimeString("ru-RU")}`
                : "Изменения сохраняются по мере ввода"}{" "}
              ·{" "}
              {draft.dirty
                ? "Есть изменения для отправки"
                : "Серверный вариант получен"}
            </small>
          </div>
          <div className="form-actions">
            {completed ? <button type="button" className="primary" disabled={saving || !online} onClick={reopen}>
              {saving ? "Возвращаем…" : "Вернуть в работу"}
            </button> : <>
              <button type="button" className="outline" disabled={saving || !!completionReview} onClick={() => {
                commit(current.current);
                setNotice("Попытка локального сохранения выполнена. Проверьте статус автосохранения.");
              }}>Сохранить на устройстве</button>
              <button className="primary" disabled={saving || !!completionReview}>
                {saving ? "Отправляем…" : "Сохранить на сервере"}
              </button>
              <button type="button" className="completion-finish-button" disabled={saving || !!completionReview || !online} onClick={beginCompletion}>
                Завершить проверку
              </button>
            </>}
          </div>
        </div>
        <p className="workspace-note">
          {completed ? "Завершённый лист доступен для просмотра. Изменения — после возврата в работу."
            : "Обычное сохранение оставляет черновик. Завершение выполняется отдельной кнопкой при подключении к серверу."}
        </p>
      </form>
      <ObservationHub
        journal={form.observations}
        catalog={meta.observations}
        scratch={draft.observation_scratch || {}}
        onJournalChange={value => change("observations", value)}
        onScratchChange={value => commit({ ...current.current, observation_scratch: value })}
        saving={saving || !!completionReview}
        readOnly={completed}
        localError={localError}
        dirty={draft.dirty}
        online={online}
      />
      {completionReview && <CompletionDialog
        review={completionReview}
        busy={saving}
        error={error}
        onCancel={() => { setCompletionReview(null); setError(""); }}
        onConfirm={confirmCompletion}
        onAcknowledge={value => setCompletionReview({ ...completionReview, acknowledged: value })}
      />}
    </section>
  );
}
