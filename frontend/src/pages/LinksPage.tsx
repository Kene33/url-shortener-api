import * as Dialog from "@radix-ui/react-dialog";
import * as Select from "@radix-ui/react-select";
import * as Switch from "@radix-ui/react-switch";
import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronDown, Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusMessage } from "@/components/ui/status-message";
import { useFoldersQuery } from "@/features/folders/api";
import { useCreateLinkMutation, useLinksQuery, useUpdateLinkMutation } from "@/features/links/api";
import { copyToClipboard, formatDate } from "@/lib/utils";

const schema = z.object({
  url: z.string().min(1),
  label: z.string().optional(),
  mode: z.enum(["reuse", "new"]),
  folder_id: z.string().optional(),
});

export function LinksPage() {
  const [search, setSearch] = useState("");
  const [active, setActive] = useState("all");
  const [folderId, setFolderId] = useState("");
  const [sort, setSort] = useState<"created_at_desc" | "created_at_asc" | "access_count_desc" | "access_count_asc">("created_at_desc");
  const [page, setPage] = useState(1);
  const links = useLinksQuery({
    q: search || undefined,
    is_active: active === "all" ? undefined : active,
    folder_id: folderId || undefined,
    sort,
    limit: 8,
    offset: (page - 1) * 8,
  });
  const folders = useFoldersQuery();
  const createLink = useCreateLinkMutation();
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { mode: "reuse" },
  });

  const totalPages = Math.max(1, Math.ceil((links.data?.total ?? 0) / 8));

  return (
    <div className="space-y-4">
      <Card className="space-y-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="m-0 text-lg font-semibold">Мои ссылки</h1>
            <p className="m-0 text-sm text-subtle">Поиск, фильтры, создание и управление активностью.</p>
          </div>
          <Dialog.Root>
            <Dialog.Trigger asChild>
              <Button>
                <Plus className="h-4 w-4" />
                Новая ссылка
              </Button>
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 bg-black/50" />
              <Dialog.Content className="fixed left-1/2 top-1/2 w-[min(92vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-panel border border-border bg-panel p-6">
                <Dialog.Title className="text-lg font-semibold">Создать ссылку</Dialog.Title>
                <form
                  className="mt-5 space-y-4"
                  onSubmit={form.handleSubmit(async (values) => {
                    await createLink.mutateAsync({
                      ...values,
                      folder_id: values.folder_id ? Number(values.folder_id) : undefined,
                    });
                  })}
                >
                  <Input placeholder="https://example.com" {...form.register("url")} />
                  <Input placeholder="Label" {...form.register("label")} />
                  <Select.Root defaultValue="reuse" onValueChange={(value) => form.setValue("mode", value as "reuse" | "new")}>
                    <Select.Trigger className="flex h-10 w-full items-center justify-between rounded-panel border border-border bg-panel px-3 text-left">
                      <Select.Value placeholder="Mode" />
                      <ChevronDown className="h-4 w-4 text-subtle" />
                    </Select.Trigger>
                    <Select.Portal>
                      <Select.Content className="rounded-panel border border-border bg-panel p-1">
                        <Select.Item value="reuse" className="flex cursor-pointer items-center gap-2 rounded-panel px-3 py-2">
                          <Select.ItemText>Reuse existing</Select.ItemText>
                        </Select.Item>
                        <Select.Item value="new" className="flex cursor-pointer items-center gap-2 rounded-panel px-3 py-2">
                          <Select.ItemText>Create new</Select.ItemText>
                        </Select.Item>
                      </Select.Content>
                    </Select.Portal>
                  </Select.Root>
                  <select
                    className="h-10 w-full rounded-panel border border-border bg-panel px-3"
                    {...form.register("folder_id")}
                  >
                    <option value="">Без папки</option>
                    {folders.data?.map((folder) => (
                      <option key={folder.id} value={folder.id}>
                        {folder.name}
                      </option>
                    ))}
                  </select>
                  <Button type="submit" className="w-full">
                    Создать
                  </Button>
                </form>
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        </div>
        <div className="grid gap-3 md:grid-cols-4">
          <Input placeholder="Поиск по ссылкам..." value={search} onChange={(event) => setSearch(event.target.value)} />
          <select className="h-10 rounded-panel border border-border bg-panel px-3" value={active} onChange={(event) => setActive(event.target.value)}>
            <option value="all">Все</option>
            <option value="true">Активные</option>
            <option value="false">Отключённые</option>
          </select>
          <select className="h-10 rounded-panel border border-border bg-panel px-3" value={folderId} onChange={(event) => setFolderId(event.target.value)}>
            <option value="">Все папки</option>
            {folders.data?.map((folder) => (
              <option key={folder.id} value={folder.id}>
                {folder.name}
              </option>
            ))}
          </select>
          <select className="h-10 rounded-panel border border-border bg-panel px-3" value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}>
            <option value="created_at_desc">Сначала новые</option>
            <option value="created_at_asc">Сначала старые</option>
            <option value="access_count_desc">По кликам</option>
            <option value="access_count_asc">По кликам: сначала меньше</option>
          </select>
        </div>
      </Card>
      {links.isLoading ? <StatusMessage type="loading" message="Загружаем ссылки…" /> : null}
      {links.error ? <StatusMessage type="error" message={links.error.message} /> : null}
      {!links.isLoading && !links.error && !links.data?.items.length ? (
        <EmptyState title="Ссылок пока нет" description="Создайте первую ссылку или ослабьте фильтры." />
      ) : null}
      <div className="grid gap-3">
        {links.data?.items.map((item) => (
          <LinkRow key={item.shortcode} item={item} />
        ))}
      </div>
      <Card className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {Array.from({ length: totalPages }, (_, index) => index + 1).map((value) => (
            <Button key={value} variant={value === page ? "primary" : "secondary"} size="sm" onClick={() => setPage(value)}>
              {value}
            </Button>
          ))}
        </div>
        <p className="m-0 text-sm text-subtle">
          {(links.data?.offset ?? 0) + 1}–{Math.min((links.data?.offset ?? 0) + 8, links.data?.total ?? 0)} из {links.data?.total ?? 0}
        </p>
      </Card>
    </div>
  );
}

