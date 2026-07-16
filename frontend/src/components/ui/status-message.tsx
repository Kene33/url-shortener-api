import { AlertCircle, CheckCircle2, LoaderCircle } from "lucide-react";

export function StatusMessage({
  type,
  message,
}: {
  type: "loading" | "error" | "success";
  message: string;
}) {
  const icon =
    type === "loading" ? (
      <LoaderCircle className="h-4 w-4 animate-spin" />
    ) : type === "error" ? (
      <AlertCircle className="h-4 w-4" />
    ) : (
      <CheckCircle2 className="h-4 w-4" />
    );

  return (
    <div
      aria-live="polite"
      className="flex items-center gap-2 rounded-panel border border-border bg-muted px-3 py-2 text-sm text-subtle"
    >
      {icon}
      <span>{message}</span>
    </div>
  );
}
