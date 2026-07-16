import * as AlertDialog from "@radix-ui/react-alert-dialog";
import * as Switch from "@radix-ui/react-switch";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusMessage } from "@/components/ui/status-message";
import { useSession } from "@/features/session/session-provider";
import { useTheme } from "@/features/theme/theme-provider";
import {
  useChangePasswordMutation,
  useDeleteAccountMutation,
  useExportDataMutation,
} from "@/features/settings/api";

const passwordSchema = z.object({
  current_password: z.string().min(8),
  new_password: z.string().min(8),
});

export function SettingsPage() {
  const { user, preferences } = useSession();
  const { language, resolvedTheme, setLanguage, setTheme } = useTheme();
  const form = useForm<z.infer<typeof passwordSchema>>({ resolver: zodResolver(passwordSchema) });
  const passwordMutation = useChangePasswordMutation();
  const exportMutation = useExportDataMutation();
  const deleteMutation = useDeleteAccountMutation();
  const [twoFactorCode, setTwoFactorCode] = useState("");
  const [twoFactorMessage, setTwoFactorMessage] = useState<string | null>(null);
  const [twoFactorError, setTwoFactorError] = useState<string | null>(null);
  const [twoFactorPending, setTwoFactorPending] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");

  const exportJson = async () => {
    const data = await exportMutation.mutateAsync();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "linkcutter-export.json";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const requestTwoFactor = async () => {
    setTwoFactorError(null);
    try {
      const response = await api.requestEnableTwoFactor();
      setTwoFactorPending(true);
      setTwoFactorMessage(response.debug_code ? `Development code: ${response.debug_code}` : response.message);
    } catch (error) {
      setTwoFactorError(error instanceof Error ? error.message : "Could not start two-factor authentication");
    }
  };

  return (
    <div className="space-y-4">
      <Card className="space-y-4">
        <h1 className="m-0 text-lg font-semibold">Настройки</h1>
        <div className="grid gap-5 md:grid-cols-2">
          <div>
            <p className="m-0 text-xs text-subtle">Аккаунт</p>
            <p className="m-0 mt-2 text-sm">{user?.email}</p>
          </div>
          <div className="grid gap-3">
            <label className="grid gap-1 text-xs text-subtle">Язык
              <select className="h-10 rounded-panel border border-border bg-panel px-3 text-text" value={language} onChange={(event) => {
                const next = event.target.value as "ru" | "en";
                setLanguage(next);
                void api.updatePreferences({ language: next });
              }}>
                <option value="ru">Русский</option><option value="en">English</option>
              </select>
            </label>
            <label className="grid gap-1 text-xs text-subtle">Тема
              <select className="h-10 rounded-panel border border-border bg-panel px-3 text-text" value={resolvedTheme} onChange={(event) => {
                const next = event.target.value as "light" | "dark";
                setTheme(next);
                void api.updatePreferences({ theme: next });
              }}>
                <option value="light">Светлая</option><option value="dark">Тёмная</option>
              </select>
            </label>
          </div>
        </div>
      </Card>

      <Card className="space-y-4">
        <p className="m-0 font-semibold">Безопасность</p>
        <form className="grid gap-3 md:grid-cols-3" onSubmit={form.handleSubmit(async (values) => passwordMutation.mutateAsync(values))}>
          <Input type="password" placeholder="Текущий пароль" {...form.register("current_password")} />
          <Input type="password" placeholder="Новый пароль" {...form.register("new_password")} />
          <Button type="submit">Сменить пароль</Button>
        </form>
        {passwordMutation.data ? <StatusMessage type="success" message={passwordMutation.data.message} /> : null}
        <div className="border-t border-border pt-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div><p className="m-0 font-medium">Email 2FA</p><p className="m-0 text-sm text-subtle">{user?.two_factor_enabled ? "Включена" : "Защищает вход одноразовым кодом."}</p></div>
            {user?.two_factor_enabled ? <Button variant="secondary" onClick={() => void api.disableTwoFactor()}>Отключить</Button> : <Button variant="secondary" onClick={() => void requestTwoFactor()}>Включить</Button>}
          </div>
          {twoFactorPending ? <div className="mt-3 flex flex-col gap-2 sm:flex-row"><Input value={twoFactorCode} onChange={(event) => setTwoFactorCode(event.target.value)} placeholder="Код подтверждения" /><Button onClick={() => void api.confirmEnableTwoFactor(twoFactorCode).then(() => { setTwoFactorPending(false); setTwoFactorMessage("Двухэтапный вход включён."); }).catch((error: unknown) => setTwoFactorError(error instanceof Error ? error.message : "Invalid code"))}>Подтвердить</Button></div> : null}
          {twoFactorMessage ? <StatusMessage type="success" message={twoFactorMessage} /> : null}
          {twoFactorError ? <StatusMessage type="error" message={twoFactorError} /> : null}
        </div>
      </Card>

      <Card className="space-y-3">
        <p className="m-0 font-semibold">Уведомления</p>
        {[
          ["Email уведомления", preferences?.email_notifications ?? true, "email_notifications"],
          ["Системные уведомления", preferences?.system_notifications ?? true, "system_notifications"],
        ].map(([label, value, field]) => (
          <div key={String(field)} className="flex items-center justify-between gap-4"><span>{label}</span>
            <Switch.Root checked={Boolean(value)} onCheckedChange={(checked) => void api.updatePreferences({ [String(field)]: checked })} className="relative h-6 w-11 rounded-full bg-border data-[state=checked]:bg-accent">
              <Switch.Thumb className="block h-5 w-5 translate-x-0.5 rounded-full bg-white transition data-[state=checked]:translate-x-[22px]" />
            </Switch.Root>
          </div>
        ))}
      </Card>

      <Card className="space-y-3">
        <p className="m-0 font-semibold">Данные аккаунта</p>
        <div className="flex flex-wrap gap-2"><Button variant="secondary" onClick={() => void exportJson()}>Экспорт JSON</Button>
          <AlertDialog.Root><AlertDialog.Trigger asChild><Button variant="danger">Удалить аккаунт</Button></AlertDialog.Trigger><AlertDialog.Portal><AlertDialog.Overlay className="fixed inset-0 bg-black/50" /><AlertDialog.Content className="fixed left-1/2 top-1/2 w-[min(92vw,420px)] -translate-x-1/2 -translate-y-1/2 rounded-panel border border-border bg-panel p-6"><AlertDialog.Title className="text-lg font-semibold">Удалить аккаунт?</AlertDialog.Title><AlertDialog.Description className="mt-2 text-sm text-subtle">Профиль будет анонимизирован. Ссылки продолжат работать только ограниченный срок.</AlertDialog.Description><Input className="mt-4" type="password" value={deletePassword} onChange={(event) => setDeletePassword(event.target.value)} placeholder="Подтвердите паролем" /><div className="mt-5 flex gap-2"><AlertDialog.Cancel asChild><Button variant="secondary">Отмена</Button></AlertDialog.Cancel><AlertDialog.Action asChild><Button variant="danger" onClick={() => void deleteMutation.mutateAsync(deletePassword)}>Удалить</Button></AlertDialog.Action></div></AlertDialog.Content></AlertDialog.Portal></AlertDialog.Root>
        </div>
        {deleteMutation.error ? <StatusMessage type="error" message={deleteMutation.error.message} /> : null}
      </Card>
    </div>
  );
}
