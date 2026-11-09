import { config } from "./config";
import { dateKey, validateAssignment } from "./domain";

const STORE = "losa-web-demo-v1";
const SESSION = "losa-web-demo-session-v1";
const accounts = [
  {
    id: 1,
    username: "coordinator",
    name: "Анна Смирнова",
    roles: ["coordinator", "auditor"],
    auditor_id: 1,
  },
  {
    id: 2,
    username: "auditor",
    name: "Михаил Орлов",
    roles: ["auditor"],
    auditor_id: 2,
  },
];
const catalog = {
  flights: [
    {
      id: 1,
      number: "NS 101",
      departure: "DME",
      arrival: "KJA",
      time: "08:40",
      aircraft: "B737-800",
    },
    {
      id: 2,
      number: "NS 204",
      departure: "KJA",
      arrival: "NSK",
      time: "14:20",
      aircraft: "B737-800",
    },
    {
      id: 3,
      number: "NS 318",
      departure: "NSK",
      arrival: "DME",
      time: "18:10",
      aircraft: "B737-800",
    },
  ],
  pilots: [
    { id: 1, label: "Пилот 104 · CAPT" },
    { id: 2, label: "Пилот 208 · FO" },
    { id: 3, label: "Пилот 312 · CAPT" },
    { id: 4, label: "Пилот 416 · FO" },
  ],
  auditors: [
    { id: 1, name: "Анна Смирнова" },
    { id: 2, name: "Михаил Орлов" },
  ],
};
function storageError() {
  return new Error(
    "Браузер не разрешает локальное сохранение. Разрешите хранение данных для этого сайта.",
  );
}
function demoSession() {
  try {
    return (
      accounts.find(
        (a) => a.id === JSON.parse(sessionStorage.getItem(SESSION)),
      ) || null
    );
  } catch {
    return null;
  }
}
function demoRead() {
  try {
    const raw = localStorage.getItem(STORE);
    if (raw) {
      const value = JSON.parse(raw);
      if (!Array.isArray(value)) throw new Error();
      return value;
    }
    const today = dateKey(new Date(), config.timeZone);
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const seed = [
      {
        id: "demo-1",
        date: today,
        flight: 1,
        captain: 1,
        first_officer: 2,
        auditor: 1,
        status: "scheduled",
      },
      {
        id: "demo-2",
        date: today,
        flight: 2,
        captain: 3,
        first_officer: 4,
        auditor: 2,
        status: "scheduled",
      },
      {
        id: "demo-3",
        date: dateKey(tomorrow, config.timeZone),
        flight: 3,
        captain: 1,
        first_officer: 4,
        auditor: 2,
        status: "scheduled",
      },
    ];
    localStorage.setItem(STORE, JSON.stringify(seed));
    return seed;
  } catch {
    throw storageError();
  }
}
async function request(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const csrf = document.cookie
      .split("; ")
      .find((v) => v.startsWith("csrftoken="))
      ?.slice(10);
    const response = await fetch(`${config.apiBase}${path}`, {
      ...options,
      credentials: "include",
      signal: controller.signal,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(csrf ? { "X-CSRFToken": decodeURIComponent(csrf) } : {}),
        ...options.headers,
      },
    });
    const result = await response.json().catch(() => null);
    if (!response.ok) {
      const collectErrors = (value, path = "") => {
        if (Array.isArray(value)) return value.flatMap((entry, index) =>
          collectErrors(entry, typeof entry === "object" ? `${path}[${index}]` : path));
        if (value && typeof value === "object") return Object.entries(value).flatMap(
          ([key, entry]) => collectErrors(entry, path ? `${path}.${key}` : key));
        return value == null ? [] : [`${path ? path + ": " : ""}${String(value)}`];
      };
      const details = result?.errors ? collectErrors(result.errors).join(" ") : "";
      const error = new Error(
        [result?.detail || `Ошибка сервера (${response.status}).`, details]
          .filter(Boolean)
          .join(" "),
      );
      error.status = response.status;
      throw error;
    }
    return result;
  } catch (error) {
    if (error.name === "AbortError")
      throw new Error("Сервер не ответил. Повторите попытку.");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  async downloadCycleReport(cycleId, reportId, kind) {
    const response = await fetch(`${config.apiBase}/round-table/${cycleId}/reports/${reportId}/${kind}/`, {credentials: "include"});
    if (!response.ok) throw new Error("Не удалось скачать PDF. Проверьте доступ и повторите попытку.");
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url; link.download = `losa-${cycleId}-${reportId}-${kind}.pdf`;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
  async roundTable(path = "", method = "GET", data) {
    if (config.demo) throw new Error("Круглый стол использует Django. Установите VITE_DEMO_MODE=false.");
    if (method !== "GET") await request("/auth/csrf/");
    return request(`/round-table/${path}`, { method, ...(data ? { body: JSON.stringify(data) } : {}) });
  },
  async analytics(filters = {}) {
    if (config.demo) throw new Error("Аналитика использует сохранённые данные Django. Установите VITE_DEMO_MODE=false.");
    const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value !== ""));
    return request(`/analytics/?${query}`);
  },
  async previewCompletion(id, data) {
    await request("/auth/csrf/");
    return request(`/assignments/${encodeURIComponent(id)}/completion/preview/`, {
      method: "POST", body: JSON.stringify(data),
    });
  },
  async completeAssignment(id, data) {
    await request("/auth/csrf/");
    return request(`/assignments/${encodeURIComponent(id)}/complete/`, {
      method: "POST", body: JSON.stringify(data),
    });
  },
  async reopenAssignment(id, revision) {
    await request("/auth/csrf/");
    return request(`/assignments/${encodeURIComponent(id)}/reopen/`, {
      method: "POST", body: JSON.stringify({ revision }),
    });
  },
  async openDemography(id) {
    if (config.demo)
      throw new Error(
        "Этот блок подключён к Django. Установите VITE_DEMO_MODE=false.",
      );
    await request("/auth/csrf/");
    return request(`/assignments/${encodeURIComponent(id)}/demography/open/`, {
      method: "POST",
    });
  },
  async saveDemography(id, data) {
    await request("/auth/csrf/");
    return request(`/assignments/${encodeURIComponent(id)}/demography/`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },
  async me() {
    if (config.demo) return demoSession();
    try {
      return await request("/auth/me/");
    } catch (error) {
      if (error.status === 401) return null;
      throw error;
    }
  },
  async login(username, password) {
    if (!config.demo) {
      await request("/auth/csrf/");
      return request("/auth/login/", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
    }
    const user = accounts.find((a) => a.username === username.trim());
    if (!user || password !== "LosaDemo2026!")
      throw new Error("Неверный логин или пароль.");
    try {
      sessionStorage.setItem(SESSION, JSON.stringify(user.id));
    } catch {
      throw storageError();
    }
    return user;
  },
  async logout() {
    if (config.demo) {
      sessionStorage.removeItem(SESSION);
      return;
    }
    await request("/auth/csrf/");
    return request("/auth/logout/", { method: "POST" });
  },
  async planningReference(kind, method = "GET", data) {
    if (config.demo) throw new Error("Добавление справочников доступно при подключении к серверу.");
    return request(`/planning/references/${encodeURIComponent(kind)}/`, {
      method, ...(data === undefined ? {} : {body: JSON.stringify(data)}),
    });
  },
  async catalog() {
    return config.demo
      ? structuredClone(catalog)
      : request("/planning/catalog/");
  },
  async assignments() {
    if (!config.demo) return request("/assignments/");
    const user = demoSession();
    if (!user) throw new Error("Войдите в систему.");
    const all = demoRead();
    return user.roles.includes("coordinator")
      ? all
      : all.filter((a) => a.auditor === user.auditor_id);
  },
  async assignmentEntry(id) {
    if (!config.demo)
      return request(`/assignments/${encodeURIComponent(id)}/entry/`);
    const items = await this.assignments();
    return items.find((item) => String(item.id) === id) || null;
  },
  async saveAssignment(data) {
    if (!config.demo)
      return request("/assignments/", {
        method: "POST",
        body: JSON.stringify(data),
      });
    if (!demoSession()?.roles.includes("coordinator"))
      throw new Error("Нет прав координатора.");
    const error = validateAssignment(data, catalog);
    if (error) throw new Error(error);
    const all = demoRead();
    if (all.some((a) => a.date === data.date && a.flight === data.flight))
      throw new Error("На этот рейс в выбранную дату уже назначена проверка.");
    const item = { ...data, id: crypto.randomUUID(), status: "scheduled" };
    try {
      localStorage.setItem(STORE, JSON.stringify([...all, item]));
    } catch {
      throw storageError();
    }
    return item;
  },
};
