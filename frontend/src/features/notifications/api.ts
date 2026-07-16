import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

export const notificationsKeys = {
  all: ["notifications"] as const,
};

export function useNotificationsQuery() {
  return useQuery({
    queryKey: notificationsKeys.all,
    queryFn: api.getNotifications,
  });
}

export function useReadNotificationMutation(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.readNotification(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: notificationsKeys.all }),
  });
}

export function useReadAllNotificationsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.readAllNotifications,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: notificationsKeys.all }),
  });
}
