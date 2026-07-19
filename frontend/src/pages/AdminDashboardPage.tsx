import { Link2, Settings, Users } from "lucide-react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusMessage } from "@/components/ui/status-message";
import { useAdminLinksQuery, useAdminSettingsQuery, useAdminUsersQuery } from "@/features/admin/api";
import { formatDate } from "@/lib/utils";
import { AdminPageHeader, AdminQuickLink, AdminStatCard } from "@/pages/admin-shared";

export function AdminDashboardPage() {
  const { t } = useTranslation();
  const users = useAdminUsersQuery({ limit: 5, offset: 0 });
  const links = useAdminLinksQuery({ limit: 5, offset: 0 });
  const activeLinks = useAdminLinksQuery({ is_active: "true", limit: 1, offset: 0 });
  const settings = useAdminSettingsQuery();

  const isLoading = users.isLoading || links.isLoading || activeLinks.isLoading || settings.isLoading;
  const error = users.error ?? links.error ?? activeLinks.error ?? settings.error;

  const recentUsers = useMemo(() => users.data?.items ?? [], [users.data]);
  const recentLinks = useMemo(() => links.data?.items ?? [], [links.data]);

  return (
    <div className="space-y-4">
      <AdminPageHeader
        title={t("admin.dashboardTitle")}
        subtitle={t("admin.dashboardSubtitle")}
        actions={
          <>
            <AdminQuickLink to="/admin/users" label={t("admin.openUsers")} />
            <AdminQuickLink to="/admin/links" label={t("admin.openLinks")} />
            <AdminQuickLink to="/admin/settings" label={t("admin.openSettings")} />
          </>
        }
      />

      {isLoading ? <StatusMessage type="loading" message={t("admin.dashboardLoading")} /> : null}
      {error ? <StatusMessage type="error" message={error.message} /> : null}

      {!isLoading && !error ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <AdminStatCard label={t("admin.usersStat")} value={String(users.data?.total ?? 0)} />
            <AdminStatCard label={t("admin.linksStat")} value={String(links.data?.total ?? 0)} />
            <AdminStatCard label={t("admin.activeLinksStat")} value={String(activeLinks.data?.total ?? 0)} />
            <AdminStatCard
              label={t("admin.retentionStat")}
              value={t("admin.retentionDaysShort", { count: settings.data?.user_link_retention_days ?? 0 })}
              hint={
                settings.data?.updated_at
                  ? t("admin.settingsUpdatedAt", { date: formatDate(settings.data.updated_at) })
                  : undefined
              }
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card className="space-y-4">
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-accent" />
                <h2 className="m-0 text-base font-semibold">{t("admin.recentUsers")}</h2>
              </div>
              {recentUsers.length ? (
                <div className="space-y-3">
                  {recentUsers.map((user) => (
                    <div key={user.id} className="flex flex-col gap-1 rounded-panel border border-border bg-muted/40 p-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <p className="m-0 truncate font-medium">{user.display_name || user.email}</p>
                        <p className="m-0 truncate text-sm text-subtle">{user.email}</p>
                      </div>
                      <div className="text-sm text-subtle">{formatDate(user.created_at)}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title={t("admin.usersEmptyTitle")} description={t("admin.usersEmptyDescription")} />
              )}
            </Card>

            <Card className="space-y-4">
              <div className="flex items-center gap-2">
                <Link2 className="h-4 w-4 text-accent" />
                <h2 className="m-0 text-base font-semibold">{t("admin.recentLinks")}</h2>
              </div>
              {recentLinks.length ? (
                <div className="space-y-3">
                  {recentLinks.map((link) => (
                    <div key={link.shortcode} className="flex flex-col gap-1 rounded-panel border border-border bg-muted/40 p-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <p className="m-0 font-medium">{link.label || t("common.noLabel")}</p>
                        <p className="m-0 truncate text-sm text-subtle">{link.short_url}</p>
                      </div>
                      <div className="text-sm text-subtle">{formatDate(link.created_at)}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title={t("admin.linksEmptyTitle")} description={t("admin.linksEmptyDescription")} />
              )}
            </Card>
          </div>

          <Card className="grid gap-3 sm:grid-cols-3">
            <div className="flex items-center gap-2 text-sm text-subtle">
              <Users className="h-4 w-4 text-accent" />
              {t("admin.dashboardUsersHint")}
            </div>
            <div className="flex items-center gap-2 text-sm text-subtle">
              <Link2 className="h-4 w-4 text-accent" />
              {t("admin.dashboardLinksHint")}
            </div>
            <div className="flex items-center gap-2 text-sm text-subtle">
              <Settings className="h-4 w-4 text-accent" />
              {t("admin.dashboardSettingsHint")}
            </div>
          </Card>
        </>
      ) : null}
    </div>
  );
}
