export function emptyJournal() {
  return { mistakes: [], threats: [], deleted_mistakes: [], deleted_threats: [] };
}

export function observationId(cryptoApi = globalThis.crypto) {
  if (cryptoApi?.randomUUID) return cryptoApi.randomUUID();
  // getRandomValues also works on HTTP inside a local network.
  if (!cryptoApi?.getRandomValues) throw new Error("Браузер не поддерживает безопасное создание идентификатора.");
  const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = [...bytes].map(v => v.toString(16).padStart(2, "0")).join("");
  return [hex.slice(0,8),hex.slice(8,12),hex.slice(12,16),hex.slice(16,20),hex.slice(20)].join("-");
}

export function newObservation(kind, phaseId = null, cryptoApi) {
  const common = {
    id: observationId(cryptoApi), flight_phase: phaseId,
    observed_at: new Date().toISOString(), comment: "",
  };
  return kind === "mistake" ? {
    ...common, mistake: null, who_made: null, who_noticed: null,
    reaction: null, error_result: null, is_action_ok: null,
    threat_id: null, safety_condition_ids: [],
  } : { ...common, threat: null, was_control_effective: null, correct_actions: null };
}

export function observationProblem(kind, event, journal, catalog) {
  if (!catalog?.phases.some(p => p.id === event.flight_phase)) return "Выберите точную фазу полёта.";
  const key = kind === "mistake" ? "mistake" : "threat";
  const source = kind === "mistake" ? catalog.mistakes : catalog.threats;
  if (!source.some(row => row.id === event[key])) return kind === "mistake" ? "Выберите конкретную ошибку." : "Выберите фактор угрозы.";
  if (event.observed_at && !Number.isFinite(new Date(event.observed_at).getTime()))
    return "Проверьте время наблюдения.";
  if (kind === "mistake" && event.threat_id && !journal.threats.some(t => t.id === event.threat_id))
    return "Связанная угроза больше не доступна. Выберите другую или снимите связь.";
  return "";
}

export function needsDetails(kind, event) {
  const fields = kind === "mistake"
    ? ["who_made", "who_noticed", "reaction", "error_result", "is_action_ok"]
    : ["was_control_effective", "correct_actions"];
  if (kind === "mistake" && event.error_result === "2" && !event.safety_condition_ids?.length) return true;
  return fields.some(field => event[field] === null || event[field] === undefined || event[field] === "");
}

export function putObservation(journal, kind, event) {
  const key = kind === "mistake" ? "mistakes" : "threats";
  const exists = journal[key].some(row => row.id === event.id);
  return { ...journal, [key]: exists
    ? journal[key].map(row => row.id === event.id ? structuredClone(event) : row)
    : [...journal[key], structuredClone(event)] };
}

export function removeObservation(journal, kind, id) {
  const key = kind === "mistake" ? "mistakes" : "threats";
  if (kind === "threat" && journal.mistakes.some(row => row.threat_id === id))
    throw new Error("Угроза связана с ошибкой. Сначала снимите или измените связь в форме ошибки.");
  const item = journal[key].find(row => row.id === id);
  if (item?.safety_condition_ids?.length)
    throw new Error("Ошибка связана с изменениями состояния безопасности. Сначала снимите эти связи.");
  return {
    ...journal, [key]: journal[key].filter(row => row.id !== id),
    [`deleted_${key}`]: [...new Set([...journal[`deleted_${key}`], id])],
  };
}

export function searchMistakes(catalog, query, typeId = "", sectionId = "") {
  const q = query.trim().toLocaleLowerCase("ru");
  return catalog.mistakes.filter(row =>
    (!typeId || row.type_id === Number(typeId)) &&
    (!sectionId || (sectionId === "none" ? row.section_id === null : row.section_id === Number(sectionId))) &&
    (!q || `${row.code} ${row.name}`.toLocaleLowerCase("ru").includes(q)));
}

export function searchThreats(catalog, query, type = "") {
  const q = query.trim().toLocaleLowerCase("ru");
  return catalog.threats.filter(row => (!type || row.type === type) &&
    (!q || `${row.code} ${row.describe}`.toLocaleLowerCase("ru").includes(q)));
}

export function toUTCTime(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (!Number.isFinite(date.getTime())) return "";
  const pad = n => String(n).padStart(2, "0");
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth()+1)}-${pad(date.getUTCDate())}T${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`;
}
