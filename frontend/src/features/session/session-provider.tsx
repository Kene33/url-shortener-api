import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, configureApiAuth, ApiError } from "@/api/client";
import type {
  ActionMessageResponse,
  Preferences,
  SessionResponse,
  TwoFactorChallengeResponse,
  User,
} from "@/api/types";
import { useTheme } from "@/features/theme/theme-provider";
import i18n from "@/i18n";

interface SessionContextValue {
  user: User | null;
  accessToken: string | null;
  isBootstrapping: boolean;
  login: (payload: { email: string; password: string }) => Promise<void | TwoFactorChallengeResponse>;
  verifyTwoFactor: (payload: { login_token: string; code: string }) => Promise<void>;
  logout: () => Promise<ActionMessageResponse>;
  preferences: Preferences | null;
  setSessionFromResponse: (response: SessionResponse) => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

function normalizePreferences(source?: Partial<Preferences> | null): Preferences {
  return {
    theme: source?.theme ?? "light",
    language: source?.language ?? "ru",
    email_notifications: source?.email_notifications ?? true,
    system_notifications: source?.system_notifications ?? true,
    created_at: source?.created_at ?? "",
    updated_at: source?.updated_at ?? "",
  };
}

function isSessionResponse(
  response: SessionResponse | TwoFactorChallengeResponse,
): response is SessionResponse {
  return "access_token" in response;
}

export function SessionProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const { setLanguage, setTheme } = useTheme();
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [preferences, setPreferences] = useState<Preferences | null>(null);

  const setSessionFromResponse = (response: SessionResponse) => {
    setAccessToken(response.access_token);
    setUser(response.user);
  };

  useEffect(() => {
    configureApiAuth({
      getToken: () => accessToken,
      setToken: setAccessToken,
      refresh: async () => {
        try {
          const response = await api.refresh();
          setSessionFromResponse(response);
          return response.access_token;
        } catch {
          setAccessToken(null);
          setUser(null);
          setPreferences(null);
          return null;
        }
      },
    });
  }, [accessToken]);

  const bootstrap = useQuery({
    queryKey: ["session", "bootstrap"],
    queryFn: async () => {
      const response = await api.refresh();
      setSessionFromResponse(response);
      return response;
    },
    retry: false,
  });

  const profileQuery = useQuery({
    queryKey: ["session", "profile", user?.id],
    queryFn: api.getProfile,
    enabled: !!accessToken,
    retry: false,
  });

  useEffect(() => {
    if (profileQuery.data) {
      const next = normalizePreferences(profileQuery.data.preferences);
      setPreferences(next);
      setLanguage(next.language);
      setTheme(next.theme);
      void i18n.changeLanguage(next.language);
      setUser(profileQuery.data.user);
    }
  }, [profileQuery.data, setLanguage, setTheme]);

  const loginMutation = useMutation({
    mutationFn: api.login,
  });

  const verifyMutation = useMutation({
    mutationFn: api.loginWithTwoFactor,
    onSuccess: setSessionFromResponse,
  });

  const logoutMutation = useMutation({
    mutationFn: api.logout,
    onSettled: () => {
      setAccessToken(null);
      setUser(null);
      setPreferences(null);
      void queryClient.invalidateQueries();
    },
  });

  const value = useMemo<SessionContextValue>(
    () => ({
      user,
      accessToken,
      isBootstrapping: bootstrap.isLoading,
      preferences,
      setSessionFromResponse,
      login: async (payload) => {
        const response = await loginMutation.mutateAsync(payload);
        if ("requires_two_factor" in response && response.requires_two_factor) {
          return response;
        }
        if (isSessionResponse(response)) {
          setSessionFromResponse(response);
        }
        return undefined;
      },
      verifyTwoFactor: async (payload) => {
        await verifyMutation.mutateAsync(payload);
      },
      logout: () => logoutMutation.mutateAsync(),
    }),
    [
      accessToken,
      bootstrap.isLoading,
      loginMutation,
      logoutMutation,
      preferences,
      user,
      verifyMutation,
    ],
  );

  if (bootstrap.error && bootstrap.error instanceof ApiError && bootstrap.error.status !== 401) {
    console.error(bootstrap.error);
  }

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used within SessionProvider");
  return value;
}
