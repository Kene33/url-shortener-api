import * as Avatar from "@radix-ui/react-avatar";
import { zodResolver } from "@hookform/resolvers/zod";
import { ImagePlus, Loader2, Trash2 } from "lucide-react";
import { useRef } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusMessage } from "@/components/ui/status-message";
import { useDeleteAvatarMutation, useProfileQuery, useUpdateProfileMutation, useUploadAvatarMutation } from "@/features/profile/api";
import { formatDate, getInitials } from "@/lib/utils";

const schema = z.object({
  display_name: z.string().min(1),
  email: z.email(),
});

export function ProfilePage() {
  const profile = useProfileQuery();
  const updateProfile = useUpdateProfileMutation();
  const uploadAvatar = useUploadAvatarMutation();
  const deleteAvatar = useDeleteAvatarMutation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    values: {
      display_name: profile.data?.user.display_name ?? "",
      email: profile.data?.user.email ?? "",
    },
  });

  if (profile.isLoading) return <StatusMessage type="loading" message="Загружаем профиль…" />;
  if (profile.error) return <StatusMessage type="error" message={profile.error.message} />;
  if (!profile.data) return null;

  const { user } = profile.data;
  return (
    <div className="space-y-4">
      <Card className="space-y-5">
        <h1 className="m-0 text-lg font-semibold">Профиль</h1>
        <div className="grid gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
          <div className="space-y-3">
            <Avatar.Root className="flex h-24 w-24 items-center justify-center rounded-full bg-accent/10 text-xl font-semibold text-accent ring-4 ring-accent/10">
              <Avatar.Image src={user.avatar_url ?? undefined} alt={user.display_name ?? user.email} className="h-full w-full rounded-full object-cover" />
              <Avatar.Fallback>{getInitials(user.display_name ?? user.email)}</Avatar.Fallback>
            </Avatar.Root>
            <input
              ref={fileInputRef}
              className="sr-only"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void uploadAvatar.mutateAsync(file);
                event.target.value = "";
              }}
            />
            <div className="space-y-2">
              <p className="m-0 text-xs text-subtle">PNG, JPG или WebP до 2 МБ</p>
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" onClick={() => fileInputRef.current?.click()} disabled={uploadAvatar.isPending}>
                  {uploadAvatar.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ImagePlus className="h-4 w-4" />}
                  {uploadAvatar.isPending ? "Загрузка…" : "Выбрать фото"}
                </Button>
                {user.avatar_url && (
                  <Button type="button" variant="secondary" size="sm" onClick={() => void deleteAvatar.mutateAsync()} disabled={deleteAvatar.isPending}>
                    {deleteAvatar.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                    Удалить
                  </Button>
                )}
              </div>
            </div>
          </div>
          <form
            className="space-y-4"
            onSubmit={form.handleSubmit(async (values) => {
              await updateProfile.mutateAsync(values);
            })}
          >
            <Input placeholder="Display name" {...form.register("display_name")} />
            <Input placeholder="Email" type="email" {...form.register("email")} />
            <Button type="submit">Сохранить профиль</Button>
          </form>
        </div>
      </Card>
      <Card className="grid gap-3 md:grid-cols-2">
        {[
          ["Статус", user.is_active ? "active" : "disabled"],
          ["Роль", user.is_admin ? "admin" : "user"],
          ["Дата регистрации", formatDate(user.created_at)],
          ["Ожидающий email", user.pending_email ?? "—"],
        ].map(([label, value]) => (
          <div key={String(label)} className="panel-soft p-4">
            <p className="m-0 text-xs text-subtle">{label}</p>
            <p className="m-0 mt-2 text-sm">{value}</p>
          </div>
        ))}
      </Card>
    </div>
  );
}
