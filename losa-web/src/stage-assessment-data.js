export const STAGE_CODES = ["preflight", "takeoff_climb", "cruise", "descent_landing"];

export function mergeStageAssessmentDraft(localForm, serverForm, definitions) {
  const result = structuredClone(serverForm.stage_assessments || {});
  const unmapped = [];
  for (const code of STAGE_CODES) {
    result[code] ||= { facts: "", scores: {} };
    const local = localForm.stage_assessments?.[code];
    if (local) {
      const allowed = new Set((definitions?.[code]?.sections || []).flatMap(section => section.criteria.map(row => String(row.id))));
      const scores = { ...local.scores };
      for (const [id, score] of Object.entries(scores)) {
        if (allowed.has(id)) continue;
        if (score === null || score === undefined || score === "") delete scores[id];
        else unmapped.push(`${code}: #${id}`);
      }
      result[code] = {
        facts: local.facts,
        scores: { ...result[code].scores, ...scores },
      };
      continue;
    }
    // Upgrade cached drafts made before the stage-specific API was introduced.
    const legacy = code === "preflight" ? localForm.preflight : code === "cruise" ? localForm.cruise : null;
    if (!legacy) continue;
    result[code].facts = legacy.facts ?? result[code].facts;
    if (code === "preflight") {
      const criteria = definitions?.[code]?.sections.flatMap(section => section.criteria) || [];
      for (const [oldCode, value] of Object.entries(legacy.scores || {})) {
        const matches = criteria.filter(row => row.code === oldCode);
        if (matches.length === 1) result[code].scores[String(matches[0].id)] = value;
        else if (value !== null && value !== undefined && value !== "") unmapped.push(oldCode);
      }
    }
  }
  return { values: result, unmapped };
}

export function prepareStageAssessments(raw) {
  const result = structuredClone(raw);
  for (const [code, block] of Object.entries(result)) {
    if (!STAGE_CODES.includes(code)) throw new Error("Неизвестный этап оценки.");
    for (const [id, value] of Object.entries(block.scores)) {
      if (!/^[1-9]\d*$/.test(id)) throw new Error("Некорректный идентификатор критерия.");
      if (value !== null && (!Number.isInteger(value) || value < 1 || value > 4))
        throw new Error("Оценки критериев должны быть от 1 до 4 или пустыми.");
    }
  }
  return result;
}
