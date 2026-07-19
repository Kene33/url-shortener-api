import { Shield, UserCheck, UserMinus } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { User } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusMessage } from "@/components/ui/status-message";
import { useUpdateAdminUserMutation, useAdminUsersQuery } from "@/features/admin/api";
import { useSession } from "@/features/session/session-provider";
import { formatDate } from "@/lib/utils";
import { AdminConfirmDialog, AdminPageHeader, AdminPagination } from "@/pages/admin-shared";

const PAGE_SIZE = 10;

export function AdminUsersPage() {
  const { t } = useTranslation();
  const { user: sessionUser } = useSession();
  const [page, setPage] = useState(1);
  const [pendingAction, setPendingAction] = useState<{
    user: User;
    field: "is_active" | "is_admin";
    nextValue: boolean;
  } | null>(null);

  const users = useAdminUsersQuery({ limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE });
  const items = useMemo(() => users.data?.items ?? [], [users.data]);
  const selectedUserId = pendingAction?.user.id ?? -1;
  const updateUser = useUpdateAdminUserMutation(selectedUserId);

  const confirmTitle =
    pendingAction?.field === "is_admin"
      ? pendingAction.nextValue
        ? t("admin.confirmGrantAdminTitle")
        : t("admin.confirmRemoveAdminTitle")
      : pendingAction?.nextValue
        ? t("admin.confirmActivateUserTitle")
        : t("admin.confirmDisableUserTitle");

  const confirmDescription = pendingAction
    ? t("admin.confirmUserChangeDescription", {
        email: pendingAction.user.email,
        action:
          pendingAction.field === "is_admin"
            ? pendingAction.nextValue
              ? t("admin.makeAdmin")
              : t("admin.removeAdmin")
            : pendingAction.nextValue
              ? t("admin.activateUser")
              : t("admin.disableUser"),
      })
    : "";

  const confirmAction = async () => {
    if (!pendingAction) return;
    await updateUser.mutateAsync({ [pendingAction.field]: pendingAction.nextValue });
    setPendingAction(null);
  };

  return (
    <div className="space-y-4">
      <AdminPageHeader title={t("admin.usersTitle")} subtitle={t("admin.usersSubtitle")} />
      {users.isLoading ? <StatusMessage type="loading" message={t("admin.usersLoading")} /> : null}
      {users.error ? <StatusMessage type="error" message={users.error.message} /> : null}

      {!users.isLoading && !users.error && !items.length ? (
        <EmptyState title={t("admin.usersEmptyTitle")} description={t("admin.usersEmptyDescription")} />
      ) : null}

      {!users.isLoading && !users.error && items.length ? (
        <div className="grid gap-3">
          {items.map((item) => {
            const isSelf = sessionUser?.id === item.id;
            return (
              <Card key={item.id} className="space-y-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="m-0 truncate text-base font-semibold">{item.display_name || item.email}</p>
                      {item.is_admin ? <span className="pill border-accent/40 bg-accent/10 text-accent">{t("common.admin")}</span> : null}
                      {!item.is_active ? <span className="pill text-danger">{t("common.disabled")}</span> : null}
                    </div>
                    <p className="m-0 truncate text-sm text-subtle">{item.email}</p>
                  </div>
                  <div className="grid gap-1 text-sm text-subtle sm:grid-cols-2 lg:text-right">
                    <span>{t("common.createdAt")}: {formatDate(item.created_at)}</span>
                    <span>{t("common.updatedAt")}: {formatDate(item.updated_at)}</span>
                  </div>
                </div>

                <div className="grid gap-3 border-t border-border pt-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                  <div className="grid gap-2 text-sm text-subtle sm:grid-cols-2">
                    <span>{t("common.role")}: {item.is_admin ? t("common.admin") : t("common.user")}</span>
                    <span>{t("common.status")}: {item.is_active ? t("common.active") : t("common.disabled")}</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      onClick={() => setPendingAction({ user: item, field: "is_admin", nextValue: !item.is_admin })}
                      disabled={isSelf}
                    >
                      <Shield className="h-4 w-4" />
                      {item.is_admin ? t("admin.removeAdmin") : t("admin.makeAdmin")}
                    </Button>
                    <Button
                      variant={item.is_active ? "danger" : "secondary"}
                      onClick={() => setPendingAction({ user: item, field: "is_active", nextValue: !item.is_active })}
                      disabled={isSelf}
                    >
                      {item.is_active ? <UserMinus className="h-4 w-4" /> : <UserCheck className="h-4 w-4" />}
                      {item.is_active ? t("admin.disableUser") : t("admin.activateUser")}
                    </Button>
                  </div>
                </div>

                {isSelf ? <p className="m-0 text-sm text-subtle">{t("admin.selfProtectedHint")}</p> : null}
              </Card>
            );
          })}
        </div>
      ) : null}

      {!users.isLoading && !users.error && users.data ? (
        <AdminPagination page={page} total={users.data.total} pageSize={PAGE_SIZE} onPageChange={setPage} />
      ) : null}

      <AdminConfirmDialog
        open={Boolean(pendingAction)}
        onOpenChange={(open) => {
          if (!open) setPendingAction(null);
        }}
        title={confirmTitle}
        description={confirmDescription}
        confirmLabel={
          pendingAction?.field === "is_admin"
            ? pendingAction.nextValue
              ? t("admin.makeAdmin")
              : t("admin.removeAdmin")
            : pendingAction?.nextValue
              ? t("admin.activateUser")
              : t("admin.disableUser")
        }
        confirmVariant={pendingAction?.field === "is_active" && pendingAction.nextValue === false ? "danger" : "primary"}
        pending={updateUser.isPending}
        onConfirm={() => void confirmAction()}
      />
    </div>
  );
}
