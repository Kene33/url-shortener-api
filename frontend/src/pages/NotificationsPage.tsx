import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusMessage } from "@/components/ui/status-message";
import { useNotificationsQuery, useReadAllNotificationsMutation, useReadNotificationMutation } from "@/features/notifications/api";
import { formatDate } from "@/lib/utils";

export function NotificationsPage() {
  const notifications = useNotificationsQuery();
  const readAll = useReadAllNotificationsMutation();

  return (
    <div className="space-y-4">
      <Card className="flex items-center justify-between">
        <div>
          <h1 className="m-0 text-lg font-semibold">Уведомления</h1>
          <p className="m-0 text-sm text-subtle">Центр событий аккаунта и ссылок.</p>
        </div>
        <Button variant="secondary" onClick={() => void readAll.mutateAsync()}>
          Прочитать всё
        </Button>
      </Card>
      {notifications.isLoading ? <StatusMessage type="loading" message="Загружаем уведомления…" /> : null}
      {notifications.error ? <StatusMessage type="error" message={notifications.error.message} /> : null}
      {!notifications.isLoading && !notifications.data?.items.length ? (
        <EmptyState title="Уведомлений нет" description="Новые системные события появятся здесь." />
      ) : null}
      <div className="grid gap-3">
        {notifications.data?.items.map((item) => (
          <NotificationRow key={item.id} item={item} />
        ))}
      </div>
    </div>
  );
}

function NotificationRow({ item }: { item: { id: string; title: string; body: string; created_at: string; is_read: boolean } }) {
  const readMutation = useReadNotificationMutation(item.id);

  return (
    <Card className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <p className="m-0 font-semibold">{item.title}</p>
          {!item.is_read ? <span className="rounded-full bg-accent/10 px-2 py-0.5 text-[11px] text-accent">new</span> : null}
        </div>
        <p className="m-0 text-sm text-subtle">{item.body}</p>
        <p className="m-0 text-xs text-subtle">{formatDate(item.created_at)}</p>
      </div>
      {!item.is_read ? (
        <Button variant="secondary" onClick={() => void readMutation.mutateAsync()}>
          Отметить как прочитанное
        </Button>
      ) : null}
    </Card>
  );
}
