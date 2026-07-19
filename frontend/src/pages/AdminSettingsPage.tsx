import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusMessage } from "@/components/ui/status-message";
import { useAdminSettingsQuery, useUpdateAdminSettingsMutation } from "@/features/admin/api";
import { formatDate } from "@/lib/utils";
import { AdminPageHeader } from "@/pages/admin-shared";

export function AdminSettingsPage() {
  const { t } = useTranslation();
  const schema = z.object({
    user_link_retention_days: z.coerce.number<number>().int().min(1).max(3650),
  });
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { user_link_retention_days: 30 },
  });
  const settings = useAdminSettingsQuery();
  const updateSettings = useUpdateAdminSettingsMutation();

  useEffect(() => {
    if (settings.data) {
      form.reset({ user_link_retention_days: settings.data.user_link_retention_days });
    }
  }, [form, settings.data]);

  return (
    <div className="space-y-4">
      <AdminPageHeader title={t("admin.settingsTitle")} subtitle={t("admin.settingsSubtitle")} />

      <Card className="space-y-4">
        {settings.isLoading ? <StatusMessage type="loading" message={t("admin.settingsLoading")} /> : null}
        {settings.error ? <StatusMessage type="error" message={settings.error.message} /> : null}

        {!settings.isLoading && !settings.error ? (
          <form
            className="grid gap-4 md:max-w-xl"
            onSubmit={form.handleSubmit(async (values) => {
              await updateSettings.mutateAsync(values);
            })}
          >
            <label className="grid gap-1 text-sm">
              <span className="text-subtle">{t("admin.retentionDays")}</span>
              <Input
                type="number"
                min={1}
                max={3650}
                step={1}
                {...form.register("user_link_retention_days")}
              />
              <span className="text-xs text-subtle">{t("admin.retentionHelp")}</span>
            </label>
            {form.formState.errors.user_link_retention_days ? (
              <StatusMessage type="error" message={t("admin.retentionValidation")} />
            ) : null}
            {updateSettings.error ? <StatusMessage type="error" message={updateSettings.error.message} /> : null}
            {updateSettings.isSuccess ? <StatusMessage type="success" message={t("admin.settingsSaved")} /> : null}
            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={updateSettings.isPending}>
                {t("admin.saveSettings")}
              </Button>
              {settings.data?.updated_at ? (
                <span className="text-sm text-subtle">
                  {t("admin.settingsUpdatedAt", { date: formatDate(settings.data.updated_at) })}
                </span>
              ) : null}
            </div>
          </form>
        ) : null}
      </Card>
    </div>
  );
}
