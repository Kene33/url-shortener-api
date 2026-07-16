import { useMutation } from "@tanstack/react-query";
import { api } from "@/api/client";

export function useChangePasswordMutation() {
  return useMutation({
    mutationFn: api.changePassword,
  });
}

export function useExportDataMutation() {
  return useMutation({
    mutationFn: api.exportData,
  });
}

export function useDeleteAccountMutation() {
  return useMutation({
    mutationFn: api.deleteAccount,
  });
}
