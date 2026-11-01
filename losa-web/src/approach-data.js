export const APPROACH_STAGES = ["glideslope_entry", "1000_ft", "500_ft"];

export function emptyApproach() {
  const measurements = Object.fromEntries(APPROACH_STAGES.map(stage => [stage, {
    speed_deviation: null,
    rate_of_descent_deviation: null,
    thrust_settings: null,
    landing_config: null,
    course_deviation: null,
    course_more_than: false,
    glideslope_deviation: null,
    glideslope_more_than: false,
  }]));
  return {
    descent: {
      ten_thousand_brief: null, start_of_descent: null, descent_trajectory: null,
      describe_deviation: "", approach_mode: null, flap_settings: null,
    },
    conditions: { approach_type: "", visual_condition: null },
    measurements,
    landing: { threshold_height: null, flare_and_touch_distance: null, g_load: null },
    rollout: {
      thrust_reverser_on: null, thrust_reverser_off: null,
      taxi_speed: null, taxi_speed_turn: null, parking: null,
    },
  };
}

function numberOrNull(raw, label, integer) {
  if (raw === "" || raw === null || raw === undefined) return null;
  const text = String(raw).trim().replace(",", ".");
  if (!(integer ? /^[+-]?\d+$/ : /^\+?(?:\d+(?:\.\d{0,2})?|\.\d{1,2})$/).test(text))
    throw new Error(`${label}: ${integer ? "укажите целое число со знаком или без него" : "укажите неотрицательное число, не более двух знаков после запятой"}.`);
  const value = Number(text);
  if (!Number.isFinite(value) || (integer
      ? value < -2147483648 || value > 2147483647
      : value < 0 || value > 999.99))
    throw new Error(`${label}: значение вне допустимого диапазона поля.`);
  // Decimal strings preserve the same precision as the database.
  return integer ? value : value.toFixed(2);
}

export function prepareApproach(raw) {
  const value = structuredClone(raw);
  for (const stage of APPROACH_STAGES) {
    const row = value.measurements[stage];
    row.speed_deviation = numberOrNull(row.speed_deviation, "Отклонение скорости", true);
    for (const axis of ["course", "glideslope"]) {
      row[`${axis}_deviation`] = numberOrNull(
        row[`${axis}_deviation`],
        axis === "course" ? "Отклонение по курсу" : "Отклонение от глиссады",
        false,
      );
      if (row[`${axis}_more_than`] && row[`${axis}_deviation`] === null)
        throw new Error("Для отметки «более» укажите отклонение в dot.");
    }
  }
  return value;
}
