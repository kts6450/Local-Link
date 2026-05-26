import type { FulfillmentStatus, Order, OrderItem } from "../types";

export type OrderFlowType = "product" | "lodging" | "experience";

export const ORDER_FLOW_TABS: { id: OrderFlowType; label: string; emoji: string }[] = [
  { id: "product", label: "특산 주문", emoji: "🛒" },
  { id: "lodging", label: "스테이 예약", emoji: "🏠" },
  { id: "experience", label: "체험 예약", emoji: "🌾" },
];

export function orderItemFlow(item: OrderItem): OrderFlowType {
  if (item.kind === "lodging") return "lodging";
  if (item.category === "experience") return "experience";
  return "product";
}

/** 주문에 포함된 유형 — 숙박·체험이 하나라도 있으면 해당 탭으로 분류 */
export function orderFlowType(order: Order): OrderFlowType {
  if (order.items.some((i) => orderItemFlow(i) === "lodging")) return "lodging";
  if (order.items.some((i) => orderItemFlow(i) === "experience")) return "experience";
  return "product";
}

export function ordersForFlow(orders: Order[], flow: OrderFlowType): Order[] {
  return orders.filter((o) => orderFlowType(o) === flow);
}

type ProgressStep = { id: FulfillmentStatus; label: string; emoji: string };

export type OrderFlowConfig = {
  pageBadge: string;
  pageTitle: string;
  pageDesc: string;
  progressSteps: ProgressStep[];
  nextStepLabels: Partial<Record<FulfillmentStatus, string>>;
  statusBadge: Partial<Record<FulfillmentStatus, string>>;
  filterShippingLabel: string;
  statPreparingLabel: string;
  statShippingLabel: string;
  statPreparingEmoji: string;
  statShippingEmoji: string;
};

const PRODUCT_FLOW: OrderFlowConfig = {
  pageBadge: "배송",
  pageTitle: "특산 주문",
  pageDesc: "결제된 주문을 준비·배송 단계로 진행하세요.",
  progressSteps: [
    { id: "pending", label: "결제", emoji: "💳" },
    { id: "preparing", label: "준비", emoji: "📦" },
    { id: "shipping", label: "배송", emoji: "🚚" },
    { id: "completed", label: "완료", emoji: "✅" },
  ],
  nextStepLabels: {
    preparing: "준비 시작",
    shipping: "배송 시작",
    completed: "완료 처리",
    cancelled: "취소",
  },
  statusBadge: {
    preparing: "준비 중",
    shipping: "배송 중",
  },
  filterShippingLabel: "배송 중",
  statPreparingLabel: "준비 중",
  statShippingLabel: "배송·진행 중",
  statPreparingEmoji: "📦",
  statShippingEmoji: "🚚",
};

const LODGING_FLOW: OrderFlowConfig = {
  pageBadge: "예약",
  pageTitle: "스테이 예약",
  pageDesc: "예약 확정 → 체크인 → 이용 완료 순으로 진행하세요.",
  progressSteps: [
    { id: "pending", label: "결제", emoji: "💳" },
    { id: "preparing", label: "예약확인", emoji: "📋" },
    { id: "shipping", label: "체크인", emoji: "🏠" },
    { id: "completed", label: "완료", emoji: "✅" },
  ],
  nextStepLabels: {
    preparing: "예약 확정",
    shipping: "체크인 처리",
    completed: "이용 완료",
    cancelled: "취소",
  },
  statusBadge: {
    preparing: "예약 확인 중",
    shipping: "체크인 전",
  },
  filterShippingLabel: "체크인 전",
  statPreparingLabel: "예약 확인 중",
  statShippingLabel: "체크인 전",
  statPreparingEmoji: "📋",
  statShippingEmoji: "🏠",
};

const EXPERIENCE_FLOW: OrderFlowConfig = {
  pageBadge: "예약",
  pageTitle: "체험 예약",
  pageDesc: "참가 확정 → 체험 진행 → 완료 순으로 진행하세요.",
  progressSteps: [
    { id: "pending", label: "결제", emoji: "💳" },
    { id: "preparing", label: "준비", emoji: "🎒" },
    { id: "shipping", label: "진행", emoji: "🎯" },
    { id: "completed", label: "완료", emoji: "✅" },
  ],
  nextStepLabels: {
    preparing: "참가 확정",
    shipping: "체험 시작",
    completed: "체험 완료",
    cancelled: "취소",
  },
  statusBadge: {
    preparing: "준비 중",
    shipping: "진행 중",
  },
  filterShippingLabel: "진행 중",
  statPreparingLabel: "준비 중",
  statShippingLabel: "체험 진행 중",
  statPreparingEmoji: "🎒",
  statShippingEmoji: "🎯",
};

export function flowConfig(flow: OrderFlowType): OrderFlowConfig {
  if (flow === "lodging") return LODGING_FLOW;
  if (flow === "experience") return EXPERIENCE_FLOW;
  return PRODUCT_FLOW;
}

export const NEXT_STEPS: Partial<Record<FulfillmentStatus, FulfillmentStatus[]>> = {
  pending: ["preparing", "cancelled"],
  preparing: ["shipping", "cancelled"],
  shipping: ["completed", "cancelled"],
  completed: [],
  cancelled: [],
};

