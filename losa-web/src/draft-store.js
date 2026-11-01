import { prepareStageAssessments } from "./stage-assessment-data.js";
import { prepareApproach } from "./approach-data.js";

export function draftKey(userId, assignmentId) {
  return `losa-demography-v1:${userId}:${assignmentId}`;
}

export function loadDraft(storage, userId, assignmentId) {
  const raw = storage.getItem(draftKey(userId, assignmentId));
  if (!raw) return null;
  const data = JSON.parse(raw);
  if (
    data.schema !== 1 ||
    data.assignment_id !== assignmentId ||
    !data.form ||
    !data.meta ||
    !Number.isInteger(data.revision)
  ) {
    throw new Error(
      "Локальный черновик имеет неизвестный формат. Он не был удалён.",
    );
  }
  return data;
}

export function storeDraft(storage, userId, assignmentId, draft) {
  const value = {
    ...draft,
    schema: 1,
    assignment_id: assignmentId,
    localSavedAt: new Date().toISOString(),
  };
  storage.setItem(draftKey(userId, assignmentId), JSON.stringify(value));
  return value;
}

export function prepareDemography(draft) {
  const form = { ...draft.form };
  for (const key of [
    "captain_experience",
    "captain_type_experience",
    "first_officer_experience",
    "first_officer_type_experience",
  ]) {
    const raw = form[key];
    const value =
      raw === "" || raw === null || raw === undefined ? null : Number(raw);
    if (
      value !== null &&
      (!Number.isInteger(value) || value < 0 || value > 2147483647)
    )
      throw new Error(
        "Стаж указывается целым неотрицательным числом полных лет.",
      );
    form[key] = value;
  }
  for (const [total, onType] of [
    ["captain_experience", "captain_type_experience"],
    ["first_officer_experience", "first_officer_type_experience"],
  ]) {
    if (
      form[total] !== null &&
      form[onType] !== null &&
      form[onType] > form[total]
    )
      throw new Error("Стаж на типе не может превышать общий стаж.");
  }
  form.delay =
    !form.is_delay || form.delay === "" || form.delay === null
      ? null
      : Number(form.delay);
  if (
    form.delay !== null &&
    (!Number.isInteger(form.delay) ||
      form.delay <= 0 ||
      form.delay > 2147483647)
  )
    throw new Error("Задержку укажите целым числом минут больше нуля.");
  if (form.approach) form.approach = prepareApproach(form.approach);
  if (draft.assessment_migration_errors?.length)
    throw new Error("Не удалось сопоставить критерии старого черновика: " + draft.assessment_migration_errors.join(", ") + ". Локальные данные сохранены.");
  if (form.stage_assessments) {
    form.stage_assessments = prepareStageAssessments(form.stage_assessments);
    delete form.preflight;
    delete form.cruise;
  }
  return { ...form, revision: draft.revision };
}
