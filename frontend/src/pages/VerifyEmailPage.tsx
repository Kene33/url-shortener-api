import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusMessage } from "@/components/ui/status-message";
import { AuthLayout } from "@/pages/shared";

const schema = z.object({ token: z.string().min(8) });

export function VerifyEmailPage() {
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <AuthLayout title="Подтверждение email" subtitle="Введите токен подтверждения." footer={null}>
      <form
        className="space-y-4"
        onSubmit={form.handleSubmit(async ({ token }) => {
          setError(null);
          setMessage(null);
          try {
            await api.verifyEmail(token);
            setMessage("Email подтверждён.");
          } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : "Verification failed");
          }
        })}
      >
        <Input placeholder="Verification token" {...form.register("token")} />
        <Button type="submit" className="w-full">
          Подтвердить
        </Button>
        {message ? <StatusMessage type="success" message={message} /> : null}
        {error ? <StatusMessage type="error" message={error} /> : null}
      </form>
    </AuthLayout>
  );
}
