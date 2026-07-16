import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  const navigate = useNavigate();
  const { login, verifyTwoFactor } = useSession();
  const [challenge, setChallenge] = useState<{ token: string; debugCode?: string | null } | null>(null);
  const form = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema) });
  const codeForm = useForm<z.infer<typeof twoFactorSchema>>({ resolver: zodResolver(twoFactorSchema) });
  const [error, setError] = useState<string | null>(null);

  return (
    <AuthLayout
      title="Вход"
      subtitle="Email, пароль и при необходимости код подтверждения."
      footer={<AuthFooter question="Нет аккаунта?" action="Зарегистрироваться" to="/register" />}
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
          <Input placeholder="Пароль" type="password" {...form.register("password")} />
          <Button type="submit" className="w-full">
            Войти
          </Button>
          <Link to="/forgot-password" className="block text-sm text-accent">
            Забыли пароль?
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
          <Input placeholder="Код 2FA" {...codeForm.register("code")} />
          {challenge.debugCode ? <StatusMessage type="success" message={`Dev code: ${challenge.debugCode}`} /> : null}
          <Button type="submit" className="w-full">
            Подтвердить
          </Button>
          {error ? <StatusMessage type="error" message={error} /> : null}
        </form>
      )}
    </AuthLayout>
  );
}
