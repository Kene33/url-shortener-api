import { Link2 } from "lucide-react";
import { Link } from "react-router-dom";

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/10 text-accent">
        <Link2 className="h-4 w-4" />
      </span>
      <span>LinkCut</span>
    </Link>
  );
}