export const PROGRESS_INDEX: Record<FulfillmentStatus, number> = {
  pending: 0,
  preparing: 1,
  shipping: 2,
  completed: 3,
  cancelled: -1,
};

function fmtDate(iso: string): string {
  const d = iso.slice(0, 10);
  const [y, m, day] = d.split("-");
  if (!y || !m || !day) return iso;
  return `${Number(m)}월 ${Number(day)}일`;
}

function nightsBetween(start: string, end: string): number {
  const a = new Date(`${start.slice(0, 10)}T12:00:00`);
  const b = new Date(`${end.slice(0, 10)}T12:00:00`);
  const diff = Math.round((b.getTime() - a.getTime()) / 86400000);
  return Math.max(1, diff);
}

/** 예약 일정 한 줄 요약 (한국어) */
export function formatOrderSchedule(order: Order, flow: OrderFlowType): string | null {
  const line = order.items.find((i) => i.stay_start) ?? order.items[0];
  const start = line?.stay_start ?? order.stay_start;
  const end = line?.stay_end ?? order.stay_end;
  if (!start) return null;

  const qty = order.items.reduce((s, i) => s + i.quantity, 0);

  if (flow === "lodging") {
    if (end && end.slice(0, 10) !== start.slice(0, 10)) {
      return `📅 ${fmtDate(start)} ~ ${fmtDate(end)} · ${nightsBetween(start, end)}박`;
    }
    return `📅 ${fmtDate(start)} · 1박`;
  }

  if (flow === "experience") {
    return `📅 ${fmtDate(start)} · ${qty}명`;
  }

  return null;
}

export function alimtalkKind(flow: OrderFlowType): "product" | "lodging" {
  return flow === "lodging" ? "lodging" : "product";
}

type BuyerBadge = { label: string; emoji: string; cls: string };

const BUYER_BADGE: Record<OrderFlowType, Record<FulfillmentStatus, BuyerBadge>> = {
  product: {
    pending: { label: "접수 대기", emoji: "", cls: "text-gray-600 bg-gray-50 border-gray-200" },
    preparing: { label: "상품 준비 중", emoji: "📦", cls: "text-indigo-700 bg-indigo-50 border-indigo-200" },
    shipping: { label: "배송 중", emoji: "🚚", cls: "text-blue-700 bg-blue-50 border-blue-200" },
    completed: { label: "배송 완료", emoji: "✅", cls: "text-emerald-700 bg-emerald-50 border-emerald-200" },
    cancelled: { label: "주문 취소", emoji: "❌", cls: "text-rose-700 bg-rose-50 border-rose-200" },
  },
  lodging: {
    pending: { label: "접수 대기", emoji: "", cls: "text-gray-600 bg-gray-50 border-gray-200" },
    preparing: { label: "예약 확인 중", emoji: "📋", cls: "text-indigo-700 bg-indigo-50 border-indigo-200" },
    shipping: { label: "체크인 전", emoji: "🏠", cls: "text-blue-700 bg-blue-50 border-blue-200" },
    completed: { label: "이용 완료", emoji: "✅", cls: "text-emerald-700 bg-emerald-50 border-emerald-200" },
    cancelled: { label: "예약 취소", emoji: "❌", cls: "text-rose-700 bg-rose-50 border-rose-200" },
  },
  experience: {
    pending: { label: "접수 대기", emoji: "", cls: "text-gray-600 bg-gray-50 border-gray-200" },
    preparing: { label: "참가 준비 중", emoji: "🎒", cls: "text-indigo-700 bg-indigo-50 border-indigo-200" },
    shipping: { label: "체험 진행 중", emoji: "🎯", cls: "text-blue-700 bg-blue-50 border-blue-200" },
    completed: { label: "체험 완료", emoji: "✅", cls: "text-emerald-700 bg-emerald-50 border-emerald-200" },
    cancelled: { label: "예약 취소", emoji: "❌", cls: "text-rose-700 bg-rose-50 border-rose-200" },
  },
};

export function buyerFulfillmentBadge(
  flow: OrderFlowType,
  status: FulfillmentStatus
): BuyerBadge {
  return BUYER_BADGE[flow][status] ?? BUYER_BADGE.product.pending;
}

export function buyerQuantityLabel(flow: OrderFlowType, qty: number): string {
  if (flow === "experience") return `${qty}명`;
  return `${qty}개`;
}

export function buyerReviewCta(flow: OrderFlowType): string {
  if (flow === "experience") return "체험 후기 작성하기";
  if (flow === "lodging") return "숙박 후기 작성하기";
  return "상품 리뷰 작성하기";
}

export function buyerReviewTitle(flow: OrderFlowType): string {
  if (flow === "experience") return "체험 만족도 별점";
  if (flow === "lodging") return "숙박 만족도 별점";
  return "상품 만족도 별점";
}

export function buyerFlowTypeLabel(flow: OrderFlowType): string {
  if (flow === "experience") return "체험 예약";
  if (flow === "lodging") return "스테이 예약";
  return "특산 주문";
}
