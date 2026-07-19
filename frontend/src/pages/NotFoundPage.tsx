import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/app/logo";
import { ThemeLanguageControls } from "@/components/app/theme-language-controls";

export function NotFoundPage() {
  const { t } = useTranslation();

  return (
    <div className="page-shell flex min-h-screen items-center justify-center p-4">
      <main className="w-full max-w-[560px]">
        <div className="mb-7 flex items-center justify-between"><Logo /><ThemeLanguageControls /></div>
        <section className="panel space-y-5 p-7 sm:p-10">
          <p className="m-0 text-sm font-semibold text-accent">{t("notFound.code")}</p>
          <div className="space-y-2">
            <h1 className="m-0 text-2xl font-semibold">{t("notFound.title")}</h1>
            <p className="m-0 text-sm leading-6 text-subtle">{t("notFound.description")}</p>
          </div>
          <Link to="/"><Button>{t("notFound.action")}</Button></Link>
        </section>
      </main>
    </div>
  );
}
