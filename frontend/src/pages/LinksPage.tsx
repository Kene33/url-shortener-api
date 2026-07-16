import * as AlertDialog from "@radix-ui/react-alert-dialog";
import * as Dialog from "@radix-ui/react-dialog";
import * as Switch from "@radix-ui/react-switch";
import { zodResolver } from "@hookform/resolvers/zod";
import { Check, Copy, Pencil, Plus, Power, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { CreateLinkPayload, LinkItem } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { StatusMessage } from "@/components/ui/status-message";
import { useFoldersQuery } from "@/features/folders/api";
import { useCreateLinkMutation, useLinksQuery, useUpdateLinkMutation } from "@/features/links/api";
import { copyToClipboard, formatDate } from "@/lib/utils";

const schema = z.object({
  url: z.string().min(1),
  label: z.string().optional(),
  folder_id: z.string().optional(),
});

type DraftLink = CreateLinkPayload;

export function LinksPage() {
  const [search, setSearch] = useState("");
  const [active, setActive] = useState("all");
  const [folderId, setFolderId] = useState("");
  const [sort, setSort] = useState<"created_at_desc" | "created_at_asc" | "access_count_desc" | "access_count_asc">("created_at_desc");
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [duplicate, setDuplicate] = useState<{ draft: DraftLink; shortcode: string; label: string | null; folderId: number | null } | null>(null);
  const [copied, setCopied] = useState(false);
  const links = useLinksQuery({ q: search || undefined, is_active: active === "all" ? undefined : active, folder_id: folderId || undefined, sort, limit: 8, offset: (page - 1) * 8 });
  const folders = useFoldersQuery();
  const createLink = useCreateLinkMutation();
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const folderNames = useMemo(() => new Map((folders.data ?? []).map((folder) => [folder.id, folder.name])), [folders.data]);
  const totalPages = Math.max(1, Math.ceil((links.data?.total ?? 0) / 8));

  const createOrConfirm = async (values: z.infer<typeof schema>) => {
    const draft: DraftLink = { url: values.url, label: values.label || undefined, folder_id: values.folder_id ? Number(values.folder_id) : undefined, mode: "reuse" };
    const result = await createLink.mutateAsync(draft);
    if (result.created) {
      setCreateOpen(false);
      form.reset();
      return;
    }
    setDuplicate({ draft, shortcode: result.shortcode, label: result.label ?? null, folderId: result.folder_id ?? null });
  };

  return (
    <div className="space-y-4">
      <Card className="space-y-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"><div><h1 className="m-0 text-lg font-semibold">Мои ссылки</h1><p className="m-0 text-sm text-subtle">Поиск, папки, статистика и безопасное управление активностью.</p></div>
          <Dialog.Root open={createOpen} onOpenChange={setCreateOpen}><Dialog.Trigger asChild><Button><Plus className="h-4 w-4" />Новая ссылка</Button></Dialog.Trigger><Dialog.Portal><Dialog.Overlay className="fixed inset-0 bg-black/50" /><Dialog.Content className="fixed left-1/2 top-1/2 w-[min(92vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-panel border border-border bg-panel p-6"><Dialog.Title className="text-lg font-semibold">Создать ссылку</Dialog.Title><p className="mt-1 text-sm text-subtle">Выберите папку сейчас или оставьте ссылку без папки.</p><form className="mt-5 space-y-4" onSubmit={form.handleSubmit((values) => void createOrConfirm(values))}><Input placeholder="https://example.com" {...form.register("url")} /><Input placeholder="Название, например Реклама у блогера A" {...form.register("label")} /><label className="grid gap-1 text-xs text-subtle">Папка<select className="h-10 rounded-panel border border-border bg-panel px-3 text-text" {...form.register("folder_id")}><option value="">Без папки</option>{folders.data?.map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}</select></label><Button type="submit" className="w-full" disabled={createLink.isPending}>Проверить и создать</Button></form>{createLink.error ? <StatusMessage type="error" message={createLink.error.message} /> : null}</Dialog.Content></Dialog.Portal></Dialog.Root>
        </div>
        <div className="grid gap-3 md:grid-cols-4"><Input placeholder="Поиск по ссылкам..." value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} /><select className="h-10 rounded-panel border border-border bg-panel px-3 text-text" value={active} onChange={(event) => setActive(event.target.value)}><option value="all">Все</option><option value="true">Активные</option><option value="false">Отключённые</option></select><select className="h-10 rounded-panel border border-border bg-panel px-3 text-text" value={folderId} onChange={(event) => setFolderId(event.target.value)}><option value="">Все папки</option>{folders.data?.map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}</select><select className="h-10 rounded-panel border border-border bg-panel px-3 text-text" value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}><option value="created_at_desc">Сначала новые</option><option value="created_at_asc">Сначала старые</option><option value="access_count_desc">По кликам</option><option value="access_count_asc">По кликам: сначала меньше</option></select></div>
      </Card>
      {links.isLoading ? <StatusMessage type="loading" message="Загружаем ссылки…" /> : null}{links.error ? <StatusMessage type="error" message={links.error.message} /> : null}
      {!links.isLoading && !links.error && !links.data?.items.length ? <EmptyState title="Ссылок пока нет" description="Создайте первую ссылку или ослабьте фильтры." /> : null}
      <div className="grid gap-3">{links.data?.items.map((item) => <LinkRow key={item.shortcode} item={item} folders={folders.data ?? []} onCopied={() => setCopied(true)} />)}</div>
      <Card className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2">{Array.from({ length: totalPages }, (_, index) => index + 1).map((value) => <Button key={value} variant={value === page ? "primary" : "secondary"} size="sm" onClick={() => setPage(value)}>{value}</Button>)}</div><p className="m-0 text-sm text-subtle">{(links.data?.offset ?? 0) + 1}–{Math.min((links.data?.offset ?? 0) + 8, links.data?.total ?? 0)} из {links.data?.total ?? 0}</p></Card>
      <AlertDialog.Root open={Boolean(duplicate)} onOpenChange={(open) => { if (!open) setDuplicate(null); }}><AlertDialog.Portal><AlertDialog.Overlay className="fixed inset-0 bg-black/50" /><AlertDialog.Content className="fixed left-1/2 top-1/2 w-[min(92vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-panel border border-border bg-panel p-6"><AlertDialog.Title className="text-lg font-semibold">Такая ссылка уже есть</AlertDialog.Title><AlertDialog.Description className="mt-2 text-sm text-subtle">Код <span className="font-medium text-text">{duplicate?.shortcode}</span>{duplicate?.label ? `, «${duplicate.label}»` : ""}{duplicate?.folderId ? `, папка «${folderNames.get(duplicate.folderId) ?? `#${duplicate.folderId}`}»` : ", без папки"}. Выберите, продолжать ли эту статистику или создать отдельную кампанию.</AlertDialog.Description><div className="mt-5 flex flex-col gap-2 sm:flex-row"><AlertDialog.Cancel asChild><Button variant="secondary" onClick={() => { setCreateOpen(false); form.reset(); }}>Использовать существующую</Button></AlertDialog.Cancel><Button onClick={() => { if (duplicate) void createLink.mutateAsync({ ...duplicate.draft, mode: "new" }).then(() => { setDuplicate(null); setCreateOpen(false); form.reset(); }); }}>Создать отдельную</Button></div></AlertDialog.Content></AlertDialog.Portal></AlertDialog.Root>
      {copied ? <CopyToast onClose={() => setCopied(false)} /> : null}
    </div>
  );
}

