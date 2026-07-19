import { render, screen } from "@testing-library/react";
import { MemoryRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/app/app-shell";
import { useSession } from "@/features/session/session-provider";
import { AdminAccessDeniedPage } from "@/pages/AdminAccessDeniedPage";
import type { User } from "@/api/types";

vi.mock("@/features/session/session-provider", () => ({
  useSession: vi.fn(),
}));

vi.mock("@/features/profile/api", () => ({
  useProfileQuery: () => ({ data: null }),
}));

vi.mock("@/components/app/theme-language-controls", () => ({
  ThemeLanguageControls: () => <div data-testid="theme-language-controls" />,
}));

type SessionState = {
  user: User | null;
  isBootstrapping: boolean;
  logout: () => Promise<{ message: string }>;
};

const mockedUseSession = vi.mocked(useSession);

function buildUser(overrides: Partial<User>): User {
  return {
    id: 1,
    email: "member@example.com",
    role: "user",
    is_admin: false,
    is_active: true,
    email_verified: true,
    display_name: "Regular Member",
    avatar_url: null,
    pending_email: null,
    two_factor_enabled: false,
    created_at: "2026-07-19T00:00:00Z",
    updated_at: "2026-07-19T00:00:00Z",
    ...overrides,
  };
}

function setSession(state: Partial<SessionState>) {
  mockedUseSession.mockReturnValue({
    user: null,
    isBootstrapping: false,
    logout: vi.fn(async () => ({ message: "Logged out" })),
    accessToken: null,
    preferences: null,
    login: vi.fn(),
    verifyTwoFactor: vi.fn(),
    setSessionFromResponse: vi.fn(),
    ...state,
  });
}

function ProtectedRoute() {
  const { user, isBootstrapping } = useSession();
  if (isBootstrapping) return <div>Loading session…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

function AdminRoute() {
  const { user } = useSession();
  if (!user || !["support", "moderator", "admin"].includes(user.role)) {
    return <Navigate to="/admin/access-denied" replace />;
  }
  return <Outlet />;
}

function AdminDashboardPage() {
  return (
    <section>
      <h1>Панель админа</h1>
      <p>Следите за пользователями, ссылками и сроком хранения.</p>
    </section>
  );
}

function renderAdminRoutes(initialPath: string) {
  window.history.pushState({}, "", initialPath);
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AppShell>
        <Routes>
          <Route path="/login" element={<div>Введите email и пароль.</div>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/links" element={<div>Мои ссылки</div>} />
            <Route element={<AdminRoute />}>
              <Route path="/admin" element={<AdminDashboardPage />} />
            </Route>
            <Route path="/admin/access-denied" element={<AdminAccessDeniedPage />} />
          </Route>
        </Routes>
      </AppShell>
    </MemoryRouter>,
  );
}

describe("admin route guards", () => {
  it("redirects guests from admin pages to login", async () => {
    setSession({ user: null });

    renderAdminRoutes("/admin");

    expect(await screen.findByText("Введите email и пароль.")).toBeInTheDocument();
  });

  it("shows access denied for authenticated non-admin users", async () => {
    setSession({
      user: buildUser({ id: 7 }),
    });

    renderAdminRoutes("/admin");

    expect(await screen.findByRole("heading", { name: "Нет доступа" })).toBeInTheDocument();
    expect(screen.getByText("Этот раздел доступен только админам.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Открыть мои ссылки" })).toBeInTheDocument();
  });

  it.each([
    { role: "support" as const, is_admin: false, label: "support" },
    { role: "moderator" as const, is_admin: false, label: "moderator" },
    { role: "admin" as const, is_admin: true, label: "admin" },
  ])("renders the admin dashboard for $label staff", async ({ role, is_admin }) => {
    setSession({
      user: buildUser({
        id: 1,
        email: "admin@example.com",
        display_name: "Admin User",
        role,
        is_admin,
      }),
    });

    renderAdminRoutes("/admin");

    expect(await screen.findByRole("heading", { name: "Панель админа" })).toBeInTheDocument();
    expect(screen.getByText("Следите за пользователями, ссылками и сроком хранения.")).toBeInTheDocument();
  });
});
