import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

export const profileKeys = {
  all: ["profile"] as const,
};

export function useProfileQuery() {
  return useQuery({
    queryKey: profileKeys.all,
    queryFn: api.me,
  });
}

export function useUpdateProfileMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.updateProfile,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: profileKeys.all }),
  });
}

export function useUploadAvatarMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.uploadAvatar,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: profileKeys.all }),
  });
}

export function useDeleteAvatarMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.deleteAvatar,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: profileKeys.all }),
  });
}
