import { emptyApproach } from "./approach-data";

function Select({ id, label, choices, value, onChange, emptyValue = null }) {
  return (
    <select id={id} aria-label={label} value={value ?? ""}
      onChange={e => onChange(e.target.value || emptyValue)}>
      <option value="">Не указано</option>
      {choices.map(([code, text]) => <option key={code} value={code}>{text}</option>)}
    </select>
  );
}

export default function DescentApproachBlock({ value, catalog, onChange }) {
  if (!catalog) return (
    <section className="demographic-card">
      <h2>Снижение / заход на посадку / посадка и руление</h2>
      <p>Подключитесь к серверу и обновите форму, чтобы загрузить новый блок. Локальный черновик сохранён.</p>
    </section>
  );
  const data = value || emptyApproach();
  const set = (group, field, next) => onChange({
    ...data, [group]: { ...data[group], [field]: next },
  });
  const setMeasurement = (stage, field, next) => onChange({
    ...data,
    measurements: {
      ...data.measurements,
      [stage]: { ...data.measurements[stage], [field]: next },
    },
  });
  const descentFields = [
    ["ten_thousand_brief", "Был ли проведён инструктаж по выполнению манёвра снижения?"],
    ["start_of_descent", "Начало снижения относительно точки TOD, рассчитанной FMS"],
    ["descent_trajectory", "Положение относительно траектории FMS или стандартной траектории"],
    ["approach_mode", "Заход на посадку: тип управления"],
    ["flap_settings", "Выпуск закрылков: был ли процесс в основном завершён"],
  ];
  const select = (group, field, label) => (
    <Select id={`approach-${group}-${field}`} label={label}
      choices={catalog[group][field]} value={data[group][field]}
      emptyValue={field === "approach_type" ? "" : null}
      onChange={next => set(group, field, next)} />
  );
  const dot = (stage, axis, stageName) => (
    <div className="dot-control">
      <label className="dot-value">
        <span className="sr-only">{stageName}: отклонение {axis === "course" ? "по курсу" : "от глиссады"}</span>
        <input type="text" inputMode="decimal" placeholder="—" maxLength={10}
          value={data.measurements[stage][`${axis}_deviation`] ?? ""}
          onChange={e => setMeasurement(stage, `${axis}_deviation`, e.target.value)} />
        <span>dot</span>
      </label>
      <label className="more-than-label">
        <input type="checkbox" checked={data.measurements[stage][`${axis}_more_than`]}
          onChange={e => setMeasurement(stage, `${axis}_more_than`, e.target.checked)} />
        <span>Более</span>
        <span className="sr-only"> указанного значения: {stageName}, {axis === "course" ? "курс" : "глиссада"}</span>
      </label>
    </div>
  );
  const rows = [
    { key: "speed_deviation", label: "Точность выдерживания заданной воздушной скорости",
      hint: "Отклонение в узлах · ориентир −5…+15",
      cell: (stage, label) => {
        const raw = data.measurements[stage].speed_deviation;
        const display = typeof raw === "number" && raw > 0 ? `+${raw}` : raw ?? "";
        return <input type="text" inputMode="text" maxLength={12}
          aria-label={`${label}: отклонение скорости, узлы`} placeholder="+10 / −5"
          value={display}
          onChange={e => setMeasurement(stage, "speed_deviation", e.target.value)} />;
      } },
    { key: "rate_of_descent_deviation", label: "Вертикальная скорость < 1 000 фут/мин" },
    { key: "thrust_settings", label: "Выдерживание требуемого режима работы двигателей" },
    { key: "landing_config", label: "Установка посадочной конфигурации ВС",
      hint: "Выбор аудитора с учётом типа ВС и методики захода" },
    { key: "glideslope_deviation", label: "Снижение по заданной траектории — глиссада (G/S)",
      cell: (stage, label) => dot(stage, "glideslope", label) },
    { key: "course_deviation", label: "Снижение по заданной траектории — курс (LOC)",
      cell: (stage, label) => dot(stage, "course", label) },
  ];
  const landingFields = [
    ["threshold_height", "Высота пролёта порога ВПП (50 футов)"],
    ["flare_and_touch_distance", "Место касания относительно посадочных знаков"],
    ["g_load", "Перегрузка — субъективная оценка"],
  ];
  const rolloutFields = [
    ["thrust_reverser_on", "Включение реверса тяги"],
    ["thrust_reverser_off", "Выключение реверса тяги"],
    ["taxi_speed", "Скорость руления по прямой"],
    ["taxi_speed_turn", "Скорость руления на разворотах"],
    ["parking", "Заруливание на стоянку"],
  ];

  return (
    <section className="demographic-card approach-card" data-observation-phase="descent" aria-labelledby="approach-title">
      <div className="demographic-section-title">
        <span>07</span>
        <div><h2 id="approach-title">Снижение / заход на посадку / посадка и руление</h2>
          <p>Условия захода общие, параметры фиксируются на каждом из трёх этапов.</p></div>
      </div>
      <div className="demographic-grid approach-questions">
        {descentFields.map(([field, label]) => (
          <div className="field" key={field}>
            <label htmlFor={`approach-descent-${field}`}>{label}</label>
            {select("descent", field, label)}
            {field === "descent_trajectory" && (
              <label className="field deviation-reason">
                <span>Причина отклонения от расчётной траектории и действия экипажа</span>
                <textarea rows={4} value={data.descent.describe_deviation}
                  onChange={e => set("descent", "describe_deviation", e.target.value)}
                  placeholder="Если наблюдалось отклонение, опишите причину и действия экипажа" />
              </label>
            )}
          </div>
        ))}
        <div className="field">
          <label htmlFor="approach-conditions-approach_type">Тип захода</label>
          {select("conditions", "approach_type", "Тип захода")}
        </div>
        <div className="field">
          <label htmlFor="approach-conditions-visual_condition">Погодные условия</label>
          {select("conditions", "visual_condition", "Погодные условия")}
        </div>
      </div>

      <div className="approach-subsection" data-observation-phase="approach">
        <h3 id="stabilized-title">Параметры стабилизированного захода на посадку</h3>
        <p className="table-scroll-hint" id="approach-scroll-hint">На узком экране таблицу можно прокручивать по горизонтали.</p>
        <div className="approach-table-scroll" role="region" aria-labelledby="stabilized-title"
          aria-describedby="approach-scroll-hint" tabIndex={0}>
          <table className="approach-measurements">
            <thead><tr>
              <th scope="col">Наблюдаемый параметр</th>
              {catalog.stages.map(([code, label]) => <th scope="col" key={code}>{label}</th>)}
            </tr></thead>
            <tbody>{rows.map(row => (
              <tr key={row.key}>
                <th scope="row">{row.label}{row.hint && <small>{row.hint}</small>}</th>
                {catalog.stages.map(([stage, label]) => (
                  <td key={stage}>{row.cell ? row.cell(stage, label) : (
                    <Select label={`${label}: ${row.label}`}
                      choices={catalog.measurements[row.key]} value={data.measurements[stage][row.key]}
                      onChange={next => setMeasurement(stage, row.key, next)} />
                  )}</td>
                ))}
              </tr>
            ))}</tbody>
          </table>
        </div>
        <p className="approach-help">Пусто — нет данных. Для отклонений в dot укажите величину; отметка «Более» относится к введённому значению. Выход за ориентир скорости сохраняется как наблюдение.</p>
      </div>

      <div className="approach-subsection" data-observation-phase="landing">
        <h3 id="landing-title">Посадка</h3>
        <div className="approach-table-scroll" role="region" aria-labelledby="landing-title" tabIndex={0}>
          <table className="landing-table">
            <thead><tr><th scope="col">Этап</th>{landingFields.map(([field, label]) =>
              <th scope="col" key={field}>{label}</th>)}</tr></thead>
            <tbody><tr><th scope="row">Посадка</th>{landingFields.map(([field, label]) =>
              <td key={field}>{select("landing", field, label)}</td>)}</tr></tbody>
          </table>
        </div>
      </div>

      <div className="approach-subsection" data-observation-phase="landing_roll">
        <h3 id="rollout-title">Пробег, руление и стоянка</h3>
        <table className="rollout-table" aria-labelledby="rollout-title">
          <thead><tr><th scope="col">Наблюдаемый параметр</th><th scope="col">Наблюдение</th></tr></thead>
          <tbody>{rolloutFields.map(([field, label]) => (
            <tr key={field}><th scope="row"><label htmlFor={`approach-rollout-${field}`}>{label}</label></th>
              <td>{select("rollout", field, label)}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}
