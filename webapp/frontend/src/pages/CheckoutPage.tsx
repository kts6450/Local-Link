import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import { useAuthDisplayName } from "../store/auth";
import { useCart } from "../store/cart";
import type { CartLine, Listing } from "../types";

type PaidSummary = {
  orderId: string;
  txn: string | null;
  buyerName: string;
  title: string;
  kind: "product" | "lodging";
  total: number;
};

export function CheckoutPage() {
  const displayName = useAuthDisplayName();
  const lines = useCart((s) => s.lines);
  const clear = useCart((s) => s.clear);
  const setQty = useCart((s) => s.setQty);
  const remove = useCart((s) => s.remove);

  const [listings, setListings] = useState<Listing[]>([]);
  const [name, setName] = useState(displayName || "");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [paid, setPaid] = useState<PaidSummary | null>(null);
  const [alimtalk, setAlimtalk] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (displayName && !name) setName(displayName);
  }, [displayName, name]);

  useEffect(() => {
    api.getListings().then(setListings).catch(() => setListings([]));
  }, []);

  useEffect(() => {
    if (!paid) return;
    setAlimtalk(null);
    void api
      .sellerAlimtalk({
        kind: paid.kind,
        title: paid.title,
        buyer_name: paid.buyerName,
        order_id: paid.orderId,
        price: paid.total,
      })
      .then(setAlimtalk)
      .catch(() => setAlimtalk(null));
  }, [paid]);

  const byId = useMemo(() => Object.fromEntries(listings.map((l) => [l.id, l])), [listings]);

  const rows = useMemo(() => {
    return lines
      .map((ln) => {
        const l = byId[ln.listingId];
        if (!l) return null;
        return { line: ln, listing: l };
      })
      .filter(Boolean) as { line: CartLine; listing: Listing }[];
  }, [lines, byId]);

  const lineUnitPrice = (r: { line: CartLine; listing: Listing }) =>
    r.line.variant_price != null && Number.isFinite(r.line.variant_price)
      ? r.line.variant_price
      : r.listing.price;
  const total = rows.reduce((s, r) => s + lineUnitPrice(r) * r.line.quantity, 0);

  const placeOrder = async (payMode: "mock" | "card") => {
    if (rows.length === 0) return;
    setBusy(true);
    setPaid(null);
    try {
      // 숙박 체크인/아웃 또는 체험 예약일을 주문에 싣는다.
      const datedRow = rows.find((r) => r.line.stay_start);
      const order = await api.createOrder({
        items: rows.map((r) => ({
          listing_id: r.line.listingId,
          quantity: r.line.quantity,
          stay_start: r.line.stay_start ?? null,
          stay_end: r.line.stay_end ?? null,
        })),
        buyer_name: name.trim(),
        buyer_phone: phone.trim(),
        stay_start: datedRow?.line.stay_start ?? null,
        stay_end: datedRow?.line.stay_end ?? null,
      });
      const settled =
        payMode === "card" ? await api.cardPayDemo(order.id) : await api.mockPay(order.id);
      const first = rows[0].listing;
      setPaid({
        orderId: settled.id,
        txn: settled.payment?.transaction_id ?? null,
        buyerName: name.trim(),
        title: first.title,
        kind: first.kind,
        total,
      });
      clear();
    } catch (e) {
      alert(e instanceof Error ? e.message : "결제 실패");
    } finally {
      setBusy(false);
    }
  };

  const submitMock = (e: FormEvent) => {
    e.preventDefault();
    void placeOrder("mock");
  };

  if (paid) {
    return (
      <div className="max-w-lg mx-auto space-y-6">
        <div className="rounded-3xl border border-emerald-200 bg-emerald-50/60 p-8 text-center shadow-lg">
          <div className="text-5xl mb-4" aria-hidden>
            ✓
          </div>
          <h1 className="text-2xl font-bold text-emerald-900">모의 결제가 완료되었습니다</h1>
          <p className="mt-3 text-lg text-emerald-800">
            실제 돈은 나가지 않았습니다. 시연용 거래입니다.
          </p>
          <p className="mt-6 text-sm text-hades-muted">주문 번호</p>
          <p className="font-mono font-bold text-lg text-hades-text">{paid.orderId}</p>
          {paid.txn && (
            <>
              <p className="mt-2 text-sm text-hades-muted">거래 번호 (가짜)</p>
              <p className="font-mono font-semibold text-hades-text">{paid.txn}</p>
            </>
          )}
          <Link to="/" className="btn-shop inline-block mt-8 text-lg px-8 py-3 no-underline">
            쇼핑으로 돌아가기
          </Link>
        </div>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-bold text-slate-900 text-lg">구매 확인 알림 (미리보기)</h2>
          <p className="mt-2 text-sm text-slate-600 leading-relaxed">
            실제 알림톡·문자는 카카오·통신사 연동 후 자동 발송됩니다. 지금은 문구만 확인할 수
            있습니다. 공급자는 셀러오피스 「주문 · 알림」에서 같은 주문 문구를 볼 수 있습니다.
          </p>
          {alimtalk ? (
            <pre className="mt-4 rounded-xl bg-slate-50 border border-slate-100 p-4 text-sm whitespace-pre-wrap text-slate-800">
              {String(alimtalk.buyer_message ?? "")}
            </pre>
          ) : (
            <p className="mt-4 text-slate-500 text-sm">알림 문구를 준비하는 중…</p>
          )}
        </section>
      </div>
    );
  }

  return (
    <div className="page-shell py-8 sm:py-10">
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-hades-text">장바구니 · 결제</h1>
        <p className="mt-2 text-hades-muted text-lg">
          구매자로 로그인한 상태입니다. 결제는 시연용이며 실제 청구되지 않습니다.
        </p>
      </div>

      {rows.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-hades-line bg-white p-12 text-center text-hades-muted text-lg">
          담긴 물건이 없어요.{" "}
          <Link to="/" className="text-shop-tealDark font-semibold underline">
            쇼핑하러 가기
          </Link>
        </div>
      ) : (
        <>
          <ul className="rounded-3xl border border-hades-line bg-white divide-y divide-hades-line shadow-md overflow-hidden">
            {rows.map(({ line, listing }) => {
              const unit = lineUnitPrice({ line, listing });
              return (
              <li
                key={`${line.listingId}-${line.stay_start ?? ""}-${line.variant_label ?? ""}`}
                className="p-5 flex flex-wrap gap-4 items-center"
              >
                <span className="text-4xl">{listing.emoji}</span>
                <div className="flex-1 min-w-[200px]">
                  <p className="font-bold text-lg">
                    {listing.title}
                    {line.variant_label ? (
                      <span className="ml-2 text-sm font-semibold text-shop-tealDark">
                        ({line.variant_label})
                      </span>
                    ) : null}
                  </p>
                  {listing.category === "experience" && line.stay_start ? (
                    <p className="text-xs text-shop-tealDark font-semibold">
                      체험일 {line.stay_start} · {line.quantity}명
                    </p>
                  ) : line.stay_start && line.stay_end ? (
                    <p className="text-xs text-shop-tealDark font-semibold">
                      체크인 {line.stay_start} · 체크아웃 {line.stay_end}
                    </p>
                  ) : null}
                  <p className="text-sm text-hades-muted">
                    {unit.toLocaleString()}원 ×
                    <input
                      type="number"
                      min={1}
                      className="w-16 ml-1 rounded-lg border border-hades-line px-2 py-1 text-center"
                      value={line.quantity}
                      onChange={(e) =>
                        setQty(
                          line.listingId,
                          parseInt(e.target.value, 10) || 1,
                          line.stay_start,
                          line.stay_end,
                          line.variant_label
                        )
                      }
                    />
                  </p>
                </div>
                <div className="font-bold text-lg text-shop-tealDark">
                  {(unit * line.quantity).toLocaleString()}원
                </div>
                <button
                  type="button"
                  className="text-sm text-red-600 font-semibold"
                  onClick={() =>
                    remove(line.listingId, line.stay_start, line.stay_end, line.variant_label)
                  }
                >
                  빼기
                </button>
              </li>
              );
            })}
          </ul>

          <div className="rounded-3xl border border-hades-line bg-slate-50 p-6 flex justify-between items-center">
            <span className="text-lg font-semibold">합계</span>
            <span className="text-2xl font-bold text-hades-text">{total.toLocaleString()}원</span>
          </div>

          <form
            onSubmit={submitMock}
            className="rounded-3xl border border-hades-line bg-white p-6 sm:p-8 shadow-md space-y-4"
          >
            <h2 className="text-xl font-bold text-hades-text">받는 분 정보</h2>
            <div>
              <label className="block text-sm font-semibold text-hades-muted mb-1">성함</label>
              <input
                className="w-full rounded-xl border border-hades-line px-4 py-3 text-lg"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-hades-muted mb-1">연락처</label>
              <input
                className="w-full rounded-xl border border-hades-line px-4 py-3 text-lg"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                inputMode="tel"
                required
              />
            </div>

            <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4 space-y-2">
              <p className="font-semibold text-hades-text">테스트 카드 (가짜)</p>
              <p className="text-sm text-hades-muted">
                번호 · 유효기간 · CVC는 입력하지 않아도 됩니다.
              </p>
            </div>

            <button type="submit" className="btn-shop w-full text-xl py-4" disabled={busy}>
              {busy ? "처리 중…" : "모의 결제하기"}
            </button>
            <button
              type="button"
              className="btn-ghost w-full text-lg py-3 border-slate-300"
              disabled={busy}
              onClick={() => void placeOrder("card")}
            >
              카드·간편결제 시연
            </button>
            <p className="text-xs text-center text-slate-500">
              두 방식 모두 실제 청구 없이 시연용입니다.
            </p>
          </form>
        </>
      )}
    </div>
    </div>
  );
}
