import { zodResolver } from "@hookform/resolvers/zod";
import { ChartNoAxesColumn, ShieldCheck, UserRoundPlus, Zap } from "lucide-react";
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
import { useTranslation } from "react-i18next";

const schema = z.object({
  url: z.string().min(1, "URL is required"),
});

export function HomePage() {
  const { t } = useTranslation();
  const { user } = useSession();
  const mutation = useCreateLinkMutation();
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { url: "" },
  });

  const result = mutation.data?.short_url;

  return (
    <div className={user ? "" : "page-shell"}>
      <div className="mx-auto max-w-[1280px] px-4 py-4 md:px-5">
        {!user && (
          <div className="panel mb-4 flex items-center justify-between p-4">
            <Logo />
            <div className="flex items-center gap-2">
              <Link to="/login" className="inline-flex h-9 items-center justify-center rounded-panel border border-border bg-panel px-4 text-sm font-medium text-text transition hover:bg-muted">
                {t("home.login")}
              </Link>
              <Link to="/register" className="inline-flex h-9 items-center justify-center rounded-panel border border-accent bg-accent px-4 text-sm font-medium text-white transition hover:opacity-95">
                {t("home.register")}
              </Link>
              <ThemeLanguageControls />
            </div>
          </div>
        )}
        <div className="grid gap-4">
          <Card className="space-y-6 p-6 md:p-10">
            <div className="space-y-3 text-center md:text-left">
              <h1 className="m-0 max-w-xl text-3xl font-semibold tracking-tight md:text-4xl">
                {t("home.title")}
              </h1>
              <p className="m-0 max-w-lg text-sm text-subtle">
                {t("home.hint")}
              </p>
            </div>
            <form
              className="space-y-4"
              onSubmit={form.handleSubmit((values) =>
                mutation.mutate({ url: values.url, mode: "reuse" }),
              )}
            >
              <div className="flex flex-col gap-3 md:flex-row">
                <Input
                  aria-label="URL input"
                  placeholder={t("home.urlPlaceholder")}
                  {...form.register("url")}
                />
                <Button type="submit" className="md:min-w-36">
                  {t("home.shorten")}
                </Button>
              </div>
              {result ? (
                <div className="panel-soft flex items-center justify-between gap-3 p-3" aria-live="polite">
                  <span className="min-w-0 truncate">{result}</span>
                  <Button variant="secondary" size="sm" onClick={() => void copyToClipboard(result)} type="button">
                    {t("common.copy")}
                  </Button>
                </div>
              ) : null}
              {mutation.isPending ? <StatusMessage type="loading" message={t("home.creatingLink")} /> : null}
              {mutation.error ? (
                <StatusMessage type="error" message={mutation.error.message} />
              ) : null}
            </form>
            {!user && (
              <div className="flex flex-col gap-4 rounded-panel border border-accent/20 bg-accent/5 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent/10 text-accent">
                    <UserRoundPlus className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="m-0 text-sm font-medium">{t("home.accountTitle")}</p>
                    <p className="m-0 mt-1 text-xs leading-5 text-subtle">{t("home.accountDescription")}</p>
                  </div>
                </div>
                <Link to="/register" className="inline-flex h-9 shrink-0 items-center justify-center rounded-panel border border-border bg-panel px-4 text-sm font-medium text-text transition hover:bg-muted">
                  {t("home.accountAction")}
                </Link>
              </div>
            )}
            <div className="grid gap-3 md:grid-cols-3">
              {[
                { icon: Zap, title: t("home.instant"), text: t("home.instantHint") },
                { icon: ShieldCheck, title: t("home.secure"), text: t("home.secureHint") },
                { icon: ChartNoAxesColumn, title: t("home.insights"), text: t("home.insightsHint") },
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
        </div>
      </div>
    </div>
  );
}
