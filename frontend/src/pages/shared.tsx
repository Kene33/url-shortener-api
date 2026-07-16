import { Link } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Logo } from "@/components/app/logo";
import { ThemeLanguageControls } from "@/components/app/theme-language-controls";

export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="page-shell flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-[440px] space-y-4">
        <div className="flex items-center justify-between">
          <Logo />
          <ThemeLanguageControls />
        </div>
        <Card className="space-y-5 p-6">
          <div>
            <h1 className="m-0 text-2xl font-semibold">{title}</h1>
            <p className="m-0 mt-2 text-sm text-subtle">{subtitle}</p>
          </div>
          {children}
          {footer ? <div className="text-sm text-subtle">{footer}</div> : null}
        </Card>
      </div>
    </div>
  );
}

export function AuthFooter({
  question,
  action,
  to,
}: {
  question: string;
  action: string;
  to: string;
}) {
  return (
    <p className="m-0 text-sm text-subtle">
      {question}{" "}
      <Link to={to} className="font-medium text-accent">
        {action}
      </Link>
    </p>
  );
}
