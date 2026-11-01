export default function PreflightAssessment({ value, catalog, onChange }) {
  if (!catalog) return (
    <section className="demographic-card">
      <p>Для загрузки нового блока подключитесь к серверу и обновите страницу. Черновик сохранён.</p>
    </section>
  );
  const data = value || {
    facts: "",
    scores: Object.fromEntries(catalog.sections.flatMap(s => s.criteria.map(c => [c.code, null]))),
  };
  const rated = Object.values(data.scores).filter(v => v !== null && v !== "").length;
  return (
    <section className="demographic-card preflight-card" data-observation-phase="preflight" aria-labelledby="preflight-title">
      <div className="demographic-section-title">
        <span>04</span>
        <div>
          <h2 id="preflight-title">{catalog.stage}</h2>
          <p>Оценка экипажа в целом · заполнено {rated} из 11</p>
        </div>
      </div>
      <label className="field">
        <span>Изложение фактов</span>
        <textarea
          rows={6}
          value={data.facts}
          onChange={e => onChange({ ...data, facts: e.target.value })}
          placeholder="Опишите наблюдения за работой экипажа на этом этапе"
        />
      </label>
      {catalog.sections.map(section => (
        <div className="assessment-section" key={section.number}>
          <h3>{section.name}</h3>
          <table className="assessment-table">
            <thead><tr><th scope="col">Критерий</th><th scope="col">Оценка</th></tr></thead>
            <tbody>
              {section.criteria.map(criterion => (
                <tr key={criterion.code}>
                  <th scope="row">
                    <label htmlFor={`preflight-${criterion.code}`}>
                      <span className="criterion-code">{criterion.code}</span> {criterion.name}
                    </label>
                  </th>
                  <td>
                    <select
                      id={`preflight-${criterion.code}`}
                      aria-label={`${criterion.code} ${criterion.name}: оценка`}
                      value={data.scores[criterion.code] ?? ""}
                      onChange={e => onChange({
                        ...data,
                        scores: { ...data.scores, [criterion.code]: e.target.value === "" ? null : Number(e.target.value) },
                      })}
                    >
                      <option value="">—</option>
                      {[1, 2, 3, 4].map(score => <option key={score} value={score}>{score}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
      <p className="muted">Можно сохранить незаполненный блок и вернуться к оценкам позже.</p>
    </section>
  );
}
