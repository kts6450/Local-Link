import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth, useAuthDisplayName, useAuthRole } from "../store/auth";
import { api } from "../lib/api";
import {
  buyerFlowTypeLabel,
  buyerFulfillmentBadge,
  buyerQuantityLabel,
  buyerReviewCta,
  buyerReviewTitle,
  formatOrderSchedule,
  orderFlowType,
} from "../lib/orderFlow";
import type { FulfillmentStatus, Order } from "../types";

interface WrittenReview {
  id: string;
  listing_id: string;
  order_id: string | null;
  user_id: string;
  user_name: string;
  rating: number;
  body: string;
  created_at: string;
  listing_title: string;
  listing_cover_image: string | null;
}

export function MyPage() {
  const displayName = useAuthDisplayName();
  const role = useAuthRole();
  const user = useAuth((s) => s.user);

  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 필터 칩 상태: "all" | "pending" | "paid" | "completed" | "reviews"
  const [filter, setFilter] = useState<"all" | "pending" | "paid" | "completed" | "reviews" | "settings">("all");

  // 결제 진행 중 상태
  const [payingId, setPayingId] = useState<string | null>(null);

  // 리뷰 작성 폼 열림 상태 (key: `orderId-listingId`)
  const [activeReviewKey, setActiveReviewKey] = useState<string | null>(null);
  const [reviewRating, setReviewRating] = useState<number>(5);
  const [reviewBody, setReviewBody] = useState<string>("");
  const [submittingReview, setSubmittingReview] = useState<boolean>(false);
  const [reviewSuccessMsg, setReviewSuccessMsg] = useState<{ [key: string]: string }>({});
  const [reviewErrorMsg, setReviewErrorMsg] = useState<string | null>(null);

  // 계정 설정 상태
  const [settingsNickname, setSettingsNickname] = useState("");
  const [settingsCurPw, setSettingsCurPw] = useState("");
  const [settingsNewPw, setSettingsNewPw] = useState("");
  const [settingsConfirmPw, setSettingsConfirmPw] = useState("");
  const [settingsMsg, setSettingsMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(false);

  // 계정 탭 전환 시 입력 초기화
  const handleSetFilter = (f: typeof filter) => {
    if (f === "settings") {
      setSettingsNickname(user?.display_name ?? "");
      setSettingsCurPw("");
      setSettingsNewPw("");
      setSettingsConfirmPw("");
      setSettingsMsg(null);
    }
    setFilter(f);
  };

  // 계정 정보 저장
  const handleSaveSettings = async () => {
    setSettingsMsg(null);
    const trimName = settingsNickname.trim();
    const hasPwChange = settingsNewPw.length > 0;

    if (!trimName && !hasPwChange) {
      setSettingsMsg({ type: "err", text: "변경할 내용이 없습니다." });
      return;
    }
    if (hasPwChange) {
      if (!settingsCurPw) {
        setSettingsMsg({ type: "err", text: "현재 비밀번호를 입력해 주세요." });
        return;
      }
      if (settingsNewPw.length < 8) {
        setSettingsMsg({ type: "err", text: "새 비밀번호는 8자 이상이어야 합니다." });
        return;
      }
      if (settingsNewPw !== settingsConfirmPw) {
        setSettingsMsg({ type: "err", text: "새 비밀번호와 확인이 일치하지 않습니다." });
        return;
      }
    }

    setSettingsLoading(true);
    try {
      const body: { display_name?: string; current_password?: string; new_password?: string } = {};
      if (trimName && trimName !== user?.display_name) body.display_name = trimName;
      if (hasPwChange) {
        body.current_password = settingsCurPw;
        body.new_password = settingsNewPw;
      }
      if (Object.keys(body).length === 0) {
        setSettingsMsg({ type: "err", text: "변경된 내용이 없습니다." });
        return;
      }
      const res = await api.updateProfile(body);
      // 스토어 갱신
      useAuth.getState().setSession(res.token, res.user);
      setSettingsMsg({ type: "ok", text: "계정 정보가 성공적으로 저장되었습니다. ✅" });
      setSettingsCurPw("");
      setSettingsNewPw("");
      setSettingsConfirmPw("");
    } catch (err: unknown) {
      setSettingsMsg({
        type: "err",
        text: err instanceof Error ? err.message : "저장에 실패했습니다.",
      });
    } finally {
      setSettingsLoading(false);
    }
  };

  // 작성한 리뷰 목록 추적 및 마이리뷰 관리
  const [myReviews, setMyReviews] = useState<WrittenReview[]>([]);
  const [loadingReviews, setLoadingReviews] = useState<boolean>(true);
  const [reviewedListingIds, setReviewedListingIds] = useState<string[]>([]);

  useEffect(() => {
    fetchOrders();
    fetchReviews();
  }, []);

  const fetchOrders = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMyOrders();
      // 최신 주문이 위로 가도록 정렬
      const sorted = [...data].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setOrders(sorted);
    } catch (err: unknown) {
      console.error(err);
      setError("주문 내역을 불러오는 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const fetchReviews = async () => {
    setLoadingReviews(true);
    try {
      const data = await api.getMyReviews();
      setMyReviews(data);
      // 이미 리뷰를 쓴 listing_id 수집
      setReviewedListingIds(data.map((r) => r.listing_id));
    } catch (err: unknown) {
      console.error("내가 쓴 리뷰 목록 로딩 실패:", err);
    } finally {
      setLoadingReviews(false);
    }
  };

  // 모의 결제 실행
  const handlePayment = async (orderId: string) => {
    setPayingId(orderId);
    try {
      await api.cardPayDemo(orderId);
      // 성공 후 전체 주문 내역 다시 불러오기
      await fetchOrders();
      alert("결제가 안전하게 완료되었습니다!");
    } catch (err: unknown) {
      console.error(err);
      alert(err instanceof Error ? err.message : "결제 처리 중 오류가 발생했습니다.");
    } finally {
      setPayingId(null);
    }
  };

  // 리뷰 작성 폼 초기화 및 열기
  const openReviewForm = (orderId: string, listingId: string) => {
    setActiveReviewKey(`${orderId}-${listingId}`);
    setReviewRating(5);
    setReviewBody("");
    setReviewErrorMsg(null);
  };

  // 리뷰 등록 제출
  const handleSubmitReview = async (orderId: string, listingId: string) => {
    if (!reviewBody.trim()) {
      setReviewErrorMsg("리뷰 내용을 입력해 주세요.");
      return;
    }
    setSubmittingReview(true);
    setReviewErrorMsg(null);
    try {
      await api.postReview(listingId, {
        rating: reviewRating,
        body: reviewBody.trim(),
        order_id: orderId,
      });

      const key = `${orderId}-${listingId}`;
      setReviewSuccessMsg((prev) => ({
        ...prev,
        [key]: "리뷰가 성공적으로 등록되었습니다. 감사합니다! ⭐",
      }));
      // 새로 등록 완료 시 리뷰 목록 재배치 및 작성 목록 업데이트
      await fetchReviews();
      setActiveReviewKey(null);
    } catch (err: unknown) {
      console.error(err);
      setReviewErrorMsg(err instanceof Error ? err.message : "리뷰를 저장하지 못했습니다.");
    } finally {
      setSubmittingReview(false);
    }
  };

  // 주문 필터링 로직
  const filteredOrders = orders.filter((order) => {
    if (filter === "all") return true;
    if (filter === "pending") return order.payment_status === "pending";
    if (filter === "paid") return order.payment_status === "paid";
    if (filter === "completed") return order.fulfillment_status === "completed";
    return true;
  });

  // 상태 뱃지 스타일 정의
  const getPaymentStatusBadge = (status: string) => {
    if (status === "paid") {
      return (
        <span className="inline-flex items-center gap-1 text-[13px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200/80 rounded-full px-3 py-1 shadow-sm">
          🟢 결제 완료
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 text-[13px] font-bold text-amber-700 bg-amber-50 border border-amber-200/80 rounded-full px-3 py-1 shadow-sm animate-pulse">
        🟡 결제 대기
      </span>
    );
  };

  const getFulfillmentStatusBadge = (order: Order) => {
    const flow = orderFlowType(order);
    const badge = buyerFulfillmentBadge(flow, order.fulfillment_status as FulfillmentStatus);
    const bounce = order.fulfillment_status === "shipping" ? " animate-bounce-slow" : "";
    return (
      <span
        className={`inline-flex items-center gap-1 text-[12px] font-semibold border rounded-md px-2 py-0.5 ${badge.cls}${bounce}`}
      >
        {badge.emoji ? `${badge.emoji} ` : ""}
        {badge.label}
      </span>
    );
  };

  return (
    <div className="page-shell pt-8 pb-20 sm:pb-28">
      {/* 웰컴 프로필 영역 */}
      <section className="reveal mb-12">
        <div className="card bg-aurora border-brand-line/70 p-6 sm:p-8 flex flex-col md:flex-row items-center md:justify-between gap-6 relative overflow-hidden">
          <div className="flex items-center gap-5 sm:gap-6 z-10">
            {/* 아바타 */}
            <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-full bg-gradient-to-tr from-brand-ink/10 to-brand-ink/5 border-2 border-white flex items-center justify-center text-4xl sm:text-5xl shadow-md hover:scale-105 transition-transform duration-300">
              🌾
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-2xl sm:text-3xl font-extrabold text-brand-ink">
                  {displayName}님
                </h1>
                <span className="text-xs sm:text-sm font-bold bg-brand-ink text-white rounded-full px-3 py-1 shadow-sm">
                  {role === "master" ? "운영 총괄자" : "소중한 고객"}
                </span>
              </div>
              <p className="text-sm sm:text-base text-hades-muted/90 mt-1 font-medium">
                {user?.email}
              </p>
              <p className="text-xs sm:text-sm text-brand-ink/75 font-semibold mt-1">
                로컬링크와 함께 정겨운 우리 농어촌 거래를 이어가고 있습니다.
              </p>
            </div>
          </div>

          <div className="flex gap-4 md:self-end z-10 w-full md:w-auto">
            <Link
              to="/"
              className="btn-secondary w-full md:w-auto text-sm py-2.5 px-6 font-semibold no-underline"
            >
              쇼핑하러 가기
            </Link>
          </div>
        </div>
      </section>

      {/* 메인 콘텐츠 영역 */}
      <div className="grid lg:grid-cols-4 gap-8 items-start">
        {/* 사이드바 필터 */}
        <aside className="reveal lg:col-span-1 space-y-4">
          <div className="card p-5 sm:p-6 bg-white">
            <h2 className="text-lg font-bold text-brand-ink mb-4 border-b border-brand-line/50 pb-2">
              주문 조회 필터
            </h2>
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={() => handleSetFilter("all")}
                className={`text-left px-4 py-3 rounded-2xl font-bold text-sm transition-all flex justify-between items-center ${
                  filter === "all"
                    ? "bg-brand-ink text-white shadow-soft"
                    : "text-hades-muted hover:bg-brand-warm hover:text-brand-ink"
                }`}
              >
                <span>전체 주문</span>
                <span className="text-xs bg-black/10 rounded-full px-2 py-0.5 tabular-nums">
                  {orders.length}
                </span>
              </button>

              <button
                type="button"
                onClick={() => handleSetFilter("pending")}
                className={`text-left px-4 py-3 rounded-2xl font-bold text-sm transition-all flex justify-between items-center ${
                  filter === "pending"
                    ? "bg-brand-ink text-white shadow-soft"
                    : "text-hades-muted hover:bg-brand-warm hover:text-brand-ink"
                }`}
              >
                <span>🟡 결제 대기</span>
                <span className="text-xs bg-black/10 rounded-full px-2 py-0.5 tabular-nums">
                  {orders.filter((o) => o.payment_status === "pending").length}
                </span>
              </button>

              <button
                type="button"
                onClick={() => handleSetFilter("paid")}
                className={`text-left px-4 py-3 rounded-2xl font-bold text-sm transition-all flex justify-between items-center ${
                  filter === "paid"
                    ? "bg-brand-ink text-white shadow-soft"
                    : "text-hades-muted hover:bg-brand-warm hover:text-brand-ink"
                }`}
              >
                <span>🟢 결제 완료</span>
                <span className="text-xs bg-black/10 rounded-full px-2 py-0.5 tabular-nums">
                  {orders.filter((o) => o.payment_status === "paid").length}
                </span>
              </button>

              <button
                type="button"
                onClick={() => handleSetFilter("completed")}
                className={`text-left px-4 py-3 rounded-2xl font-bold text-sm transition-all flex justify-between items-center ${
                  filter === "completed"
                    ? "bg-brand-ink text-white shadow-soft"
                    : "text-hades-muted hover:bg-brand-warm hover:text-brand-ink"
                }`}
              >
                <span>✅ 이용 완료</span>
                <span className="text-xs bg-black/10 rounded-full px-2 py-0.5 tabular-nums">
                  {orders.filter((o) => o.fulfillment_status === "completed").length}
                </span>
              </button>

              <div className="h-px bg-brand-line/50 my-2" />
              <h2 className="text-lg font-bold text-brand-ink mb-2 px-1">내 활동 관리</h2>

              <button
                type="button"
                onClick={() => handleSetFilter("reviews")}
                className={`text-left px-4 py-3 rounded-2xl font-bold text-sm transition-all flex justify-between items-center ${
                  filter === "reviews"
                    ? "bg-brand-ink text-white shadow-soft"
                    : "text-hades-muted hover:bg-brand-warm hover:text-brand-ink"
                }`}
              >
                <span>✍️ 내가 작성한 리뷰</span>
                <span className="text-xs bg-black/10 rounded-full px-2 py-0.5 tabular-nums">
                  {myReviews.length}
                </span>
              </button>

              <div className="h-px bg-brand-line/50 my-2" />
              <h2 className="text-lg font-bold text-brand-ink mb-2 px-1">계정 관리</h2>

              <button
                type="button"
                onClick={() => handleSetFilter("settings")}
                className={`text-left px-4 py-3 rounded-2xl font-bold text-sm transition-all flex items-center gap-2 ${
                  filter === "settings"
                    ? "bg-brand-ink text-white shadow-soft"
                    : "text-hades-muted hover:bg-brand-warm hover:text-brand-ink"
                }`}
              >
                ⚙️ 계정 정보 수정
              </button>
            </div>
          </div>
        </aside>

        {/* 메인 리스트 영역 */}
        <main className="reveal lg:col-span-3 space-y-6">
          {filter === "settings" ? (
            /* 계정 정보 수정 뷰 */
            <div className="space-y-6">
              <h2 className="heading-section text-brand-ink">계정 정보 수정</h2>

              <div className="card bg-white p-6 sm:p-8 space-y-8">
                {/* 닉네임 변경 */}
                <div>
                  <h3 className="text-base font-extrabold text-brand-ink mb-4 flex items-center gap-2">
                    <span className="text-xl">✏️</span> 닉네임 변경
                  </h3>
                  <div className="space-y-3">
                    <label className="block text-sm font-bold text-hades-muted" htmlFor="settings-nickname">
                      새 닉네임
                    </label>
                    <input
                      id="settings-nickname"
                      type="text"
                      value={settingsNickname}
                      onChange={(e) => setSettingsNickname(e.target.value)}
                      maxLength={100}
                      placeholder="변경할 닉네임을 입력하세요"
                      className="w-full rounded-xl border border-brand-line/60 px-4 py-3 text-sm font-medium text-brand-ink placeholder:text-hades-muted/40 focus:outline-none focus:ring-2 focus:ring-brand-ink/20 focus:border-brand-ink/40 transition"
                    />
                  </div>
                </div>

                <div className="h-px bg-brand-line/40" />

                {/* 비밀번호 변경 */}
                <div>
                  <h3 className="text-base font-extrabold text-brand-ink mb-4 flex items-center gap-2">
                    <span className="text-xl">🔒</span> 비밀번호 변경
                  </h3>
                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-bold text-hades-muted mb-1.5" htmlFor="settings-cur-pw">
                        현재 비밀번호
                      </label>
                      <input
                        id="settings-cur-pw"
                        type="password"
                        value={settingsCurPw}
                        onChange={(e) => setSettingsCurPw(e.target.value)}
                        placeholder="현재 비밀번호"
                        className="w-full rounded-xl border border-brand-line/60 px-4 py-3 text-sm font-medium text-brand-ink placeholder:text-hades-muted/40 focus:outline-none focus:ring-2 focus:ring-brand-ink/20 focus:border-brand-ink/40 transition"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-bold text-hades-muted mb-1.5" htmlFor="settings-new-pw">
                        새 비밀번호 <span className="font-normal text-xs">(8자 이상)</span>
                      </label>
                      <input
                        id="settings-new-pw"
                        type="password"
                        value={settingsNewPw}
                        onChange={(e) => setSettingsNewPw(e.target.value)}
                        placeholder="새 비밀번호 (8자 이상)"
                        className="w-full rounded-xl border border-brand-line/60 px-4 py-3 text-sm font-medium text-brand-ink placeholder:text-hades-muted/40 focus:outline-none focus:ring-2 focus:ring-brand-ink/20 focus:border-brand-ink/40 transition"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-bold text-hades-muted mb-1.5" htmlFor="settings-confirm-pw">
                        새 비밀번호 확인
                      </label>
                      <input
                        id="settings-confirm-pw"
                        type="password"
                        value={settingsConfirmPw}
                        onChange={(e) => setSettingsConfirmPw(e.target.value)}
                        placeholder="새 비밀번호 재입력"
                        className="w-full rounded-xl border border-brand-line/60 px-4 py-3 text-sm font-medium text-brand-ink placeholder:text-hades-muted/40 focus:outline-none focus:ring-2 focus:ring-brand-ink/20 focus:border-brand-ink/40 transition"
                      />
                    </div>
                  </div>
                </div>

                {/* 결과 메시지 */}
                {settingsMsg && (
                  <p
                    className={`text-sm font-bold rounded-xl px-4 py-3 ${
                      settingsMsg.type === "ok"
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : "bg-rose-50 text-rose-700 border border-rose-200"
                    }`}
                  >
                    {settingsMsg.text}
                  </p>
                )}

                {/* 저장 버튼 */}
                <div className="flex justify-end">
                  <button
                    id="settings-save-btn"
                    type="button"
                    disabled={settingsLoading}
                    onClick={handleSaveSettings}
                    className="btn-primary py-2.5 px-8 text-sm font-bold shadow-md disabled:opacity-50"
                  >
                    {settingsLoading ? (
                      <span className="flex items-center gap-2">
                        <span className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                        저장 중...
                      </span>
                    ) : (
                      "변경 사항 저장"
                    )}
                  </button>
                </div>
              </div>
            </div>
          ) : filter === "reviews" ? (
            /* 리뷰 관리 뷰 */
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="heading-section text-brand-ink">내가 작성한 리뷰</h2>
                <div className="text-sm text-hades-muted font-medium">
                  총 <span className="font-bold text-brand-ink">{myReviews.length}</span>개 작성됨
                </div>
              </div>

              {loadingReviews ? (
                <div className="card p-20 flex flex-col items-center justify-center gap-4 bg-white">
                  <span className="h-10 w-10 rounded-full border-2 border-brand-ink border-t-transparent animate-spin" />
                  <p className="text-sm font-semibold text-hades-muted">리뷰를 불러오고 있습니다...</p>
                </div>
              ) : myReviews.length === 0 ? (
                <div className="card p-16 text-center bg-white">
                  <p className="text-xl font-bold text-brand-ink">아직 작성하신 리뷰가 없습니다.</p>
                  <p className="text-sm text-hades-muted mt-2">이용하신 상품에 소중한 별점과 후기를 남겨보세요!</p>
                </div>
              ) : (
                <ul className="space-y-4">
                  {myReviews.map((review) => (
                    <li
                      key={review.id}
                      className="card bg-white p-5 sm:p-6 border border-brand-line/60 rounded-3xl flex gap-4 items-start relative overflow-hidden"
                    >
                      {/* 상품 대표 이미지 */}
                      {review.listing_cover_image ? (
                        <img
                          src={review.listing_cover_image}
                          alt={review.listing_title}
                          className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl object-cover border border-brand-line/40 shrink-0"
                        />
                      ) : (
                        <div className="w-16 h-16 sm:w-20 sm:h-20 bg-brand-cream/60 border border-brand-line/40 rounded-2xl flex items-center justify-center text-3xl shrink-0">
                          🏷️
                        </div>
                      )}

                      <div className="flex-1 min-w-0">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-2">
                          <Link
                            to={`/listing/${review.listing_id}`}
                            className="font-extrabold text-brand-ink text-base sm:text-lg hover:underline no-underline truncate"
                          >
                            {review.listing_title}
                          </Link>
                          <span className="text-[12px] font-medium text-hades-muted shrink-0">
                            {new Date(review.created_at).toLocaleDateString("ko-KR", {
                              year: "numeric",
                              month: "2-digit",
                              day: "2-digit",
                            })}
                          </span>
                        </div>

                        {/* 별점 */}
                        <div className="flex items-center gap-0.5 mb-2.5">
                          {[1, 2, 3, 4, 5].map((star) => (
                            <span
                              key={star}
                              className={`text-lg leading-none ${
                                star <= review.rating ? "text-amber-400" : "text-gray-200"
                              }`}
                            >
                              ★
                            </span>
                          ))}
                        </div>

                        {/* 리뷰 내용 */}
                        <p className="text-sm sm:text-base text-brand-ink/90 font-medium whitespace-pre-wrap leading-relaxed">
                          {review.body}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            /* 주문 조회 뷰 */
            <>
              <div className="flex items-center justify-between">
                <h2 className="heading-section text-brand-ink">주문 내역</h2>
                <div className="text-sm text-hades-muted font-medium">
                  총 <span className="font-bold text-brand-ink">{filteredOrders.length}</span>건 조회됨
                </div>
              </div>

              {loading ? (
                <div className="card p-20 flex flex-col items-center justify-center gap-4 bg-white">
                  <span className="h-10 w-10 rounded-full border-2 border-brand-ink border-t-transparent animate-spin" />
                  <p className="text-sm font-semibold text-hades-muted">주문 목록을 불러오고 있습니다...</p>
                </div>
              ) : error ? (
                <div className="card p-12 text-center bg-rose-50 border-rose-100 text-rose-700">
                  <p className="font-bold">{error}</p>
                  <button type="button" onClick={fetchOrders} className="btn-secondary mt-4 py-2 px-5 text-sm">
                    다시 시도
                  </button>
                </div>
              ) : filteredOrders.length === 0 ? (
                <div className="card p-16 text-center bg-white">
                  <p className="text-xl font-bold text-brand-ink">조건에 일치하는 주문이 없습니다.</p>
                  <p className="text-sm text-hades-muted mt-2">로컬링크의 특별한 상품들을 주문해 보세요!</p>
                  <Link to="/" className="btn-primary mt-6 text-sm no-underline inline-block">
                    상품 둘러보기
                  </Link>
                </div>
              ) : (
                <ul className="space-y-6">
                  {filteredOrders.map((order) => {
                    const flow = orderFlowType(order);
                    const schedule = formatOrderSchedule(order, flow);
                    return (
                    <li
                      key={order.id}
                      className="card-hover bg-white p-6 sm:p-7 relative overflow-hidden"
                    >
                      {/* 카드 헤더 */}
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-brand-line/50 pb-4 mb-5 gap-3">
                        <div>
                          <div className="flex items-center gap-3 flex-wrap">
                            <span className="text-[13px] font-bold text-hades-muted/70 tracking-wider font-mono">
                              주문번호: {order.id}
                            </span>
                            <span className="text-[11px] font-bold text-shop-tealDark bg-shop-tealLight/60 border border-shop-teal/20 rounded-full px-2.5 py-0.5">
                              {buyerFlowTypeLabel(flow)}
                            </span>
                            {getFulfillmentStatusBadge(order)}
                          </div>
                          <h3 className="text-[15px] font-bold text-hades-muted mt-1">
                            주문 일자: {new Date(order.created_at).toLocaleString("ko-KR", {
                              year: "numeric",
                              month: "long",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </h3>
                          {schedule ? (
                            <p className="mt-1.5 inline-flex items-center gap-1.5 text-[13px] font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200/80 rounded-full px-3 py-1">
                              {schedule}
                            </p>
                          ) : null}
                        </div>
                        <div className="flex items-center gap-3">
                          {getPaymentStatusBadge(order.payment_status)}
                        </div>
                      </div>

                      {/* 주문 상품 리스트 */}
                      <ul className="space-y-4">
                        {order.items.map((item) => {
                          const reviewKey = `${order.id}-${item.listing_id}`;
                          const hasReviewed = reviewedListingIds.includes(item.listing_id);
                          const isReviewOpen = activeReviewKey === reviewKey;

                          return (
                            <li
                              key={item.listing_id}
                              className="bg-brand-cream/35 border border-brand-line/40 rounded-2xl p-4 sm:p-5 flex flex-col gap-4"
                            >
                              <div className="flex items-start justify-between gap-4">
                                <div>
                                  <Link
                                    to={`/listing/${item.listing_id}`}
                                    className="font-extrabold text-brand-ink text-base sm:text-lg hover:underline no-underline"
                                  >
                                    {item.title}
                                  </Link>
                                  <div className="flex items-center gap-4 mt-1.5 text-sm font-semibold text-hades-muted">
                                    <span>수량: {buyerQuantityLabel(flow, item.quantity)}</span>
                                    <span>·</span>
                                    <span>단가: {item.unit_price.toLocaleString("ko-KR")}원</span>
                                  </div>
                                </div>
                                <div className="text-right shrink-0">
                                  <span className="font-extrabold text-brand-ink text-base">
                                    {(item.unit_price * item.quantity).toLocaleString("ko-KR")}원
                                  </span>
                                </div>
                              </div>

                              {/* 리뷰 쓰기 인터랙션 */}
                              {order.payment_status === "paid" && (
                                <div className="border-t border-brand-line/40 pt-3 mt-1 flex flex-col gap-3">
                                  {reviewSuccessMsg[reviewKey] ? (
                                    <p className="text-sm font-bold text-emerald-700 bg-emerald-50 rounded-xl p-2.5 border border-emerald-200">
                                      {reviewSuccessMsg[reviewKey]}
                                    </p>
                                  ) : hasReviewed ? (
                                    <p className="text-xs font-semibold text-emerald-600">
                                      ✓ 작성 완료된 리뷰가 존재합니다.
                                    </p>
                                  ) : !isReviewOpen ? (
                                    <button
                                      type="button"
                                      onClick={() => openReviewForm(order.id, item.listing_id)}
                                      className="self-start text-xs font-bold text-brand-ink hover:underline flex items-center gap-1"
                                    >
                                      ⭐ {buyerReviewCta(flow)}
                                    </button>
                                  ) : (
                                    <div className="bg-white rounded-xl p-4 border border-brand-line/70 shadow-sm animate-assistantPop space-y-3">
                                      <div className="flex items-center justify-between">
                                        <h4 className="text-[13px] font-extrabold text-brand-ink">
                                          {buyerReviewTitle(flow)}
                                        </h4>
                                        {/* 별점 컴포넌트 */}
                                        <div className="flex items-center gap-1">
                                          {[1, 2, 3, 4, 5].map((star) => (
                                            <button
                                              key={star}
                                              type="button"
                                              onClick={() => setReviewRating(star)}
                                              className={`text-xl focus:outline-none transition-colors duration-150 ${
                                                star <= reviewRating
                                                  ? "text-amber-400"
                                                  : "text-gray-200"
                                              }`}
                                            >
                                              ★
                                            </button>
                                          ))}
                                        </div>
                                      </div>

                                      <div className="space-y-1">
                                        <label className="sr-only" htmlFor={`textarea-${reviewKey}`}>리뷰 내용</label>
                                        <textarea
                                          id={`textarea-${reviewKey}`}
                                          rows={3}
                                          value={reviewBody}
                                          onChange={(e) => setReviewBody(e.target.value)}
                                          placeholder="지역 생산자분께 힘이 되는 따뜻한 후기를 작성해 주세요. (최대 2,000자)"
                                          className="w-full text-sm rounded-xl border border-brand-line/60 p-3 placeholder:text-hades-muted/50 focus:outline-none focus:ring-1 focus:ring-brand-ink/20 focus:border-brand-ink/40"
                                        />
                                      </div>

                                      {reviewErrorMsg && (
                                        <p className="text-xs font-bold text-rose-600">
                                          ⚠️ {reviewErrorMsg}
                                        </p>
                                      )}

                                      <div className="flex justify-end gap-2 text-xs">
                                        <button
                                          type="button"
                                          onClick={() => setActiveReviewKey(null)}
                                          className="px-3 py-1.5 rounded-lg border border-brand-line font-bold text-hades-muted hover:bg-brand-warm"
                                        >
                                          취소
                                        </button>
                                        <button
                                          type="button"
                                          disabled={submittingReview}
                                          onClick={() => handleSubmitReview(order.id, item.listing_id)}
                                          className="px-3 py-1.5 rounded-lg bg-brand-ink text-white font-bold shadow-soft hover:bg-brand-ink/90 disabled:opacity-50"
                                        >
                                          {submittingReview ? "등록 중..." : "리뷰 등록"}
                                        </button>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              )}
                            </li>
                          );
                        })}
                      </ul>

                      {/* 카드 푸터 (총액 및 즉시 결제 처리) */}
                      <div className="border-t border-brand-line/50 pt-4 mt-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                        <div className="flex items-baseline gap-2">
                          <span className="text-sm font-semibold text-hades-muted">최종 결제 금액:</span>
                          <span className="text-xl sm:text-2xl font-black text-brand-ink">
                            {order.total.toLocaleString("ko-KR")}원
                          </span>
                        </div>

                        {order.payment_status === "pending" && (
                          <button
                            type="button"
                            disabled={payingId !== null}
                            onClick={() => handlePayment(order.id)}
                            className="btn-primary py-2 px-6 text-sm font-bold w-full sm:w-auto shadow-md"
                          >
                            {payingId === order.id ? (
                              <span className="flex items-center justify-center gap-2">
                                <span className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                                결제 승인 중...
                              </span>
                            ) : (
                              "💳 안전하게 결제 완료하기"
                            )}
                          </button>
                        )}
                      </div>
                    </li>
                    );
                  })}
                </ul>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
