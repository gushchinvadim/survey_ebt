import RoundTable from "./RoundTable";
import Analytics from "./Analytics";
import DemographyForm from "./DemographyForm";
import { useEffect, useState } from "react";
import { api } from "./api";
import { config } from "./config";
import { canStart, dateKey, validateAssignment } from "./domain";

function Icon({ name = "arrow", size = 22 }) {
  const paths = {
    arrow: (
      <>
        <path d="M5 12h14M13 6l6 6-6 6" />
      </>
    ),
    calendar: (
      <>
        <rect x="3" y="5" width="18" height="16" rx="3" />
        <path d="M7 3v4m10-4v4M3 11h18m-13 4h2m4 0h2" />
      </>
    ),
    eye: (
      <>
        <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" />
        <circle cx="12" cy="12" r="3" />
      </>
    ),
    shield: (
      <>
        <path d="m12 2 8 3v6c0 5-8 11-8 11S4 16 4 11V5l8-3Z" />
        <path d="m8 11 3 3 5-6" />
      </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
    lock: (
      <>
        <rect x="5" y="10" width="14" height="11" rx="2" />
        <path d="M8 10V7a4 4 0 0 1 8 0v3" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.arrow}
    </svg>
  );
}

const dateLabel = (date) =>
  new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  }).format(new Date(`${date}T12:00:00Z`));