function LinkRow({ item }: { item: {
  shortcode: string;
  short_url: string;
  label?: string | null;
  url: string;
  access_count: number;
  created_at: string;
  is_active: boolean;
  folder_id: number | null;
} }) {
  const mutation = useUpdateLinkMutation(item.shortcode);
  const [label, setLabel] = useState(item.label ?? "");

  return (
    <Card className="grid gap-4 md:grid-cols-[minmax(0,1fr)_120px_160px_120px] md:items-center">
      <div className="min-w-0 space-y-1">
        <button type="button" className="block truncate text-left font-medium text-accent" onClick={() => void copyToClipboard(item.short_url)}>
          {item.shortcode}
        </button>
        <Input value={label} onChange={(event) => setLabel(event.target.value)} onBlur={() => mutation.mutate({ label })} />
        <p className="m-0 truncate text-xs text-subtle">{item.url}</p>
      </div>
      <div className="text-sm text-subtle">{item.access_count} переходов</div>
      <div className="text-sm text-subtle">{formatDate(item.created_at)}</div>
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-subtle">{item.folder_id ? `Папка #${item.folder_id}` : "Без папки"}</span>
        <Switch.Root
          checked={item.is_active}
          onCheckedChange={(checked) => mutation.mutate({ is_active: checked })}
          className="relative h-6 w-11 rounded-full bg-border data-[state=checked]:bg-accent"
        >
          <Switch.Thumb className="block h-5 w-5 translate-x-0.5 rounded-full bg-white transition data-[state=checked]:translate-x-[22px]" />
        </Switch.Root>
      </div>
    </Card>
  );
}
