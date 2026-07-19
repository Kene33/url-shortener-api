import * as Dialog from "@radix-ui/react-dialog";
import { Check, Pencil, Power } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { AdminLinkItem } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { StatusMessage } from "@/components/ui/status-message";
import { useAdminLinksQuery, useUpdateAdminLinkMutation } from "@/features/admin/api";
import { formatDate } from "@/lib/utils";
import {
  AdminConfirmDialog,
  AdminDialogShell,
  AdminPageHeader,
  AdminPagination,
} from "@/pages/admin-shared";

const PAGE_SIZE = 10;

export function AdminLinksPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [ownerId, setOwnerId] = useState("");
  const [status, setStatus] = useState("");
  const [editingLink, setEditingLink] = useState<AdminLinkItem | null>(null);
  const [toggleTarget, setToggleTarget] = useState<AdminLinkItem | null>(null);
  const [label, setLabel] = useState("");

  const links = useAdminLinksQuery({
    owner_id: ownerId || undefined,
    is_active: status || undefined,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });

  const updateLink = useUpdateAdminLinkMutation(editingLink?.shortcode ?? toggleTarget?.shortcode ?? "");
  const items = useMemo(() => links.data?.items ?? [], [links.data]);

  useEffect(() => {
    if (editingLink) {
      setLabel(editingLink.label ?? "");
    }
  }, [editingLink]);

  const saveLabel = async () => {
    if (!editingLink) return;
    await updateLink.mutateAsync({ label: label.trim() || null });
    setEditingLink(null);
  };

  const toggleActive = async () => {
    if (!toggleTarget) return;
    await updateLink.mutateAsync({ is_active: !toggleTarget.is_active });
    setToggleTarget(null);
  };

  return (
    <div className="space-y-4">
      <AdminPageHeader title={t("admin.linksTitle")} subtitle={t("admin.linksSubtitle")} />

      <Card className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <label className="grid gap-1 text-xs text-subtle">
          {t("admin.ownerId")}
          <Input
            inputMode="numeric"
            placeholder={t("admin.ownerIdPlaceholder")}
            value={ownerId}
            onChange={(event) => {
              setOwnerId(event.target.value.replace(/[^\d]/g, ""));
              setPage(1);
            }}
          />
        </label>
        <label className="grid gap-1 text-xs text-subtle">
          {t("common.status")}
          <select
            className="h-10 rounded-panel border border-border bg-panel px-3 text-sm text-text"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">{t("admin.allStatuses")}</option>
            <option value="true">{t("common.active")}</option>
            <option value="false">{t("common.disabled")}</option>
          </select>
        </label>
      </Card>

      {links.isLoading ? <StatusMessage type="loading" message={t("admin.linksLoading")} /> : null}
      {links.error ? <StatusMessage type="error" message={links.error.message} /> : null}

      {!links.isLoading && !links.error && !items.length ? (
        <EmptyState title={t("admin.linksEmptyTitle")} description={t("admin.linksEmptyDescription")} />
      ) : null}

      {!links.isLoading && !links.error && items.length ? (
        <div className="grid gap-3">
          {items.map((item) => (
            <Card key={item.shortcode} className="space-y-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="m-0 text-base font-semibold">{item.label || t("common.noLabel")}</p>
                    <span className={`pill ${item.is_active ? "border-accent/40 bg-accent/10 text-accent" : "text-subtle"}`}>
                      {item.is_active ? t("common.active") : t("common.disabled")}
                    </span>
                  </div>
                  <p className="m-0 break-all text-sm text-subtle">{item.short_url}</p>
                  <p className="m-0 break-all text-sm text-subtle">{item.url}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Dialog.Root open={editingLink?.shortcode === item.shortcode} onOpenChange={(open) => setEditingLink(open ? item : null)}>
                    <Dialog.Trigger asChild>
                      <Button variant="secondary">
                        <Pencil className="h-4 w-4" />
                        {t("admin.editLink")}
                      </Button>
                    </Dialog.Trigger>
                    <AdminDialogShell title={t("admin.editLinkTitle")} description={t("admin.immutableHint")}>
                      <div className="space-y-4">
                        <div className="grid gap-1 text-sm">
                          <span className="text-subtle">{t("admin.shortcode")}</span>
                          <div className="rounded-panel border border-border bg-muted/40 px-3 py-2 font-medium">{item.shortcode}</div>
                        </div>
                        <div className="grid gap-1 text-sm">
                          <span className="text-subtle">{t("admin.destinationUrl")}</span>
                          <div className="rounded-panel border border-border bg-muted/40 px-3 py-2 break-all">{item.url}</div>
                        </div>
                        <label className="grid gap-1 text-sm">
                          <span className="text-subtle">{t("admin.linkLabel")}</span>
                          <Input
                            value={label}
                            onChange={(event) => setLabel(event.target.value)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter" && !event.shiftKey) {
                                event.preventDefault();
                                void saveLabel();
                              }
                            }}
                          />
                        </label>
                        {updateLink.error ? <StatusMessage type="error" message={updateLink.error.message} /> : null}
                        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                          <Dialog.Close asChild>
                            <Button variant="secondary">{t("common.cancel")}</Button>
                          </Dialog.Close>
                          <Button onClick={() => void saveLabel()} disabled={updateLink.isPending}>
                            <Check className="h-4 w-4" />
                            {t("admin.saveLink")}
                          </Button>
                        </div>
                      </div>
                    </AdminDialogShell>
                  </Dialog.Root>
                  <Button
                    variant={item.is_active ? "danger" : "secondary"}
                    onClick={() => setToggleTarget(item)}
                  >
                    <Power className="h-4 w-4" />
                    {item.is_active ? t("admin.disableLink") : t("admin.enableLink")}
                  </Button>
                </div>
              </div>

              <div className="grid gap-2 border-t border-border pt-4 text-sm text-subtle sm:grid-cols-2 xl:grid-cols-4">
                <span>{t("admin.ownerEmail")}: {item.owner_email || t("common.notSet")}</span>
                <span>{t("admin.ownerId")}: {item.owner_id ?? t("common.notSet")}</span>
                <span>{t("common.createdAt")}: {formatDate(item.created_at)}</span>
                <span>{t("common.updatedAt")}: {formatDate(item.updated_at)}</span>
                <span>{t("admin.lastAccessed")}: {formatDate(item.last_accessed_at)}</span>
                <span>{t("admin.expiresAt")}: {formatDate(item.expires_at)}</span>
              </div>
            </Card>
          ))}
        </div>
      ) : null}

      {!links.isLoading && !links.error && links.data ? (
        <AdminPagination page={page} total={links.data.total} pageSize={PAGE_SIZE} onPageChange={setPage} />
      ) : null}

      <AdminConfirmDialog
        open={Boolean(toggleTarget)}
        onOpenChange={(open) => {
          if (!open) setToggleTarget(null);
        }}
        title={toggleTarget?.is_active ? t("admin.confirmDisableLinkTitle") : t("admin.confirmEnableLinkTitle")}
        description={t("admin.confirmLinkChangeDescription", {
          shortcode: toggleTarget?.shortcode ?? "",
          action: toggleTarget?.is_active ? t("admin.disableLink") : t("admin.enableLink"),
        })}
        confirmLabel={toggleTarget?.is_active ? t("admin.disableLink") : t("admin.enableLink")}
        confirmVariant={toggleTarget?.is_active ? "danger" : "primary"}
        pending={updateLink.isPending}
        onConfirm={() => void toggleActive()}
      />
    </div>
  );
}
