import { zodResolver } from "@hookform/resolvers/zod";
import { ChartNoAxesColumn, ShieldCheck, Zap } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ThemeLanguageControls } from "@/components/app/theme-language-controls";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusMessage } from "@/components/ui/status-message";
import { Logo } from "@/components/app/logo";
import { useCreateLinkMutation } from "@/features/links/api";
import { useSession } from "@/features/session/session-provider";
import { copyToClipboard } from "@/lib/utils";
import { Link } from "react-router-dom";

const schema = z.object({
  url: z.string().min(1, "URL is required"),
});

export function HomePage() {
  const { user } = useSession();
  const mutation = useCreateLinkMutation();
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { url: "" },
  });

  const result = mutation.data?.short_url;

  return (
    <div className="page-shell">
      <div className="mx-auto max-w-[1280px] px-4 py-4 md:px-5">
        <div className="panel mb-4 flex items-center justify-between p-4">
          <Logo />
          <div className="flex items-center gap-2">
            {!user && (
              <>
                <Link to="/login" className="pill">
                  Войти
                </Link>
                <Link to="/register" className="rounded-panel bg-accent px-4 py-2 text-sm font-medium text-white">
                  Регистрация
                </Link>
              </>
            )}
            <ThemeLanguageControls />
          </div>
        </div>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Card className="space-y-6 p-6 md:p-10">
            <div className="space-y-3 text-center md:text-left">
              <h1 className="m-0 max-w-xl text-3xl font-semibold tracking-tight md:text-4xl">
                Сокращайте ссылки быстро и просто
              </h1>
              <p className="m-0 max-w-lg text-sm text-subtle">
                Без регистрации. Бесплатно. Компактный интерфейс для ежедневной работы с короткими ссылками.
              </p>
            </div>
            <form
              className="space-y-4"
              onSubmit={form.handleSubmit((values) =>
                mutation.mutate({ url: values.url, mode: user ? "new" : "reuse" }),
              )}
            >
              <div className="flex flex-col gap-3 md:flex-row">
                <Input
                  aria-label="URL input"
                  placeholder="Вставьте ссылку или домен"
                  {...form.register("url")}
                />
                <Button type="submit" className="md:min-w-36">
                  Сократить
                </Button>
              </div>
              {result ? (
                <div className="panel-soft flex items-center justify-between gap-3 p-3" aria-live="polite">
                  <span className="min-w-0 truncate">{result}</span>
                  <Button variant="secondary" size="sm" onClick={() => void copyToClipboard(result)} type="button">
                    Копировать
                  </Button>
                </div>
              ) : null}
              {mutation.isPending ? <StatusMessage type="loading" message="Создаём короткую ссылку…" /> : null}
              {mutation.error ? (
                <StatusMessage type="error" message={mutation.error.message} />
              ) : null}
            </form>
            <div className="grid gap-3 md:grid-cols-3">
              {[
                { icon: Zap, title: "Мгновенно", text: "Гостевой режим и быстрый повтор ссылок." },
                { icon: ShieldCheck, title: "Безопасно", text: "Контроль активности и приватные account flows." },
                { icon: ChartNoAxesColumn, title: "Наглядно", text: "Маршруты для аналитики, папок и событий." },
              ].map(({ icon: Icon, title, text }) => (
                <div key={title} className="panel-soft space-y-3 p-4">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-accent/10 text-accent">
                    <Icon className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="m-0 font-medium">{title}</p>
                    <p className="m-0 mt-1 text-xs leading-5 text-subtle">{text}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
          {user ? (
            <Card className="space-y-4">
              <p className="m-0 text-sm font-semibold">Навигация</p>
              <div className="grid gap-2">
                {[
                  ["/links", "Мои ссылки"],
                  ["/analytics", "Аналитика"],
                  ["/folders", "Папки"],
                ].map(([to, label]) => (
                  <Link key={to} to={to} className="panel-soft px-4 py-3 text-sm text-subtle hover:text-text">
                    {label}
                  </Link>
                ))}
              </div>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}
