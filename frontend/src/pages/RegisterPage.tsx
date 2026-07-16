import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusMessage } from "@/components/ui/status-message";
import { AuthFooter, AuthLayout } from "@/pages/shared";

const schema = z
  .object({
    email: z.email(),
    password: z.string().min(8),
    confirmPassword: z.string().min(8),
  })
  .refine((value) => value.password === value.confirmPassword, {
    path: ["confirmPassword"],
    message: "Passwords must match",
  });

export function RegisterPage() {
  const { t } = useTranslation();
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
                ? `Аккаунт создан. Dev token: ${response.verification_token}`
                : "Аккаунт создан. Проверьте email для подтверждения.",
            );
          } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : "Registration failed");
          }
        })}
      >
        <Input placeholder="Email" type="email" {...form.register("email")} />
        <Input placeholder={t("common.password")} type="password" {...form.register("password")} />
        <Input placeholder={t("common.confirmPassword")} type="password" {...form.register("confirmPassword")} />
        <Button type="submit" className="w-full">
          {t("auth.registerAction")}
        </Button>
        {message ? <StatusMessage type="success" message={message} /> : null}
        {error ? <StatusMessage type="error" message={error} /> : null}
      </form>
    </AuthLayout>
  );
}
