import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusMessage } from "@/components/ui/status-message";
import { AuthLayout } from "@/pages/shared";

const schema = z.object({ email: z.email() });

export function ForgotPasswordPage() {
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <AuthLayout title="Сброс пароля" subtitle="Отправим токен восстановления." footer={null}>
      <form
        className="space-y-4"
        onSubmit={form.handleSubmit(async ({ email }) => {
          setError(null);
          setMessage(null);
          try {
            const response = await api.requestPasswordReset(email);
            setMessage(
              response.action_token
                ? `Dev token: ${response.action_token}`
                : "Инструкции подготовлены, если аккаунт существует.",
            );
          } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : "Request failed");
          }
        })}
      >
        <Input placeholder="Email" type="email" {...form.register("email")} />
        <Button type="submit" className="w-full">
          Запросить токен
        </Button>
        {message ? <StatusMessage type="success" message={message} /> : null}
        {error ? <StatusMessage type="error" message={error} /> : null}
      </form>
    </AuthLayout>
  );
}
