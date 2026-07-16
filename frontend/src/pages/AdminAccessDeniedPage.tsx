import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export function AdminAccessDeniedPage() {
  const { t } = useTranslation();

  return (
    <Card className="space-y-4 p-6 sm:p-8">
      <div className="space-y-2">
        <p className="m-0 text-sm font-semibold text-accent">{t("admin.title")}</p>
        <h1 className="m-0 text-2xl font-semibold">{t("admin.accessDeniedTitle")}</h1>
        <p className="m-0 text-sm text-subtle">{t("admin.accessDeniedDescription")}</p>
      </div>
      <Link to="/links">
        <Button>{t("admin.accessDeniedAction")}</Button>
      </Link>
    </Card>
  );
}
