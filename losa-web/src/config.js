export const config = {
  demo: import.meta.env.VITE_DEMO_MODE !== "false",
  apiBase: (import.meta.env.VITE_API_BASE || "/api").replace(/\/$/, ""),
  timeZone: "UTC",
  brand: import.meta.env.VITE_BRAND_NAME || "LOSA",
  version: "0.3.0",
  social: [
    ["Telegram", import.meta.env.VITE_TELEGRAM_URL],
    ["ВКонтакте", import.meta.env.VITE_VK_URL],
    ["Сайт", import.meta.env.VITE_WEBSITE_URL],
  ].filter(([, url]) => /^https:\/\//.test(url || "")),
};
