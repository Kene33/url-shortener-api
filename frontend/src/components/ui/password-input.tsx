import { Eye, EyeOff } from "lucide-react";
import { useState, type InputHTMLAttributes } from "react";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";

type PasswordInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type">;

export function PasswordInput({ className, ...props }: PasswordInputProps) {
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);

  return (
    <div className="relative">
      <Input className={`pr-11 ${className ?? ""}`} type={visible ? "text" : "password"} {...props} />
      <button
        type="button"
        className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-subtle transition hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        aria-label={visible ? t("auth.hidePassword") : t("auth.showPassword")}
        title={visible ? t("auth.hidePassword") : t("auth.showPassword")}
        onClick={() => setVisible((current) => !current)}
      >
        {visible ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
      </button>
    </div>
  );
}
