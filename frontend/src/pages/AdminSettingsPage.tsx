import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { StatusMessage } from "@/components/ui/status-message";
import { useAdminRetentionSettingsQuery, useUpdateAdminRetentionSettingsMutation } from "@/features/admin/api";
import { formatDate } from "@/lib/utils";
import { AdminPageHeader } from "@/pages/admin-shared";

const schema = z.object({ audit_log_days: z.coerce.number<number>().int().min(1).max(3650), report_days: z.coerce.number<number>().int().min(1).max(3650), admin_access_attempt_days: z.coerce.number<number>().int().min(1).max(3650), password_confirmation: z.string().min(1) });
type FormValues = z.infer<typeof schema>;

export function AdminSettingsPage() {
  const { t } = useTranslation();
  const settings = useAdminRetentionSettingsQuery(); const updateSettings = useUpdateAdminRetentionSettingsMutation();
  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { audit_log_days: 90, report_days: 365, admin_access_attempt_days: 90, password_confirmation: "" } });
  useEffect(() => { if (settings.data) form.reset({ ...settings.data, password_confirmation: "" }); }, [form, settings.data]);
  return <div className="space-y-4"><AdminPageHeader title={t("admin.settingsTitle")} subtitle={t("admin.settingsSubtitle")} /><Card className="space-y-4">{settings.isLoading ? <StatusMessage type="loading" message={t("admin.settingsLoading")} /> : null}{settings.error ? <StatusMessage type="error" message={settings.error.message} /> : null}{!settings.isLoading && !settings.error ? <form className="grid gap-4 md:max-w-xl" onSubmit={form.handleSubmit(async (values) => { await updateSettings.mutateAsync(values); form.setValue("password_confirmation", ""); })}><label className="grid gap-1 text-sm"><span className="text-subtle">{t("admin.auditLogDays")}</span><Input type="number" min={1} max={3650} step={1} {...form.register("audit_log_days")} /><span className="text-xs text-subtle">{t("admin.auditLogDaysHelp")}</span></label><label className="grid gap-1 text-sm"><span className="text-subtle">{t("admin.reportDays")}</span><Input type="number" min={1} max={3650} step={1} {...form.register("report_days")} /><span className="text-xs text-subtle">{t("admin.reportDaysHelp")}</span></label><label className="grid gap-1 text-sm"><span className="text-subtle">{t("admin.accessAttemptDays")}</span><Input type="number" min={1} max={3650} step={1} {...form.register("admin_access_attempt_days")} /><span className="text-xs text-subtle">{t("admin.accessAttemptDaysHelp")}</span></label><label className="grid gap-1 text-sm"><span className="text-subtle">{t("admin.passwordConfirmation")}</span><PasswordInput autoComplete="current-password" {...form.register("password_confirmation")} /></label>{Object.keys(form.formState.errors).length ? <StatusMessage type="error" message={t("admin.retentionValidation")} /> : null}{updateSettings.error ? <StatusMessage type="error" message={updateSettings.error.message} /> : null}{updateSettings.isSuccess ? <StatusMessage type="success" message={t("admin.settingsSaved")} /> : null}<div className="flex flex-wrap items-center gap-3"><Button type="submit" disabled={updateSettings.isPending}>{t("admin.saveSettings")}</Button>{settings.data?.updated_at ? <span className="text-sm text-subtle">{t("admin.settingsUpdatedAt", { date: formatDate(settings.data.updated_at) })}</span> : null}</div></form> : null}</Card></div>;
}
