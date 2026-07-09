import type { SettingsSummary } from "@/lib/api/types";

export async function getDemoSettingsSummary(): Promise<SettingsSummary> {
  return {
    app_env: "demo",
    database_url_redacted: "browser sessionStorage demo",
    export_dir: "browser download",
    sending_enabled: false,
    email_sending_enabled: false,
    whatsapp_sending_enabled: false,
    daily_email_limit: 0,
    daily_whatsapp_limit: 0,
    duplicate_send_window_hours: 0,
    providers: {
      google_places_configured: false,
      cnpj_company_search_configured: false,
      smtp_configured: false,
      resend_configured: false,
      whatsapp_cloud_configured: false,
    },
  };
}
