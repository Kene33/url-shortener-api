import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { StatusMessage } from "@/components/ui/status-message";
import { AuthFooter, AuthLayout } from "@/pages/shared";

export function RegisterPage() {
  const { t } = useTranslation();
  const schema = z
    .object({
      email: z.email(),
      password: z.string().min(8, t("auth.passwordTooShort")),
      confirmPassword: z.string().min(8, t("auth.passwordTooShort")),
    })
    .refine((value) => value.password === value.confirmPassword, {
      path: ["confirmPassword"],
      message: t("auth.passwordsMustMatch"),
    });
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <AuthLayout
      title={t("auth.registerTitle")}
      subtitle={t("auth.registerSubtitle")}
      footer={<AuthFooter question={t("auth.hasAccount")} action={t("auth.loginAction")} to="/login" />}
    >
      <form
        className="space-y-4"
        onSubmit={form.handleSubmit(async ({ email, password }) => {
          setError(null);
          setMessage(null);
          try {
            const response = await api.register({ email, password });
            setMessage(
              response.verification_token
                ? t("auth.devToken", { token: response.verification_token })
                : t("auth.accountCreated"),
            );
          } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : "Registration failed");
          }
        })}
      >
        <Input placeholder="Email" type="email" {...form.register("email")} />
        <div className="space-y-1">
          <PasswordInput
            placeholder={t("common.password")}
            aria-invalid={Boolean(form.formState.errors.password)}
            aria-describedby={form.formState.errors.password ? "register-password-error" : undefined}
            {...form.register("password")}
          />
          {form.formState.errors.password ? (
            <p id="register-password-error" role="alert" className="m-0 text-sm text-danger">
              {form.formState.errors.password.message}
            </p>
          ) : null}
        </div>
        <div className="space-y-1">
          <PasswordInput
            placeholder={t("common.confirmPassword")}
            aria-invalid={Boolean(form.formState.errors.confirmPassword)}
            aria-describedby={form.formState.errors.confirmPassword ? "register-confirm-password-error" : undefined}
            {...form.register("confirmPassword")}
          />
          {form.formState.errors.confirmPassword ? (
            <p id="register-confirm-password-error" role="alert" className="m-0 text-sm text-danger">
              {form.formState.errors.confirmPassword.message}
            </p>
          ) : null}
        </div>
        <Button type="submit" className="w-full">
          {t("auth.registerAction")}
        </Button>
        {message ? <StatusMessage type="success" message={message} /> : null}
        {error ? <StatusMessage type="error" message={error} /> : null}
      </form>
    </AuthLayout>
  );
}