const go = (route) => {
  window.location.hash = route;
};
function useRoute() {
  const [route, setRoute] = useState(
    () => window.location.hash.slice(1) || "home",
  );
  useEffect(() => {
    const update = () => setRoute(window.location.hash.slice(1) || "home");
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return route;
}
function Field({ label, children, hint }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
function Notice({ children, error = false }) {
  return (
    <div
      className={`notice ${error ? "error" : ""}`}
      role={error ? "alert" : "status"}
    >
      {children}
    </div>
  );
}

export default function App() {
  const route = useRoute();
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);
  useEffect(() => {
    let active = true;
    api
      .me()
      .then((u) => {
        if (active) setUser(u);
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setReady(true);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    document.title = `${route === "home" ? "Пространство наблюдений" : "Рабочее пространство"} · LOSA`;
  }, [route]);
  async function logout() {
    setLoggingOut(true);
    setError("");
    try {
      await api.logout();
      setUser(null);
      go("home");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoggingOut(false);
    }
  }
  const isWorkspace = user && route !== "home" && route !== "login";
  const authorized =
    user &&
    ((route === "coordinator" || route === "analytics" || route.startsWith("round-table"))
      ? user.roles.includes("coordinator")
      : user.roles.includes("auditor"));
  let content;
  if (!ready)
    content = (
      <div className="loading" role="status">
        Открываем пространство…
      </div>
    );
  else if (route === "home") content = <Landing user={user} />;
  else if (!user)
    content = (
      <Login
        onLogin={(u) => {
          setUser(u);
          go("roles");
        }}
      />
    );
  else if (route === "roles" || route === "login")
    content = <Roles user={user} />;
  else if ((route === "coordinator" || route === "auditor") && authorized)
    content = (
      <Workspace key={`${user.id}-${route}`} user={user} role={route} />
    );
  else if ((route === "round-table" || /^round-table\/\d+$/.test(route)) && authorized)
    content = <RoundTable key={route} cycleId={route.split("/")[1]} />;
  else if (route === "analytics" && authorized)
    content = <Analytics key={user.id} />;
  else if (route.startsWith("audit/") && authorized)
    content = <AuditEntry id={route.slice(6)} user={user} />;
  else
    content = (
      <section className="page narrow">
        <p className="eyebrow">Доступ к разделу</p>
        <h1>Выберите рабочую роль</h1>
        <p className="muted">Этот раздел недоступен вашей учётной записи.</p>
        <button className="primary" onClick={() => go("roles")}>
          К выбору роли
        </button>
      </section>
    );
  return (
    <div className="app-shell">
      {config.demo && (
        <div className="demo-banner">
          <span className="status-dot" />
          Демонстрационный режим{" "}
          <span className="banner-extra">
            · данные сохраняются только в этом браузере
          </span>
        </div>
      )}
      <header className="header">
        <div className="header-inner">
          <a className="brand" href="#home" aria-label="LOSA — главная">
            <img src="/logo.svg" alt="" />
            <span>
              LOSA<small>Line Operations Safety Audit</small>
            </span>
          </a>
          <nav aria-label="Основная навигация">
            {!user && (
              <a className="header-link desktop" href="#home">
                О программе
              </a>
            )}
            {user ? (
              <>
                <button className="header-link" onClick={() => go("roles")}>
                  Рабочее пространство
                </button>
                {user.roles.includes("coordinator") && <><a className="header-link" href="#analytics">Аналитика</a><a className="header-link" href="#round-table">Круглый стол</a></>}
                <span className="user-name">
                  <span className="avatar">{user.name?.[0] || "Л"}</span>
                  {user.name}
                </span>
                <button
                  className="outline small"
                  disabled={loggingOut}
                  onClick={logout}
                >
                  {loggingOut ? "Выходим…" : "Выйти"}
                </button>
              </>
            ) : (
              <button className="primary small" onClick={() => go("login")}>
                Войти <Icon size={17} />
              </button>
            )}
          </nav>
        </div>
      </header>
      {error && (
        <div className="page error-strip">
          <Notice error>{error}</Notice>
        </div>
      )}
      <main id="main-content" className={isWorkspace ? "workspace-main" : ""}>
        {content}
      </main>
      <footer className="footer">
        <div>
          <a href="#home" className="footer-brand">
            {config.brand}
            <span>Наблюдать. Понимать. Улучшать.</span>
          </a>
          <p>
            © {new Date().getFullYear()} {config.brand}. Все права защищены.
          </p>
        </div>
        <div className="footer-right">
          <div className="socials">
            {config.social.length ? (
              config.social.map(([label, url]) => (
                <a key={label} href={url} target="_blank" rel="noreferrer">
                  {label} ↗
                </a>
              ))
            ) : (
              <span className="muted">Социальные сети — скоро</span>
            )}
          </div>
          <span className="version">Версия {config.version}</span>
        </div>
      </footer>
    </div>
  );
}

function Landing({ user }) {
  return (
    <>
      <section className="hero page">
        <div className="hero-copy">
          <p className="eyebrow">
            <span className="status-dot" />
            Программа наблюдений LOSA
          </p>
          <h1>
            Безопасность
            <br />
            начинается
            <br />
            <em>с понимания.</em>
          </h1>
          <p className="hero-description">
            Наблюдаем за повседневной работой экипажа, изучаем угрозы и ошибки,
            находим возможности для улучшения.
          </p>
          <div className="hero-actions">
            <button
              className="primary"
              onClick={() => go(user ? "roles" : "login")}
            >
              {user ? "Рабочее пространство" : "Войти в программу"}{" "}
              <Icon size={18} />
            </button>
            <a
              href="#principles"
              onClick={(e) => {
                e.preventDefault();
                document
                  .getElementById("principles")
                  ?.scrollIntoView({ behavior: "smooth" });
              }}
            >
              Как это работает <span>↓</span>
            </a>
          </div>
          <div className="hero-note">
            <Icon name="shield" size={18} />
            <span>Открытое наблюдение. Уважение к экипажу.</span>
          </div>
        </div>
        <div className="hero-visual">
          <img
            className="flight-illustration"
            src="/flight-path.svg"
            alt="Иллюстрация самолёта на маршруте наблюдений"
          />
          <div className="visual-label">
            <span className="status-dot" />В центре внимания — работа команды
          </div>
          <div className="visual-caption">
            <span>Наблюдение в обычных условиях</span>
            <strong>
              Каждый полёт —<br />
              возможность узнать больше.
            </strong>
            <span className="caption-index">01 / LOSA</span>
          </div>
        </div>
      </section>
      <section className="principles page" id="principles">
        <div className="section-intro">
          <p className="eyebrow">От наблюдения к изменениям</p>
          <h2>
            Общая цель.
            <br />
            Разные роли.
          </h2>
          <p className="muted">
            Одно пространство для организации проверок и сбора наблюдений.
          </p>
        </div>
        <div className="principle">
          <span className="icon-box">
            <Icon name="calendar" />
          </span>
          <span className="step">01 / ПЛАНИРОВАНИЕ</span>
          <h3>Подготовить проверку</h3>
          <p>
            Координатор выбирает рейс, экипаж и аудитора в расписании программы.
          </p>
        </div>
        <div className="principle">
          <span className="icon-box">
            <Icon name="eye" />
          </span>
          <span className="step">02 / НАБЛЮДЕНИЕ</span>
          <h3>Увидеть целую картину</h3>
          <p>
            Аудитор открывает назначенную проверку и фиксирует наблюдения за
            работой экипажа.
          </p>
        </div>
        <div className="principle">
          <span className="icon-box">
            <Icon name="shield" />
          </span>
          <span className="step">03 / УЛУЧШЕНИЕ</span>
          <h3>Учиться на опыте</h3>
          <p>
            Собранные данные станут основой анализа по завершении серии
            проверок.
          </p>
        </div>
      </section>
    </>
  );
}

function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      onLogin(await api.login(username, password));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="login-layout page">
      <div className="login-intro">
        <p className="eyebrow">Добро пожаловать в LOSA</p>
        <h1>
          Ваше рабочее
          <br />
          <em>пространство.</em>
        </h1>
        <p className="muted">
          Расписание программы, назначенные проверки и наблюдения — в одном
          месте.
        </p>
        <div className="login-art">
          <img src="/flight-path.svg" alt="" />
        </div>
      </div>
      <div className="login-card">
        <span className="icon-box">
          <Icon name="lock" />
        </span>
        <h2>Вход в программу</h2>
        <p className="muted">Используйте свою учётную запись.</p>
        <form onSubmit={submit}>
          <Field label="Логин">
            <input
              name="username"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Введите логин"
            />
          </Field>
          <Field label="Пароль">
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Введите пароль"
            />
          </Field>
          {error && <Notice error>{error}</Notice>}
          <button className="primary full" disabled={busy}>
            {busy ? "Проверяем…" : "Войти"} <Icon size={18} />
          </button>
        </form>
        {config.demo && (
          <div className="demo-credentials">
            <strong>Доступ для знакомства</strong>
            <p>
              <code>coordinator</code> — обе роли
              <br />
              <code>auditor</code> — только аудитор
            </p>
            <p>
              Пароль: <code>LosaDemo2026!</code>
            </p>
          </div>
        )}
        <a href="#home" className="back-link">
          ← На главную
        </a>
      </div>
    </section>
  );
}

function Roles({ user }) {
  return (
    <section className="page role-page">
      <p className="eyebrow">Рабочее пространство</p>
      <h1>Здравствуйте, {user.name.split(" ")[0]}.</h1>
      <p className="muted lead">В какой роли вы хотите продолжить?</p>
      <div className="role-grid">
        {[
          [
            "coordinator",
            "calendar",
            "Координатор",
            "Планируйте проверки, назначайте экипажи и аудиторов.",
            "Войти как координатор",
          ],
          [
            "auditor",
            "eye",
            "Аудитор",
            "Просматривайте назначения и переходите к проведению проверок.",
            "Войти как аудитор",
          ],
        ].map(([role, icon, title, description, action]) => (
          <button
            key={role}
            className={`role-card ${role}`}
            disabled={!user.roles.includes(role)}
            onClick={() => go(role)}
          >
            <span className="role-card-top">
              <span className="icon-box">
                <Icon name={icon} size={28} />
              </span>
              <span className="role-label">
                {user.roles.includes(role) ? "Роль доступна" : "Нет доступа"}
              </span>
            </span>
            <h2>{title}</h2>
            <p>{description}</p>
            <span className="role-card-action">
              {action}
              <Icon />
            </span>
          </button>
        ))}
      </div>
      <p className="role-footnote">
        <Icon name="shield" size={17} />
        Доступ определяется правами вашей учётной записи.
      </p>
    </section>
  );
}

function Workspace({ user, role }) {
  const [catalog, setCatalog] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");
  const [planner, setPlanner] = useState(false);
  const [message, setMessage] = useState("");
  const [today, setToday] = useState(() =>
    dateKey(new Date(), config.timeZone),
  );
  useEffect(() => {
    const timer = setInterval(
      () => setToday(dateKey(new Date(), config.timeZone)),
      30000,
    );
    return () => clearInterval(timer);
  }, []);
  async function load() {
    setLoading(true);
    setError("");
    try {
      const [c, a] = await Promise.all([api.catalog(), api.assignments()]);
      setCatalog(c);
      setItems(a);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  const coordinator = role === "coordinator";
  const own = coordinator
    ? items
    : items.filter((a) => a.auditor === user.auditor_id);
  const visible = own
    .filter((a) => !filter || a.date === filter)
    .sort(
      (a, b) =>
        a.date.localeCompare(b.date) ||
        (
          catalog?.flights.find((f) => f.id === a.flight)?.time || ""
        ).localeCompare(
          catalog?.flights.find((f) => f.id === b.flight)?.time || "",
        ),
    );
  return (
    <section className="page workspace">
      <a className="back-link" href="#roles">
        ← Выбор роли
      </a>
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            {coordinator ? "Координатор программы" : "Аудитор LOSA"}
          </p>
          <h1>{coordinator ? "Расписание проверок" : "Мои проверки"}</h1>
          <p className="muted">
            {coordinator
              ? "Планируйте наблюдения и назначайте участников."
              : "Ваши назначения. Проведение доступно в день проверки."}
          </p>
        </div>
        {coordinator && (
          <button
            className="primary"
            disabled={!catalog || loading}
            onClick={() => {
              setPlanner(!planner);
              setMessage("");
            }}
          >
            {planner ? (
              "Закрыть форму"
            ) : (
              <>
                <Icon name="plus" size={18} />
                Назначить проверку
              </>
            )}
          </button>
        )}
      </div>
      <div className="stats-grid">
        <div>
          <span>Всего назначений</span>
          <strong>
            {loading ? "—" : own.length.toString().padStart(2, "0")}
          </strong>
        </div>
        <div>
          <span>На сегодня</span>
          <strong>
            {loading
              ? "—"
              : own
                  .filter((a) => a.date === today)
                  .length.toString()
                  .padStart(2, "0")}
            <i className="status-dot" />
          </strong>
        </div>
        <div>
          <span>Ближайшие</span>
          <strong>
            {loading
              ? "—"
              : own
                  .filter((a) => a.date > today)
                  .length.toString()
                  .padStart(2, "0")}
          </strong>
        </div>
      </div>
      {message && <Notice>{message}</Notice>}
      {error && (
        <Notice error>
          {error}{" "}
          <button className="text-button" onClick={load}>
            Повторить
          </button>
        </Notice>
      )}
      {planner && catalog && (
        <Planner
          catalog={catalog}
          today={today}
          onCancel={() => setPlanner(false)}
          onSave={async (data) => {
            const saved = await api.saveAssignment(data);
            setItems((current) => [...current, saved]);
            setMessage(
              "Проверка назначена. Она появится в расписании аудитора.",
            );
            setPlanner(false);
          }}
        />
      )}
      <div className="schedule-panel">
        <div className="schedule-toolbar">
          <div>
            <h2>{coordinator ? "План программы" : "Назначенные проверки"}</h2>
            <span className="muted">
              Сегодня {dateLabel(today)} · {config.timeZone}
            </span>
          </div>
          <label className="date-filter">
            Дата
            <input
              aria-label="Фильтр по дате"
              type="date"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </label>
          {filter && (
            <button className="text-button" onClick={() => setFilter("")}>
              Все даты
            </button>
          )}
        </div>
        {loading ? (
          <div className="empty" role="status">
            Загружаем расписание…
          </div>
        ) : !visible.length ? (
          <div className="empty">
            <Icon name="calendar" size={34} />
            <h3>Проверок пока нет</h3>
            <p>
              {filter
                ? "На выбранную дату назначений нет."
                : coordinator
                  ? "Назначьте первую проверку с помощью кнопки выше."
                  : "Новые назначения появятся здесь после планирования."}
            </p>
          </div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Дата / вылет</th>
                  <th>Рейс / маршрут</th>
                  <th>Экипаж</th>
                  <th>Аудитор</th>
                  <th>Статус</th>
                  {!coordinator && <th>Проверка</th>}
                </tr>
              </thead>
              <tbody>
                {visible.map((a) => {
                  const flight = catalog.flights.find((f) => f.id === a.flight);
                  const pilot = (id) =>
                    catalog.pilots.find((p) => p.id === id)?.label ||
                    `Пилот ${id}`;
                  const auditor = catalog.auditors.find(
                    (p) => p.id === a.auditor,
                  );
                  const enabled = canStart(a, user, today) || a.can_view === true;
                  return (
                    <tr key={a.id}>
                      <td>
                        <strong>{dateLabel(a.date)}</strong>
                        <small>{flight?.time || "—"}</small>
                      </td>
                      <td>
                        <strong>{flight?.number || "Рейс недоступен"}</strong>
                        <small>{a.audit_number}</small>
                        <small>
                          {flight?.departure} → {flight?.arrival} ·{" "}
                          {flight?.aircraft}
                        </small>
                      </td>
                      <td>
                        <span>{pilot(a.captain)}</span>
                        <small>{pilot(a.first_officer)}</small>
                      </td>
                      <td>{auditor?.name || "—"}</td>
                      <td>
                        <span
                          className={`badge ${a.date === today ? "today" : ""}`}
                        >
                          {a.status === "completed"
                            ? "Завершена"
                            : a.has_sheet
                              ? "Черновик"
                              : a.date === today
                                ? "Сегодня"
                                : a.date > today
                                  ? "Запланирована"
                                  : "Дата прошла"}
                        </span>
                      </td>
                      {!coordinator && (
                        <td>
                          <button
                            className={
                              enabled ? "primary small" : "outline small"
                            }
                            disabled={!enabled}
                            onClick={() => go(`audit/${a.id}`)}
                          >
                            {a.status === "completed"
                              ? "Просмотреть"
                              : enabled && a.has_sheet
                                ? "Продолжить проверку"
                                : "Выполнение проверки"}
                            {enabled && <Icon size={15} />}
                          </button>
                          {!enabled && (
                            <small className="action-hint">
                              {a.date > today
                                ? `Доступ ${dateLabel(a.date)}`
                                : a.date < today
                                  ? "Доступ только назначенному аудитору"
                                  : "Проверка недоступна"}
                            </small>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <p className="workspace-note">
        <Icon name="shield" size={16} />В расписании используются номера пилотов
        без ФИО.
      </p>
    </section>
  );
}

function Planner({ catalog, today, onSave, onCancel }) {
  const [data, setData] = useState({
    date: today,
    flight: "",
    captain: "",
    first_officer: "",
    auditor: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const change = (field, value) =>
    setData((current) => ({ ...current, [field]: value }));
  async function submit(e) {
    e.preventDefault();
    const payload = {
      ...data,
      flight: Number(data.flight),
      captain: Number(data.captain),
      first_officer: Number(data.first_officer),
      auditor: Number(data.auditor),
    };
    const validation = validateAssignment(payload, catalog);
    if (validation) {
      setError(validation);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await onSave(payload);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }
  return (
    <form className="planner" onSubmit={submit}>
      <div className="planner-title">
        <span className="icon-box">
          <Icon name="calendar" />
        </span>
        <div>
          <h2>Новая проверка</h2>
          <p className="muted">Выберите рейс и участников наблюдения.</p>
        </div>
      </div>
      <div className="planner-grid">
        <Field label="Дата">
          <input
            required
            type="date"
            value={data.date}
            onChange={(e) => change("date", e.target.value)}
          />
        </Field>
        <Field label="Рейс">
          <select
            required
            value={data.flight}
            onChange={(e) => change("flight", e.target.value)}
          >
            <option value="">Выберите рейс</option>
            {catalog.flights
              .filter((f) => f.is_active !== false)
              .map((f) => (
                <option key={f.id} value={f.id}>
                  {f.number} · {f.departure} → {f.arrival} · {f.time}
                </option>
              ))}
          </select>
        </Field>
        <Field label="Командир ВС">
          <select
            required
            value={data.captain}
            onChange={(e) => change("captain", e.target.value)}
          >
            <option value="">Выберите КВС</option>
            {catalog.pilots.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Второй пилот">
          <select
            required
            value={data.first_officer}
            onChange={(e) => change("first_officer", e.target.value)}
          >
            <option value="">Выберите второго пилота</option>
            {catalog.pilots.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Аудитор">
          <select
            required
            value={data.auditor}
            onChange={(e) => change("auditor", e.target.value)}
          >
            <option value="">Выберите аудитора</option>
            {catalog.auditors
              .filter((a) => a.is_active !== false)
              .map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
          </select>
        </Field>
      </div>
      {error && <Notice error>{error}</Notice>}
      <div className="form-actions">
        <button
          type="button"
          className="outline"
          disabled={busy}
          onClick={onCancel}
        >
          Отмена
        </button>
        <button className="primary" disabled={busy}>
          {busy ? "Сохраняем…" : "Сохранить назначение"}
          <Icon size={17} />
        </button>
      </div>
    </form>
  );
}

function AuditEntry({ id, user }) {
  return (
    <DemographyForm key={`${user.id}-${id}`} assignmentId={id} user={user} />
  );
}
