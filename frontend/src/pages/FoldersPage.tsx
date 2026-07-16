import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { StatusMessage } from "@/components/ui/status-message";
import { useCreateFolderMutation, useDeleteFolderMutation, useFoldersQuery, useRenameFolderMutation } from "@/features/folders/api";
import type { Folder, FolderColor } from "@/api/types";

const folderColors: FolderColor[] = ["blue", "cyan", "violet", "orange", "red", "green", "gray"];
const colorClass: Record<FolderColor, string> = {
  blue: "bg-sky-500", cyan: "bg-cyan-500", violet: "bg-violet-500", orange: "bg-orange-500",
  red: "bg-red-500", green: "bg-emerald-500", gray: "bg-slate-500",
};

const schema = z.object({
  name: z.string().min(1),
  color: z.enum(["blue", "cyan", "violet", "orange", "red", "green", "gray"]),
});

export function FoldersPage() {
  const [editingId, setEditingId] = useState<number | null>(null);
  const folders = useFoldersQuery();
  const createFolder = useCreateFolderMutation();
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { color: "violet" },
  });

  return (
    <div className="space-y-4">
      <Card className="space-y-4">
        <div>
          <h1 className="m-0 text-lg font-semibold">Папки</h1>
          <p className="m-0 text-sm text-subtle">Создание, переименование, удаление и цветовая группировка ссылок.</p>
        </div>
        <form
          className="grid gap-3 md:grid-cols-[minmax(0,1fr)_120px_140px]"
          onSubmit={form.handleSubmit(async (values) => {
            await createFolder.mutateAsync(values);
            form.reset({ name: "", color: "violet" });
          })}
        >
          <Input placeholder="Новая папка" {...form.register("name")} />
          <select className="h-10 rounded-panel border border-border bg-panel px-3" {...form.register("color")}>
            {folderColors.map((color) => <option key={color} value={color}>{color}</option>)}
          </select>
          <Button type="submit">Создать</Button>
        </form>
      </Card>
      {folders.isLoading ? <StatusMessage type="loading" message="Загружаем папки…" /> : null}
      {folders.error ? <StatusMessage type="error" message={folders.error.message} /> : null}
      {!folders.isLoading && !folders.data?.length ? (
        <EmptyState title="Папок пока нет" description="Создайте первую папку для организации ссылок." />
      ) : null}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {folders.data?.map((folder) => (
          <FolderCard key={folder.id} folder={folder} editingId={editingId} onEdit={setEditingId} />
        ))}
      </div>
    </div>
  );
}

function FolderCard({
  folder,
  editingId,
  onEdit,
}: {
  folder: Folder;
  editingId: number | null;
  onEdit: (id: number | null) => void;
}) {
  const renameFolder = useRenameFolderMutation(folder.id);
  const deleteFolder = useDeleteFolderMutation(folder.id);
  const form = useForm<{ name: string; color: FolderColor }>({
    resolver: zodResolver(z.object({ name: z.string().min(1), color: z.enum(["blue", "cyan", "violet", "orange", "red", "green", "gray"]) })),
    defaultValues: { name: folder.name, color: folder.color },
  });
  const editing = editingId === folder.id;

  return (
    <Card className="space-y-4">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <span className={`h-10 w-10 rounded-panel ${colorClass[folder.color]}`} />
          <div>
            <p className="m-0 font-semibold">{folder.name}</p>
            <p className="m-0 text-sm text-subtle">{folder.link_count} ссылок</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={() => onEdit(editing ? null : folder.id)}>
          {editing ? "Закрыть" : "Изменить"}
        </Button>
      </div>
      {editing ? (
        <form
          className="space-y-3"
          onSubmit={form.handleSubmit(async (values) => {
            await renameFolder.mutateAsync(values);
            onEdit(null);
          })}
        >
          <Input {...form.register("name")} />
          <select className="h-10 rounded-panel border border-border bg-panel px-3" {...form.register("color")}>
            {folderColors.map((color) => <option key={color} value={color}>{color}</option>)}
          </select>
          <div className="flex gap-2">
            <Button type="submit">Сохранить</Button>
            <AlertDialog.Root>
              <AlertDialog.Trigger asChild>
                <Button variant="danger" type="button">
                  Удалить
                </Button>
              </AlertDialog.Trigger>
              <AlertDialog.Portal>
                <AlertDialog.Overlay className="fixed inset-0 bg-black/50" />
                <AlertDialog.Content className="fixed left-1/2 top-1/2 w-[min(92vw,420px)] -translate-x-1/2 -translate-y-1/2 rounded-panel border border-border bg-panel p-6">
                  <AlertDialog.Title className="text-lg font-semibold">Удалить папку?</AlertDialog.Title>
                  <AlertDialog.Description className="mt-2 text-sm text-subtle">
                    Ссылки останутся, но папка будет удалена.
                  </AlertDialog.Description>
                  <div className="mt-5 flex gap-2">
                    <AlertDialog.Cancel asChild>
                      <Button variant="secondary" type="button">
                        Отмена
                      </Button>
                    </AlertDialog.Cancel>
                    <AlertDialog.Action asChild>
                      <Button variant="danger" type="button" onClick={() => void deleteFolder.mutateAsync()}>
                        Удалить
                      </Button>
                    </AlertDialog.Action>
                  </div>
                </AlertDialog.Content>
              </AlertDialog.Portal>
            </AlertDialog.Root>
          </div>
        </form>
      ) : null}
    </Card>
  );
}
