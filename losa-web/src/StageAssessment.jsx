export default function StageAssessment({ code, definition, value, onChange, number, phase, showTitle = true }) {
  if (!definition) return (
    <section className="demographic-card stage-assessment">
      <p>Подключитесь к серверу и обновите форму, чтобы получить критерии этапа.</p>
    </section>
  );
  const data = value || { facts: "", scores: {} };
  const criteria = definition.sections.flatMap(section => section.criteria);
  const rated = criteria.filter(row => data.scores[String(row.id)] !== null && data.scores[String(row.id)] !== undefined).length;
  return (
    <section className="demographic-card stage-assessment" data-observation-phase={phase}
      aria-labelledby={`stage-title-${code}`}>
      <div className="demographic-section-title">
        {number && <span>{number}</span>}
        <div>
          <h2 id={`stage-title-${code}`}>{showTitle ? definition.name : "Качественные характеристики работы экипажа"}</h2>
          <p>Оценка экипажа в целом · заполнено {rated} из {criteria.length}</p>
        </div>
      </div>
      <label className="field">
        <span>Изложение фактов</span>
        <textarea rows={6} value={data.facts}
          onChange={e => onChange({ ...data, facts: e.target.value })}
          placeholder="Опишите наблюдения за работой экипажа на этом этапе" />
      </label>
      {!definition.configured && <p className="notice">Для этого этапа пока не выбран шаблон в админке. Изложение фактов можно сохранить.</p>}
      {definition.configured && !criteria.length && <p className="muted">Критерии появятся после заполнения разделов шаблона в админке и обновления формы.</p>}
      {definition.sections.map(section => (
        <div className="assessment-section" key={section.id}>
          <h3>{section.name}</h3>
          {section.historical && <p className="assessment-history-note">Ранее использованный шаблон · {section.template_version}. Существующие оценки сохранены.</p>}
          <table className="assessment-table">
            <thead><tr><th scope="col">Критерий</th><th scope="col">Оценка</th></tr></thead>
            <tbody>{section.criteria.map(criterion => (
              <tr key={criterion.id}>
                <th scope="row"><label htmlFor={`stage-${code}-criterion-${criterion.id}`}>
                  <span className="criterion-code">{criterion.code}</span> {criterion.name}
                </label></th>
                <td><select id={`stage-${code}-criterion-${criterion.id}`}
                  value={data.scores[String(criterion.id)] ?? ""}
                  onChange={e => onChange({ ...data, scores: {
                    ...data.scores, [String(criterion.id)]: e.target.value === "" ? null : Number(e.target.value),
                  } })}>
                  <option value="">—</option>
                  {[1, 2, 3, 4].map(score => <option key={score} value={score}>{score}</option>)}
                </select></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      ))}
      <p className="muted">Пустые оценки допустимы. Оценки можно уточнить позже.</p>
    </section>
  );
}
