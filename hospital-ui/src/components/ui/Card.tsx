import React from "react";
import clsx from "clsx";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "elevated" | "bordered";
}

export const Card: React.FC<CardProps> = ({
  children,
  className,
  variant = "default",
  ...props
}) => {
  const variantStyles = {
    default: "bg-slate-900 border border-slate-800",
    elevated: "bg-slate-900/90 shadow-xl border border-slate-800 backdrop-blur-sm",
    bordered: "bg-transparent border border-slate-800",
  };

  return (
    <div className={clsx("rounded-lg p-4 text-slate-100", variantStyles[variant], className)} {...props}>
      {children}
    </div>
  );
};

