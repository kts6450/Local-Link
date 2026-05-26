import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { OrderStatusBadge } from "../../components/OrderStatusBadge";
import { PageHeader } from "../../components/ui/PageHeader";
import { api } from "../../lib/api";
import {
  ORDER_FLOW_TABS,
  NEXT_STEPS,
  PROGRESS_INDEX,
  alimtalkKind,
  flowConfig,
  formatOrderSchedule,
  orderFlowType,
  ordersForFlow,
  type OrderFlowType,
} from "../../lib/orderFlow";
import type { FulfillmentStatus, Order } from "../../types";

type StatusFilter = "all" | FulfillmentStatus;

function OrderProgress({
  status,
  flow,
}: {
  status: FulfillmentStatus;
  flow: OrderFlowType;
}) {
  const cfg = flowConfig(flow);
  const idx = PROGRESS_INDEX[status];
  const cancelled = status === "cancelled";

  if (cancelled) {
    return (
      <div className="rounded-xl bg-rose-50 border border-rose-100 px-4 py-3 text-sm font-semibold text-rose-700">
        ✕ 주문이 취소되었습니다
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1 sm:gap-2">
      {cfg.progressSteps.map((step, i) => {
        const done = i <= idx;
        const current = i === idx;
        return (
          <div key={step.id} className="flex items-center flex-1">
            <div className="flex flex-col items-center flex-1">
              <div
                className={`flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold transition-colors ${
                  done
                    ? "bg-shop-tealDark text-white"
                    : "bg-slate-100 text-slate-400"
                } ${current ? "ring-4 ring-shop-teal/30" : ""}`}
              >
                {done ? step.emoji : i + 1}
              </div>
              <span
                className={`mt-1 text-[11px] sm:text-xs font-semibold ${
                  done ? "text-shop-tealDark" : "text-slate-400"
                }`}
              >
                {step.label}
              </span>
            </div>
            {i < cfg.progressSteps.length - 1 && (
              <div
                className={`h-0.5 flex-1 -mt-5 ${
                  i < idx ? "bg-shop-tealDark" : "bg-slate-200"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function parseFlowTab(raw: string | null): OrderFlowType {
  if (raw === "lodging" || raw === "experience" || raw === "product") return raw;
  return "product";
}

export function SellerOrdersPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const flowTab = parseFlowTab(searchParams.get("tab"));
  const cfg = flowConfig(flowTab);

  const [orders, setOrders] = useState<Order[]>([]);
  const [agent, setAgent] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Record<string, unknown>>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [query, setQuery] = useState("");

  useEffect(() => {
    Promise.all([api.getSellerOrders(), api.getAgentSuggestions()])
      .then(([o, a]) => {
        setOrders(o);
        setAgent(a.suggestions);
      })
      .catch(() => {
        setOrders([]);
        setAgent([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const flowOrders = useMemo(() => ordersForFlow(orders, flowTab), [orders, flowTab]);

  const flowCounts = useMemo(() => {
    const c: Record<OrderFlowType, number> = { product: 0, lodging: 0, experience: 0 };
    for (const o of orders) c[orderFlowType(o)]++;
    return c;
  }, [orders]);

  const counts = useMemo(() => {
    const c: Record<StatusFilter, number> = {
      all: flowOrders.length,
      pending: 0,
      preparing: 0,
      shipping: 0,
      completed: 0,
      cancelled: 0,
    };
    for (const o of flowOrders) c[o.fulfillment_status]++;
    return c;
  }, [flowOrders]);

  const totals = useMemo(() => {
    const active = flowOrders.filter(
      (o) => o.fulfillment_status !== "cancelled" && o.payment_status === "paid"
    );
    const revenue = active.reduce((sum, o) => sum + o.total, 0);
    return {
      revenue,
      todoCount: counts.pending + counts.preparing + counts.shipping,
    };
  }, [flowOrders, counts]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return flowOrders.filter((o) => {
      if (filter !== "all" && o.fulfillment_status !== filter) return false;
      if (!q) return true;
      return (
        o.id.toLowerCase().includes(q) ||
        o.buyer_name.toLowerCase().includes(q) ||
        o.buyer_phone.toLowerCase().includes(q) ||
        o.items.some((i) => i.title.toLowerCase().includes(q))
      );
    });
  }, [flowOrders, filter, query]);

  const filterTabs = useMemo(
    (): { id: StatusFilter; label: string; tone: string }[] => [
      { id: "all", label: "전체", tone: "bg-brand-ink text-white" },
      { id: "pending", label: "결제 대기", tone: "bg-amber-500 text-white" },
      { id: "preparing", label: cfg.statPreparingLabel, tone: "bg-blue-500 text-white" },
      { id: "shipping", label: cfg.filterShippingLabel, tone: "bg-indigo-500 text-white" },
      { id: "completed", label: "완료", tone: "bg-emerald-600 text-white" },
      { id: "cancelled", label: "취소", tone: "bg-rose-500 text-white" },
    ],
    [cfg]
  );

  const setFlowTab = (tab: OrderFlowType) => {
    setSearchParams({ tab });
    setFilter("all");
  };

  const makeAlimtalk = async (order: Order) => {
    const title = order.items[0]?.title ?? "주문";
    const flow = orderFlowType(order);
    setBusyId(order.id);
    try {
      const r = await api.sellerAlimtalk({
        kind: alimtalkKind(flow),
        title,
        buyer_name: order.buyer_name,
        order_id: order.id,
        description: formatOrderSchedule(order, flow) ?? "",
        price: order.total,
        location: "",
      });
      setDrafts((d) => ({ ...d, [order.id]: r }));
    } finally {
      setBusyId(null);
    }
  };

  const advance = async (order: Order, next: FulfillmentStatus) => {
    const updated = await api.setOrderStatus(order.id, next);
    setOrders((prev) => prev.map((o) => (o.id === order.id ? updated : o)));
  };

  const copyDraft = async (orderId: string, buyer: string, seller: string) => {
    const text = `[구매자]\n${buyer}\n\n[판매자]\n${seller}`;
    await navigator.clipboard.writeText(text);
    setCopiedId(orderId);
    window.setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-8">
      <PageHeader badge={cfg.pageBadge} title={cfg.pageTitle}>
        {cfg.pageDesc} 알림 문구는 <strong>복사</strong>해 문자·카톡에 붙여 넣습니다.
      </PageHeader>

      <section className="flex flex-wrap gap-2">
        {ORDER_FLOW_TABS.map((t) => {
          const active = flowTab === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setFlowTab(t.id)}
              className={
                active
                  ? "rounded-full bg-brand-ink text-white text-sm font-bold px-5 py-2.5"
                  : "rounded-full border border-brand-line bg-white text-sm font-semibold px-5 py-2.5 text-hades-muted hover:bg-brand-warm"
              }
            >
              {t.emoji} {t.label}{" "}
              <span className={active ? "opacity-80" : "text-slate-400"}>
                {flowCounts[t.id]}
              </span>
            </button>
          );
        })}
      </section>

      {agent.length > 0 && (
        <section className="card p-5 border-shop-teal/20 bg-shop-tealLight/40">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-shop-tealDark text-white text-lg shrink-0">
              💡
            </span>
            <div className="flex-1">
              <h2 className="font-bold text-shop-tealDark">운영 제안</h2>
              <ul className="mt-2 space-y-1 text-slate-800 list-disc pl-5 text-sm">
                {agent.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      )}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card p-5 flex items-start gap-4">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-50 text-2xl shrink-0">
            ⏱
          </span>
          <div className="min-w-0">
            <p className="text-sm text-hades-muted">처리 대기</p>
            <p className="mt-1 text-3xl font-bold text-brand-ink tabular-nums">
              {totals.todoCount}
              <span className="text-lg font-semibold ml-0.5">건</span>
            </p>
          </div>
        </div>
        <div className="card p-5 flex items-start gap-4">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-2xl shrink-0">
            {cfg.statPreparingEmoji}
          </span>
          <div className="min-w-0">
            <p className="text-sm text-hades-muted">{cfg.statPreparingLabel}</p>
            <p className="mt-1 text-3xl font-bold text-brand-ink tabular-nums">
              {counts.preparing}
              <span className="text-lg font-semibold ml-0.5">건</span>
            </p>
          </div>
        </div>
        <div className="card p-5 flex items-start gap-4">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-2xl shrink-0">
            {cfg.statShippingEmoji}
          </span>
          <div className="min-w-0">
            <p className="text-sm text-hades-muted">{cfg.statShippingLabel}</p>
            <p className="mt-1 text-3xl font-bold text-brand-ink tabular-nums">
              {counts.shipping}
              <span className="text-lg font-semibold ml-0.5">건</span>
            </p>
          </div>
        </div>
        <div className="card p-5 flex items-start gap-4">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-2xl shrink-0">
            💰
          </span>
          <div className="min-w-0">
            <p className="text-sm text-hades-muted">진행 매출</p>
            <p className="mt-1 text-3xl font-bold text-brand-ink tabular-nums">
              {totals.revenue.toLocaleString()}
              <span className="text-lg font-semibold">원</span>
            </p>
          </div>
        </div>
      </section>

      <section className="card p-4 sm:p-5">
        <div className="flex flex-col lg:flex-row lg:items-center gap-4">
          <div className="flex flex-wrap gap-2">
            {filterTabs.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setFilter(t.id)}
                className={
                  filter === t.id
                    ? `rounded-full text-sm font-bold px-4 py-2 ${t.tone}`
                    : "rounded-full border border-brand-line bg-white text-sm font-semibold px-4 py-2 text-hades-muted hover:bg-brand-warm"
                }
              >
                {t.label} {counts[t.id]}
              </button>
            ))}
          </div>
          <label className="relative flex-1 lg:max-w-md lg:ml-auto">
            <span className="sr-only">검색</span>
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-hades-muted">🔍</span>
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="주문번호·구매자·상품 검색"
              className="w-full rounded-full border border-brand-line bg-brand-cream/50 pl-11 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-ink/20"
            />
          </label>
        </div>
      </section>

      {loading ? (
        <p className="card p-12 text-center text-hades-muted">불러오는 중…</p>
      ) : filtered.length === 0 ? (
        <div className="card p-12 text-center text-hades-muted">
          <p className="text-3xl mb-3">📭</p>
          <p className="text-lg font-semibold text-brand-ink">
            {flowOrders.length === 0
              ? `${cfg.pageTitle}이 아직 없습니다`
              : "이 조건에 맞는 주문이 없습니다"}
          </p>
          {flowOrders.length > 0 && filter !== "all" && (
            <button
              type="button"
              onClick={() => setFilter("all")}
              className="mt-4 btn-primary text-sm"
            >
              전체 보기
            </button>
          )}
        </div>
      ) : (
        <ul className="space-y-4">
          {filtered.map((o) => {
            const d = drafts[o.id];
            const flow = orderFlowType(o);
            const flowCfg = flowConfig(flow);
            const next = NEXT_STEPS[o.fulfillment_status] ?? [];
            const schedule = formatOrderSchedule(o, flow);
            const itemCount = o.items.reduce((s, i) => s + i.quantity, 0);
            return (
              <li key={o.id} className="card p-0 overflow-hidden">
                <div className="p-5 sm:p-6 space-y-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-2 min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <OrderStatusBadge status={o.fulfillment_status} flow={flow} />
                        <span className="font-mono text-xs text-hades-muted">{o.id}</span>
                        <span className="text-xs text-hades-muted">
                          ·{" "}
                          {new Date(o.created_at).toLocaleString("ko-KR", {
                            month: "numeric",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                      <p className="font-bold text-xl text-brand-ink">
                        {o.buyer_name}
                        <span className="ml-2 text-sm font-medium text-hades-muted">
                          {o.buyer_phone}
                        </span>
                      </p>
                      {schedule ? (
                        <p className="text-sm font-semibold text-shop-tealDark">{schedule}</p>
                      ) : null}
                      <div className="flex flex-wrap items-center gap-2">
                        {o.items.map((i, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center gap-1.5 rounded-full bg-brand-warm/80 border border-brand-line px-3 py-1 text-sm"
                          >
                            <span className="font-semibold text-brand-ink">{i.title}</span>
                            <span className="text-hades-muted">×{i.quantity}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-2xl font-bold text-emerald-700 tabular-nums">
                        {o.total.toLocaleString()}
                        <span className="text-base font-semibold ml-0.5">원</span>
                      </p>
                      <p className="text-xs text-hades-muted mt-1">
                        {o.payment_status === "paid" ? "✓ 결제 완료" : o.payment_status}
                        {itemCount > 1 ? ` · 총 ${itemCount}개` : ""}
                      </p>
                    </div>
                  </div>

                  <div className="rounded-2xl bg-slate-50/70 border border-slate-100 px-4 py-4">
                    <OrderProgress status={o.fulfillment_status} flow={flow} />
                  </div>

                  {(next.length > 0 || o.fulfillment_status !== "completed") && (
                    <div className="flex flex-wrap gap-2">
                      {next.length > 0 &&
                        o.payment_status === "paid" &&
                        next.map((n) => (
                          <button
                            key={n}
                            type="button"
                            className={
                              n === "cancelled"
                                ? "rounded-full border border-rose-200 bg-white text-rose-700 text-sm font-bold px-4 py-2 hover:bg-rose-50"
                                : "rounded-full bg-brand-ink text-white text-sm font-bold px-5 py-2 hover:bg-brand-ink/90"
                            }
                            onClick={() => void advance(o, n)}
                          >
                            {n === "cancelled" ? "✕" : "→"}{" "}
                            {flowCfg.nextStepLabels[n] ?? n}
                          </button>
                        ))}
                      <button
                        type="button"
                        className="rounded-full border border-brand-line bg-white text-sm font-semibold px-4 py-2 text-brand-ink hover:bg-brand-warm disabled:opacity-50"
                        disabled={busyId === o.id}
                        onClick={() => void makeAlimtalk(o)}
                      >
                        {busyId === o.id ? "만드는 중…" : "💬 알림 문구 만들기"}
                      </button>
                    </div>
                  )}

                  {d && (
                    <div className="rounded-2xl bg-shop-tealLight/30 border border-shop-teal/20 p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-bold text-shop-tealDark">📨 알림 문구</p>
                        <button
                          type="button"
                          className={
                            copiedId === o.id
                              ? "rounded-full bg-emerald-600 text-white text-xs font-bold px-3 py-1.5"
                              : "rounded-full bg-shop-tealDark text-white text-xs font-bold px-3 py-1.5 hover:bg-shop-tealDark/90"
                          }
                          onClick={() =>
                            void copyDraft(
                              o.id,
                              String(d.buyer_message),
                              String(d.seller_reminder)
                            )
                          }
                        >
                          {copiedId === o.id ? "✓ 복사됨" : "복사"}
                        </button>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="rounded-xl bg-white p-3 border border-slate-100">
                          <p className="text-xs font-bold text-hades-muted mb-1">👤 구매자에게</p>
                          <pre className="text-sm whitespace-pre-wrap font-sans text-brand-ink">
                            {String(d.buyer_message)}
                          </pre>
                        </div>
                        <div className="rounded-xl bg-white p-3 border border-slate-100">
                          <p className="text-xs font-bold text-hades-muted mb-1">🏪 판매자 체크</p>
                          <pre className="text-sm whitespace-pre-wrap font-sans text-brand-ink">
                            {String(d.seller_reminder)}
                          </pre>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
