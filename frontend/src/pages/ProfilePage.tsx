import * as Avatar from "@radix-ui/react-avatar";
import { zodResolver } from "@hookform/resolvers/zod";
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
            <Avatar.Root className="flex h-20 w-20 items-center justify-center rounded-full bg-accent/10 text-xl font-semibold text-accent">
              <Avatar.Image src={user.avatar_url ?? undefined} alt={user.display_name ?? user.email} className="h-full w-full rounded-full object-cover" />
              <Avatar.Fallback>{getInitials(user.display_name ?? user.email)}</Avatar.Fallback>
            </Avatar.Root>
            <label className="block">
              <span className="mb-2 block text-xs text-subtle">Avatar</span>
              <Input
                type="file"
                accept="image/*"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void uploadAvatar.mutateAsync(file);
                }}
              />
            </label>
            <Button variant="secondary" onClick={() => void deleteAvatar.mutateAsync()}>
              Удалить avatar
            </Button>
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
