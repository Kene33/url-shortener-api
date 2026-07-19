import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { StatusMessage } from "@/components/ui/status-message";
import { useSession } from "@/features/session/session-provider";
import { AuthFooter, AuthLayout } from "@/pages/shared";

const loginSchema = z.object({
  email: z.email(),
  password: z.string().min(8),
});

const twoFactorSchema = z.object({
  code: z.string().min(4),
});

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { login, verifyTwoFactor } = useSession();
  const [challenge, setChallenge] = useState<{ token: string; debugCode?: string | null } | null>(null);
  const form = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema) });
  const codeForm = useForm<z.infer<typeof twoFactorSchema>>({ resolver: zodResolver(twoFactorSchema) });
  const [error, setError] = useState<string | null>(null);

  return (
    <AuthLayout
      title={t("auth.loginTitle")}
      subtitle={t("auth.loginSubtitle")}
      footer={<AuthFooter question={t("auth.noAccount")} action={t("auth.registerAction")} to="/register" />}
    >
      {!challenge ? (
        <form
          className="space-y-4"
          onSubmit={form.handleSubmit(async (values) => {
            setError(null);
            try {
              const result = await login(values);
              if (result?.requires_two_factor) {
                setChallenge({ token: result.login_token, debugCode: result.debug_code });
                return;
              }
              navigate("/links");
            } catch (nextError) {
              setError(nextError instanceof Error ? nextError.message : "Login failed");
            }
          })}
        >
          <Input placeholder="Email" type="email" {...form.register("email")} />
          <PasswordInput placeholder={t("common.password")} {...form.register("password")} />
          <Button type="submit" className="w-full">
            {t("auth.loginAction")}
          </Button>
          <Link to="/forgot-password" className="block text-sm text-accent">
            {t("auth.forgotPassword")}
          </Link>
          {error ? <StatusMessage type="error" message={error} /> : null}
        </form>
      ) : (
        <form
          className="space-y-4"
          onSubmit={codeForm.handleSubmit(async ({ code }) => {
            setError(null);
            try {
              await verifyTwoFactor({ login_token: challenge.token, code });
              navigate("/links");
            } catch (nextError) {
              setError(nextError instanceof Error ? nextError.message : "Verification failed");
            }
          })}
        >
          <Input placeholder={t("auth.twoFactorCode")} {...codeForm.register("code")} />
          {challenge.debugCode ? <StatusMessage type="success" message={`Dev code: ${challenge.debugCode}`} /> : null}
          <Button type="submit" className="w-full">
            {t("common.confirm")}
          </Button>
          {error ? <StatusMessage type="error" message={error} /> : null}
        </form>
      )}
    </AuthLayout>
  );
}
