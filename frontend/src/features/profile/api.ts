import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

export const profileKeys = {
  all: ["profile"] as const,
};

export function useProfileQuery(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: profileKeys.all,
    queryFn: api.getProfile,
    enabled: options?.enabled ?? true,
  });
}

export function useUpdateProfileMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.updateProfile,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profileKeys.all }),
        queryClient.invalidateQueries({ queryKey: ["session", "profile"] }),
      ]);
    },
  });
}

export function useUploadAvatarMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.uploadAvatar,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profileKeys.all }),
        queryClient.invalidateQueries({ queryKey: ["session", "profile"] }),
      ]);
    },
  });
}

export function useDeleteAvatarMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.deleteAvatar,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: profileKeys.all }),
        queryClient.invalidateQueries({ queryKey: ["session", "profile"] }),
      ]);
    },
  });
}
