import React from "react";
import clsx from "clsx";

export interface BadgeProps {
  children: React.ReactNode;
  variant?: "neutral" | "success" | "warning" | "danger" | "info" | "purple";
  size?: "sm" | "md";
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = "neutral",
  size = "md",
  className,
}) => {
  const baseStyles = "inline-flex items-center font-medium rounded-full";

  const sizeStyles = {
    sm: "px-2 py-0.5 text-[10px]",
    md: "px-2.5 py-0.5 text-xs",
  };

  const variantStyles = {
    neutral: "bg-slate-800 text-slate-300 border border-slate-700",
    success: "bg-emerald-950/80 text-emerald-400 border border-emerald-800/60",
    warning: "bg-amber-950/80 text-amber-400 border border-amber-800/60",
    danger: "bg-rose-950/80 text-rose-400 border border-rose-800/60",
    info: "bg-sky-950/80 text-sky-400 border border-sky-800/60",
    purple: "bg-purple-950/80 text-purple-400 border border-purple-800/60",
  };

  return (
    <span className={clsx(baseStyles, sizeStyles[size], variantStyles[variant], className)}>
      {children}
    </span>
  );
};

