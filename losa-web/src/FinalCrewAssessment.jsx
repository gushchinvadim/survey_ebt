import { emptyFinalCrew } from "./final-crew-data";

export default function FinalCrewAssessment({ value, catalog, onChange }) {
  if (!catalog) return (
    <section className="demographic-card">
      <h2>Итоговая оценка</h2>
      <p>Подключитесь к серверу и обновите форму, чтобы загрузить новый блок. Локальный черновик сохранён.</p>
    </section>
  );
  const data = value || emptyFinalCrew();
  const change = (field, next) => onChange({ ...data, [field]: next });
  const rated = catalog.scores.filter(({ field }) => data[field] !== null && data[field] !== undefined).length;
  return (
    <section className="demographic-card final-crew-card" aria-labelledby="final-crew-title">
      <div className="demographic-section-title">
        <span>08</span>
        <div>
          <h2 id="final-crew-title">Итоговая оценка</h2>
          <p>Общее впечатление о работе экипажа · оценок заполнено {rated} из {catalog.scores.length}</p>
        </div>
      </div>
      <label className="field final-brief">
        <span>{catalog.brief_label}</span>
        <select value={data.preflight_brief_with_fa ?? ""}
          onChange={e => change("preflight_brief_with_fa", e.target.value || null)}>
          <option value="">Не указано</option>
          {catalog.brief_choices.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
        </select>
      </label>
      <table className="final-crew-table">
        <thead><tr><th scope="col">Критерий</th><th scope="col">Оценка</th></tr></thead>
        <tbody>{catalog.scores.map(({ field, label }) => (
          <tr key={field} className={field === "total_general_mark" ? "final-total-row" : ""}>
            <th scope="row"><label htmlFor={`final-crew-${field}`}>{label}</label></th>
            <td><select id={`final-crew-${field}`} value={data[field] ?? ""}
              onChange={e => change(field, e.target.value === "" ? null : Number(e.target.value))}>
              <option value="">—</option>
              {catalog.score_choices.map(([code, text]) => <option key={code} value={code}>{text}</option>)}
            </select></td>
          </tr>
        ))}</tbody>
      </table>
      <label className="field final-general-notes">
        <span>Общее впечатление о работе экипажа</span>
        <textarea rows={6} value={data.general_notes}
          onChange={e => change("general_notes", e.target.value)}
          placeholder="Опишите общее впечатление и значимые наблюдения за работой экипажа" />
      </label>
      <p className="muted">Общую оценку выставляет аудитор. Оценки можно уточнить позже; пустые поля допустимы.</p>
    </section>
  );
}
