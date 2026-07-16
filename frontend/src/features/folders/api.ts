import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { FolderColor } from "@/api/types";

export const foldersKeys = {
  all: ["folders"] as const,
};

export function useFoldersQuery() {
  return useQuery({
    queryKey: foldersKeys.all,
    queryFn: api.getFolders,
  });
}

export function useCreateFolderMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createFolder,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: foldersKeys.all }),
  });
}

export function useRenameFolderMutation(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; color: FolderColor }) => api.updateFolder(id, payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: foldersKeys.all }),
  });
}

export function useDeleteFolderMutation(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.deleteFolder(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: foldersKeys.all }),
  });
}
