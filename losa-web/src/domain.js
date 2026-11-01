export function dateKey(now = new Date(), timeZone = "Europe/Moscow") {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const get = (name) => parts.find((part) => part.type === name).value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

export function canStart(assignment, user, today) {
  const assigned =
    user?.roles?.includes("auditor") &&
    assignment.auditor === user.auditor_id &&
    assignment.status === "scheduled";
  if (typeof assignment.can_start === "boolean")
    return Boolean(assigned && assignment.can_start);
  return Boolean(assigned && assignment.date <= today);
}

export function validateAssignment(data, catalog) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(data.date || ""))
    return "Укажите дату проверки.";
  if (!catalog.flights.some((item) => item.id === data.flight))
    return "Выберите рейс.";
  if (!catalog.pilots.some((item) => item.id === data.captain))
    return "Выберите КВС.";
  if (!catalog.pilots.some((item) => item.id === data.first_officer))
    return "Выберите второго пилота.";
  if (data.captain === data.first_officer)
    return "КВС и второй пилот должны быть разными сотрудниками.";
  if (!catalog.auditors.some((item) => item.id === data.auditor))
    return "Выберите аудитора.";
  return "";
}
