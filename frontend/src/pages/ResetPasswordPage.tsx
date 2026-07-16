import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusMessage } from "@/components/ui/status-message";
import { AuthLayout } from "@/pages/shared";

const schema = z.object({
  token: z.string().min(8),
  new_password: z.string().min(8),
});

export function ResetPasswordPage() {
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <AuthLayout title="Новый пароль" subtitle="Введите токен и новый пароль." footer={null}>
      <form
        className="space-y-4"
        onSubmit={form.handleSubmit(async (values) => {
          setError(null);
          setMessage(null);
          try {
            const response = await api.resetPassword(values);
            setMessage(response.message);
          } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : "Reset failed");
          }
        })}
      >
        <Input placeholder="Reset token" {...form.register("token")} />
        <Input placeholder="Новый пароль" type="password" {...form.register("new_password")} />
        <Button type="submit" className="w-full">
          Обновить пароль
        </Button>
        {message ? <StatusMessage type="success" message={message} /> : null}
        {error ? <StatusMessage type="error" message={error} /> : null}
      </form>
    </AuthLayout>
  );
}