function LinkRow({ item, folders, onCopied }: { item: LinkItem; folders: Array<{ id: number; name: string }>; onCopied: () => void }) {
  const mutation = useUpdateLinkMutation(item.shortcode);
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(item.label ?? "");
  const [folderId, setFolderId] = useState(item.folder_id?.toString() ?? "");
  const folderName = folders.find((folder) => folder.id === item.folder_id)?.name ?? "Без папки";
  const save = () => { void mutation.mutateAsync({ label, folder_id: folderId ? Number(folderId) : null }).then(() => setEditing(false)); };
  const copyLink = () => void copyToClipboard(item.short_url).then(onCopied);
  return <Card className="grid gap-4 md:grid-cols-[minmax(0,1fr)_110px_150px_190px] md:items-center"><div className="min-w-0 space-y-1"><button type="button" className="block max-w-full truncate font-medium text-accent hover:underline" title={`Копировать ${item.short_url}`} onClick={copyLink}>{item.shortcode}</button>{editing ? <><Input value={label} onChange={(event) => setLabel(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") save(); }} /><select className="h-9 w-full rounded-panel border border-border bg-panel px-2 text-sm text-text" value={folderId} onChange={(event) => setFolderId(event.target.value)}><option value="">Без папки</option>{folders.map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}</select></> : <p className="m-0 text-sm">{item.label || "Без названия"}</p>}<p className="m-0 truncate text-xs text-subtle">{item.url}</p></div><div className="text-sm text-subtle">{item.access_count} переходов</div><div className="text-sm text-subtle">{formatDate(item.created_at)}<br />{folderName}</div><div className="flex items-center justify-end gap-1"><button className="pill" type="button" title="Копировать короткую ссылку" aria-label="Копировать короткую ссылку" onClick={copyLink}><Copy className="h-4 w-4" /></button><button className="pill" type="button" title={editing ? "Сохранить" : "Редактировать название и папку"} aria-label={editing ? "Сохранить" : "Редактировать название и папку"} onClick={editing ? save : () => setEditing(true)}>{editing ? <Check className="h-4 w-4" /> : <Pencil className="h-4 w-4" />}</button><AlertDialog.Root><AlertDialog.Trigger asChild><button className="pill text-danger" type="button" title="Удалить ссылку" aria-label="Удалить ссылку"><Trash2 className="h-4 w-4" /></button></AlertDialog.Trigger><AlertDialog.Portal><AlertDialog.Overlay className="fixed inset-0 bg-black/50" /><AlertDialog.Content className="fixed left-1/2 top-1/2 w-[min(92vw,400px)] -translate-x-1/2 -translate-y-1/2 rounded-panel border border-border bg-panel p-6"><AlertDialog.Title className="text-lg font-semibold">Удалить ссылку?</AlertDialog.Title><AlertDialog.Description className="mt-2 text-sm text-subtle">Ссылка будет отключена и начнёт отвечать 410. URL и shortcode сохранятся и повторно использоваться не будут.</AlertDialog.Description><div className="mt-5 flex gap-2"><AlertDialog.Cancel asChild><Button variant="secondary">Отмена</Button></AlertDialog.Cancel><AlertDialog.Action asChild><Button variant="danger" onClick={() => void mutation.mutateAsync({ is_active: false })}>Удалить</Button></AlertDialog.Action></div></AlertDialog.Content></AlertDialog.Portal></AlertDialog.Root><button className="pill" type="button" title={item.is_active ? "Отключить ссылку" : "Включить ссылку"} aria-label={item.is_active ? "Отключить ссылку" : "Включить ссылку"} onClick={() => void mutation.mutateAsync({ is_active: !item.is_active })}><Power className="h-4 w-4" /></button><Switch.Root checked={item.is_active} onCheckedChange={(checked) => mutation.mutate({ is_active: checked })} aria-label={item.is_active ? "Ссылка включена" : "Ссылка отключена"} className="relative h-6 w-11 rounded-full bg-border data-[state=checked]:bg-accent"><Switch.Thumb className="block h-5 w-5 translate-x-0.5 rounded-full bg-white transition data-[state=checked]:translate-x-[22px]" /></Switch.Root></div></Card>;
}

function CopyToast({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const timeout = window.setTimeout(onClose, 2200);
    return () => window.clearTimeout(timeout);
  }, [onClose]);
  return <div role="status" className="fixed bottom-5 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-panel border border-border bg-panel px-4 py-3 text-sm shadow-panel"><Check className="h-4 w-4 text-success" />Ссылка скопирована</div>;
}
