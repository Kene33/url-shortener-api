import * as AlertDialog from "@radix-ui/react-alert-dialog";
import * as Dialog from "@radix-ui/react-dialog";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { PropsWithChildren, ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export function AdminPageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle: string;
  actions?: ReactNode;
}) {
  const { t } = useTranslation();

  return (
    <Card className="space-y-3">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="space-y-1">
          <p className="m-0 text-sm font-semibold text-accent">{t("admin.title")}</p>
          <h1 className="m-0 text-xl font-semibold sm:text-2xl">{title}</h1>
          <p className="m-0 max-w-3xl text-sm text-subtle">{subtitle}</p>
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
    </Card>
  );
}

export function AdminStatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="space-y-2">
      <p className="m-0 text-sm text-subtle">{label}</p>
      <p className="m-0 text-2xl font-semibold">{value}</p>
      {hint ? <p className="m-0 text-xs text-subtle">{hint}</p> : null}
    </Card>
  );
}

export function AdminPagination({
  page,
  total,
  pageSize,
  onPageChange,
}: {
  page: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}) {
  const { t } = useTranslation();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = total === 0 ? 0 : Math.min(page * pageSize, total);

  return (
    <Card className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="m-0 text-sm text-subtle">{t("admin.pageRange", { start, end, total })}</p>
      <div className="flex items-center gap-2 self-end sm:self-auto">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          aria-label={t("admin.previousPage")}
        >
          <ChevronLeft className="h-4 w-4" />
          {t("admin.previousPage")}
        </Button>
        <span className="min-w-[5rem] text-center text-sm text-subtle">
          {t("admin.pageNumber", { page, totalPages })}
        </span>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          aria-label={t("admin.nextPage")}
        >
          {t("admin.nextPage")}
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </Card>
  );
}

export function AdminQuickLink({ to, label }: { to: string; label: string }) {
  return (
    <Link to={to}>
      <Button variant="secondary">{label}</Button>
    </Link>
  );
}

export function AdminDialogShell({
  title,
  description,
  children,
}: PropsWithChildren<{ title: string; description?: string }>) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
      <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,520px)] max-h-[85vh] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-panel border border-border bg-panel p-6 outline-none">
        <Dialog.Title className="text-lg font-semibold">{title}</Dialog.Title>
        {description ? <Dialog.Description className="mt-2 text-sm text-subtle">{description}</Dialog.Description> : null}
        <div className="mt-5">{children}</div>
      </Dialog.Content>
    </Dialog.Portal>
  );
}

export function AdminConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  confirmVariant = "primary",
  pending,
  confirmDisabled,
  onConfirm,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  confirmVariant?: "primary" | "danger";
  pending?: boolean;
  confirmDisabled?: boolean;
  onConfirm: () => void;
  children?: ReactNode;
}) {
  const { t } = useTranslation();

  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <AlertDialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,460px)] -translate-x-1/2 -translate-y-1/2 rounded-panel border border-border bg-panel p-6 outline-none">
          <AlertDialog.Title className="text-lg font-semibold">{title}</AlertDialog.Title>
          <AlertDialog.Description className="mt-2 text-sm text-subtle">{description}</AlertDialog.Description>
          {children ? <div className="mt-4">{children}</div> : null}
          <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <AlertDialog.Cancel asChild>
              <Button variant="secondary">{t("common.cancel")}</Button>
            </AlertDialog.Cancel>
            <Button variant={confirmVariant} onClick={onConfirm} disabled={pending || confirmDisabled}>
              {confirmLabel}
            </Button>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
