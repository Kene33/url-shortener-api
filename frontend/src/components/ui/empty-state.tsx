import { Inbox } from "lucide-react";

export function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="panel-soft flex min-h-52 flex-col items-center justify-center gap-3 p-8 text-center">
      <Inbox className="h-8 w-8 text-subtle" />
      <div>
        <p className="m-0 font-semibold">{title}</p>
        <p className="m-0 text-sm text-subtle">{description}</p>
      </div>
    </div>
  );
}
