import type { FulfillmentStatus } from "../types";
import type { OrderFlowType } from "../lib/orderFlow";
import { flowConfig } from "../lib/orderFlow";

const BASE_LABELS: Record<FulfillmentStatus, { label: string; cls: string }> = {
  pending: { label: "결제 대기", cls: "bg-slate-100 text-slate-700" },
  preparing: { label: "준비 중", cls: "bg-amber-100 text-amber-800" },
  shipping: { label: "배송·진행 중", cls: "bg-blue-100 text-blue-800" },
  completed: { label: "완료", cls: "bg-emerald-100 text-emerald-800" },
  cancelled: { label: "취소", cls: "bg-rose-100 text-rose-800" },
};

export function OrderStatusBadge({
  status,
  flow = "product",
}: {
  status: FulfillmentStatus;
  flow?: OrderFlowType;
}) {
  const cfg = flowConfig(flow);
  const base = BASE_LABELS[status] ?? BASE_LABELS.pending;
  const label = cfg.statusBadge[status] ?? base.label;
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${base.cls}`}>
      {label}
    </span>
  );
}

export const FULFILLMENT_LABEL = BASE_LABELS;
