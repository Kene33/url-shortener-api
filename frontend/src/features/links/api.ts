import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { CreateLinkPayload, LinkSort, UpdateLinkPayload } from "@/api/types";

export const linksKeys = {
  all: ["links"] as const,
  list: (params: string) => ["links", "list", params] as const,
};

export function useLinksQuery(params: {
  q?: string;
  is_active?: string;
  folder_id?: string;
  sort: LinkSort;
  limit: number;
  offset: number;
}) {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.is_active) search.set("is_active", params.is_active);
  if (params.folder_id) search.set("folder_id", params.folder_id);
  search.set("sort", params.sort);
  search.set("limit", String(params.limit));
  search.set("offset", String(params.offset));

  return useQuery({
    queryKey: linksKeys.list(search.toString()),
    queryFn: () => api.getLinks(search),
  });
}

export function useCreateLinkMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateLinkPayload) => api.createLink(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: linksKeys.all });
    },
  });
}

export function useUpdateLinkMutation(shortcode: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UpdateLinkPayload) => api.updateLink(shortcode, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: linksKeys.all });
    },
  });
}
