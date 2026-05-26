import { FormEvent, useEffect, useState } from "react";

import { api } from "../lib/api";
import { useAuth, useAuthRole } from "../store/auth";

interface Review {
  id: string;
  user_name: string;
  rating: number;
  body: string;
  created_at: string;
}

function StarRow({ rating }: { rating: number }) {
  return (
    <span className="text-amber-500 tabular-nums" aria-label={`별점 ${rating}`}>
      {"★".repeat(rating)}
      <span className="text-slate-300">{"★".repeat(5 - rating)}</span>
    </span>
  );
}

export function ReviewSection({ listingId }: { listingId: string }) {
  const role = useAuthRole();
  const user = useAuth((s) => s.user);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [average, setAverage] = useState(0);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [rating, setRating] = useState(5);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // AI 리뷰 요약 관련 상태
  const [summaryText, setSummaryText] = useState<string | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  const fetchSummary = async () => {
    setLoadingSummary(true);
    try {
      const res = await api.getReviewsSummary(listingId);
      if (res.status === "success" && res.summary) {
        setSummaryText(res.summary);
      } else {
        setSummaryText(null);
      }
    } catch (err) {
      console.error("AI 요약 로드 실패:", err);
      setSummaryText(null);
    } finally {
      setLoadingSummary(false);
    }
  };

  const reload = async () => {
    setLoading(true);
    setSummaryText(null);
    try {
      const r = await api.getReviews(listingId);
      setReviews(r.items);
      setAverage(r.average);
      setCount(r.count);
      
      // 리뷰 개수가 3개 이상일 때 요약 데이터 조회
      if (r.count >= 3) {
        void fetchSummary();
      }
    } catch {
      setReviews([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
  }, [listingId]);

  const canWrite = role === "consumer" || role === "master";
  const already = user ? reviews.some((r) => r.user_name === user.display_name) : false;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!body.trim()) {
      setError("리뷰 내용을 입력해 주세요.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.postReview(listingId, { rating, body: body.trim() });
      setBody("");
      setRating(5);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "리뷰 등록 실패");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex items-baseline gap-3">
        <div className="flex items-baseline gap-2">
          <span className="text-4xl font-bold text-amber-600 tabular-nums">
            {count > 0 ? average.toFixed(1) : "—"}
          </span>
          <span className="text-sm text-hades-muted tabular-nums">/ 5.0</span>
        </div>
        <p className="text-sm text-hades-muted">{count}개의 리뷰</p>
      </header>

      {/* AI 리뷰 요약 카드 */}
      {count >= 3 && (
        <div className="rounded-2xl border border-brand-line bg-brand-warm/60 p-5 space-y-2 relative overflow-hidden transition-all duration-300">
          <div className="absolute top-0 right-0 p-3">
            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-brand-ink/10 text-brand-ink">
              AI 요약
            </span>
          </div>
          <p className="font-bold text-brand-ink flex items-center gap-1.5">
            ✨ AI 리뷰 한눈에 보기
          </p>
          {loadingSummary ? (
            <div className="space-y-2 py-2">
              <div className="h-4 bg-slate-200/60 rounded w-3/4 animate-pulse"></div>
              <div className="h-4 bg-slate-200/60 rounded w-5/6 animate-pulse"></div>
            </div>
          ) : summaryText ? (
            <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
              {summaryText}
            </p>
          ) : (
            <p className="text-sm text-hades-muted italic">리뷰 분석 대기 중...</p>
          )}
        </div>
      )}

      {canWrite && !already && (
        <form
          onSubmit={onSubmit}
          className="rounded-2xl border border-hades-line bg-white p-5 space-y-3"
        >
          <p className="font-semibold text-hades-text">리뷰 남기기</p>
          <div className="flex items-center gap-2">
            <span className="text-sm text-hades-muted">별점</span>
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setRating(n)}
                className={`text-2xl ${n <= rating ? "text-amber-500" : "text-slate-300"}`}
                aria-label={`${n}점`}
              >
                ★
              </button>
            ))}
          </div>
          <textarea
            className="input-field min-h-[100px]"
            placeholder="구매·이용 경험을 자세히 적어 주세요."
            value={body}
            onChange={(e) => setBody(e.target.value)}
            maxLength={2000}
          />
          {error ? (
            <p className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </p>
          ) : null}
          <button type="submit" className="btn-primary text-sm py-2 px-4" disabled={busy}>
            {busy ? "등록 중…" : "리뷰 등록"}
          </button>
          <p className="text-xs text-hades-muted">
            결제·이용 완료한 상품에만 등록할 수 있습니다.
          </p>
        </form>
      )}

      {already && (
        <p className="text-sm rounded-lg bg-shop-tealLight/40 text-shop-tealDark px-3 py-2">
          이미 이 상품에 리뷰를 남기셨습니다.
        </p>
      )}

      {!canWrite && (
        <p className="text-sm text-hades-muted">
          구매자로 로그인하시면 결제 완료 후 리뷰를 남길 수 있습니다.
        </p>
      )}

      {loading ? (
        <p className="text-hades-muted py-6">불러오는 중…</p>
      ) : reviews.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 p-8 text-center">
          <p className="text-slate-600">아직 리뷰가 없습니다. 첫 리뷰의 주인공이 되어 주세요.</p>
        </div>
      ) : (
        <ul className="space-y-4">
          {reviews.map((r) => (
            <li key={r.id} className="rounded-2xl border border-hades-line bg-white p-5">
              <div className="flex items-center justify-between gap-2">
                <p className="font-bold text-hades-text">{r.user_name}</p>
                <StarRow rating={r.rating} />
              </div>
              <p className="mt-2 text-slate-800 leading-relaxed whitespace-pre-wrap">{r.body}</p>
              <p className="mt-2 text-xs text-hades-muted">{r.created_at.slice(0, 10)}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
