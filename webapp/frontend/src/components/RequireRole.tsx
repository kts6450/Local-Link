import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { roleMatches, useAuthRole } from "../store/auth";

export function RequireRole({
  role,
  children,
}: {
  role: "consumer" | "seller";
  children: ReactNode;
}) {
  const current = useAuthRole();
  const location = useLocation();

  if (!current) {
    return (
      <Navigate
        to={`/login?role=${role}`}
        replace
        state={{ from: location.pathname }}
      />
    );
  }

  if (!roleMatches(current, role)) {
    const dest =
      current === "master"
        ? "/seller/products"
        : current === "seller"
          ? "/seller/dashboard"
          : "/";
    return <Navigate to={dest} replace />;
  }

  return <>{children}</>;
}
