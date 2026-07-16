import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type {
  AdminLinkUpdatePayload,
  AdminSettingsUpdatePayload,
  AdminUserUpdatePayload,
} from "@/api/types";

export const adminKeys = {
  users: (limit: number, offset: number) => ["admin", "users", limit, offset] as const,
  links: (ownerId: string, isActive: string, limit: number, offset: number) =>
    ["admin", "links", ownerId, isActive, limit, offset] as const,
  settings: ["admin", "settings"] as const,
};

export function useAdminUsersQuery(params: { limit: number; offset: number }) {
  return useQuery({
    queryKey: adminKeys.users(params.limit, params.offset),
    queryFn: () => api.getAdminUsers(params),
  });
}

export function useUpdateAdminUserMutation(userId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AdminUserUpdatePayload) => api.updateAdminUser(userId, payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin"] }),
  });
}

export function useAdminLinksQuery(params: {
  owner_id?: string;
  is_active?: string;
  limit: number;
  offset: number;
}) {
  return useQuery({
    queryKey: adminKeys.links(params.owner_id ?? "", params.is_active ?? "", params.limit, params.offset),
    queryFn: () => api.getAdminLinks(params),
  });
}

export function useUpdateAdminLinkMutation(shortcode: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AdminLinkUpdatePayload) => api.updateAdminLink(shortcode, payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin"] }),
  });
}

export function useAdminSettingsQuery() {
  return useQuery({
    queryKey: adminKeys.settings,
    queryFn: api.getAdminSettings,
  });
}

export function useUpdateAdminSettingsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AdminSettingsUpdatePayload) => api.updateAdminSettings(payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin"] }),
  });
}
