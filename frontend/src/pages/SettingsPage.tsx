import * as Switch from "@radix-ui/react-switch";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusMessage } from "@/components/ui/status-message";
import { api } from "@/api/client";
import { useSession } from "@/features/session/session-provider";
import { useTheme } from "@/features/theme/theme-provider";
import { useChangePasswordMutation, useDeleteAccountMutation, useExportDataMutation, useToggleTwoFactorMutation } from "@/features/settings/api";

const passwordSchema = z.object({
  current_password: z.string().min(8),
  new_password: z.string().min(8),
});

export function SettingsPage() {
  const { user, preferences } = useSession();
  const { language, setLanguage, setTheme, theme } = useTheme();
  const form = useForm<z.infer<typeof passwordSchema>>({ resolver: zodResolver(passwordSchema) });
  const passwordMutation = useChangePasswordMutation();
  const exportMutation = useExportDataMutation();
  const deleteMutation = useDeleteAccountMutation();
  const twoFactorMutation = useToggleTwoFactorMutation();

  return (
    <div className="space-y-4">
      <Card className="space-y-4">
        <h1 className="m-0 text-lg font-semibold">Настройки</h1>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="panel-soft p-4">
            <p className="m-0 text-xs text-subtle">Аккаунт</p>
            <p className="m-0 mt-2 text-sm">{user?.email}</p>
          </div>
          <div className="panel-soft space-y-3 p-4">
            <label className="block text-xs text-subtle">Язык</label>
            <select
              className="h-10 w-full rounded-panel border border-border bg-panel px-3"
              value={language}
              onChange={(event) => {
                const next = event.target.value as "ru" | "en";
                setLanguage(next);
                void api.updatePreferences({ language: next }).catch(() => undefined);
              }}
            >
              <option value="ru">Русский</option>
              <option value="en">English</option>
            </select>
            <label className="block text-xs text-subtle">Тема</label>
            <select
              className="h-10 w-full rounded-panel border border-border bg-panel px-3"
              value={theme}
              onChange={(event) => {
                const next = event.target.value as "light" | "dark" | "system";
                setTheme(next);
                void api.updatePreferences({ theme: next }).catch(() => undefined);
              }}
            >
              <option value="light">Светлая</option>
              <option value="dark">Тёмная</option>
              <option value="system">Системная</option>
            </select>
          </div>
        </div>
      </Card>
      <Card className="space-y-4">
        <p className="m-0 font-semibold">Безопасность</p>
        <form
          className="grid gap-3 md:grid-cols-3"
          onSubmit={form.handleSubmit(async (values) => {
            await passwordMutation.mutateAsync(values);
          })}
        >
          <Input type="password" placeholder="Текущий пароль" {...form.register("current_password")} />
          <Input type="password" placeholder="Новый пароль" {...form.register("new_password")} />
          <Button type="submit">Сменить пароль</Button>
        </form>
        {passwordMutation.data ? <StatusMessage type="success" message={passwordMutation.data.message} /> : null}
        <div className="panel-soft flex items-center justify-between p-4">
          <div>
            <p className="m-0 font-medium">Email 2FA</p>
            <p className="m-0 text-sm text-subtle">Development code support при доступности backend endpoint.</p>
          </div>
          <Button
            variant="secondary"
            onClick={() => void twoFactorMutation.mutateAsync({ enabled: true })}
          >
            Включить / выключить
          </Button>
        </div>
        {twoFactorMutation.error ? <StatusMessage type="error" message="2FA flow unavailable on current backend." /> : null}
      </Card>
      <Card className="space-y-4">
        <p className="m-0 font-semibold">Уведомления</p>
        <div className="space-y-3">
          {[
            ["Email уведомления", preferences?.email_notifications ?? true],
            ["Системные уведомления", preferences?.system_notifications ?? true],
          ].map(([label, value]) => (
            <div key={String(label)} className="flex items-center justify-between">
              <span>{label}</span>
              <Switch.Root
                checked={Boolean(value)}
                onCheckedChange={(checked) => {
                  void api.updatePreferences(
                    label === "Email уведомления"
                      ? { email_notifications: checked }
                      : { system_notifications: checked },
                  );
                }}
                className="relative h-6 w-11 rounded-full bg-border data-[state=checked]:bg-accent"
              >
                <Switch.Thumb className="block h-5 w-5 translate-x-0.5 rounded-full bg-white transition data-[state=checked]:translate-x-[22px]" />
              </Switch.Root>
            </div>
          ))}
        </div>
      </Card>
      <Card className="space-y-3">
        <p className="m-0 font-semibold">Прочее</p>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => void exportMutation.mutateAsync()}>
            Экспорт JSON
          </Button>
          <Button variant="danger" onClick={() => void deleteMutation.mutateAsync("confirm-password")}>
            Удалить аккаунт
          </Button>
        </div>
        {exportMutation.data ? (
          <StatusMessage type="success" message={`Экспорт готов: ${exportMutation.data.exported_at}`} />
        ) : null}
      </Card>
    </div>
  );
}
