import { Activity, Link2, ShieldAlert, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusMessage } from "@/components/ui/status-message";
import { useAdminDashboardQuery } from "@/features/admin/api";
import { useSession } from "@/features/session/session-provider";
import { formatDate } from "@/lib/utils";
import { AdminPageHeader, AdminQuickLink, AdminStatCard } from "@/pages/admin-shared";

export function AdminDashboardPage() {
  const { t } = useTranslation();
  const { user } = useSession();
  const dashboard = useAdminDashboardQuery();
  const data = dashboard.data;
  return <div className="space-y-4">
    <AdminPageHeader title={t("admin.dashboardTitle")} subtitle={t("admin.dashboardSubtitle")} actions={<>{user?.role === "admin" ? <AdminQuickLink to="/admin/users" label={t("admin.openUsers")} /> : null}<AdminQuickLink to="/admin/links" label={t("admin.openLinks")} />{user?.role === "admin" ? <AdminQuickLink to="/admin/settings" label={t("admin.openSettings")} /> : null}</>} />
    {dashboard.isLoading ? <StatusMessage type="loading" message={t("admin.dashboardLoading")} /> : null}
    {dashboard.error ? <StatusMessage type="error" message={dashboard.error.message} /> : null}
    {data ? <>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <AdminStatCard label={t("admin.usersStat")} value={String(data.users_total)} />
        <AdminStatCard label={t("admin.linksStat")} value={String(data.links_total)} />
        <AdminStatCard label={t("admin.activeLinksStat")} value={String(data.links_active)} hint={t("admin.disabledLinks", { count: data.links_disabled })} />
        <AdminStatCard label={t("admin.reportsStat")} value={String(data.reports_total)} hint={t("admin.openReports", { count: data.reports_open })} />
      </div>
      <Card className="space-y-4"><div className="flex items-center gap-2"><Activity className="h-4 w-4 text-accent" /><h2 className="m-0 text-base font-semibold">{t("admin.recentActions")}</h2></div>{data.recent_actions.length ? <div className="space-y-3">{data.recent_actions.map((event) => <div key={event.id} className="flex flex-col gap-1 rounded-panel border border-border bg-muted/40 p-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="m-0 font-medium">{event.action}</p><p className="m-0 text-sm text-subtle">{event.object_type} #{event.object_id}</p></div><span className="text-sm text-subtle">{formatDate(event.created_at)}</span></div>)}</div> : <EmptyState title={t("admin.actionsEmptyTitle")} description={t("admin.actionsEmptyDescription")} />}</Card>
      <Card className="grid gap-3 sm:grid-cols-3"><div className="flex items-center gap-2 text-sm text-subtle"><Users className="h-4 w-4 text-accent" />{t("admin.dashboardUsersHint")}</div><div className="flex items-center gap-2 text-sm text-subtle"><Link2 className="h-4 w-4 text-accent" />{t("admin.dashboardLinksHint")}</div><div className="flex items-center gap-2 text-sm text-subtle"><ShieldAlert className="h-4 w-4 text-accent" />{t("admin.dashboardSettingsHint")}</div></Card>
    </> : null}
  </div>;
}
