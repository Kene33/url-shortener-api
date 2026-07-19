import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type {
  AdminLinkUpdatePayload,
  AdminUserUpdatePayload,
  ReportResolvePayload,
  RetentionSettingsUpdatePayload,
  User,
} from "@/api/types";

export const adminKeys = {
  dashboard: ["admin", "dashboard"] as const,
  users: (params: {
    q?: string;
    role?: User["role"];
    is_active?: boolean;
    limit: number;
    offset: number;
  }) => ["admin", "users", params] as const,
  links: (params: { owner_id?: string; is_active?: boolean; limit: number; offset: number }) =>
    ["admin", "links", params] as const,
  reports: (params: { status_filter?: ReportResolvePayload["status"]; category?: AdminLinkUpdatePayload["category"]; limit: number; offset: number }) =>
    ["admin", "reports", params] as const,
  auditLog: (params: {
    actor_id?: string;
    action?: string;
    object_type?: string;
    date_from?: string;
    date_to?: string;
    limit: number;
    offset: number;
  }) => ["admin", "audit-log", params] as const,
  retention: ["admin", "retention"] as const,
};

export function useAdminDashboardQuery(enabled = true) {
  return useQuery({
    queryKey: adminKeys.dashboard,
    queryFn: api.getAdminDashboard,
    enabled,
  });
}

export function useAdminUsersQuery(params: {
  q?: string;
  role?: User["role"];
  is_active?: boolean;
  limit: number;
  offset: number;
}) {
  return useQuery({
    queryKey: adminKeys.users(params),
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
  is_active?: boolean;
  limit: number;
  offset: number;
}) {
  return useQuery({
    queryKey: adminKeys.links(params),
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

export function useAdminReportsQuery(params: {
  status_filter?: ReportResolvePayload["status"];
  category?: AdminLinkUpdatePayload["category"];
  limit: number;
  offset: number;
}) {
  return useQuery({
    queryKey: adminKeys.reports(params),
    queryFn: () => api.getAdminReports(params),
  });
}

export function useUpdateAdminReportMutation(reportId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReportResolvePayload) => api.updateAdminReport(reportId, payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin"] }),
  });
}

export function useAdminAuditLogQuery(params: {
  actor_id?: string;
  action?: string;
  object_type?: string;
  date_from?: string;
  date_to?: string;
  limit: number;
  offset: number;
}) {
  return useQuery({
    queryKey: adminKeys.auditLog(params),
    queryFn: () => api.getAdminAuditLog(params),
  });
}

export function useAdminRetentionSettingsQuery(enabled = true) {
  return useQuery({
    queryKey: adminKeys.retention,
    queryFn: api.getAdminRetentionSettings,
    enabled,
  });
}

export function useUpdateAdminRetentionSettingsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RetentionSettingsUpdatePayload) => api.updateAdminRetentionSettings(payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin"] }),
  });
}
