import { Navigate, Outlet } from "react-router-dom";

import { useAuthRole } from "../store/auth";

/** 쇼핑몰 — 구매자·운영자만. 공급자는 판매 화면으로 보냄. */
export function RequireConsumer() {
  const role = useAuthRole();
  if (role === "seller") {
    return <Navigate to="/seller/dashboard" replace />;
  }
  return <Outlet />;
}
