import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ListingLocalGuide } from "../components/ListingLocalGuide";
import {
  ListingInfoSections,
  ListingUsageGuideSections,
} from "../components/ListingPackageSections";
import { ReviewSection } from "../components/ReviewSection";
import { useListingDetailPoll } from "../hooks/useListingDetailPoll";
import { api } from "../lib/api";
import {
  listingCoverPhoto,
  listingDemoViewCount,
} from "../lib/listingDisplay";
import { useCart } from "../store/cart";

type TabId = "info" | "guide" | "reviews";

function startOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function daysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** 월 달력 — 예약된 날짜(회색·비활성), 체크인/체크아웃 범위 강조 */
function MonthCalendar({
  month,
  checkIn,
  checkOut,
  bookedDates,
  onSelect,
}: {
  month: Date;
  checkIn: Date | null;
  checkOut: Date | null;
  bookedDates: Set<string>;
  onSelect: (d: Date) => void;
}) {
  const y = month.getFullYear();
  const m = month.getMonth();
  const first = new Date(y, m, 1).getDay();
  const total = daysInMonth(y, m);
  const cells: (number | null)[] = [];
  for (let i = 0; i < first; i++) cells.push(null);
  for (let d = 1; d <= total; d++) cells.push(d);

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const inRange = (day: number) => {
    if (!checkIn || !checkOut) return false;
    const d = new Date(y, m, day);
    return d > checkIn && d < checkOut;
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <p className="text-center font-bold text-slate-800 mb-2">
        {y}년 {m + 1}월
      </p>
      <div className="grid grid-cols-7 gap-1 text-center text-xs text-slate-500 mb-1">
        {["일", "월", "화", "수", "목", "금", "토"].map((w) => (
          <span key={w}>{w}</span>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((day, idx) => {
          if (day == null) return <span key={`e-${idx}`} className="h-9" />;
          const d = new Date(y, m, day);
          const iso = toIsoDate(d);
          const past = d < today;
          const booked = bookedDates.has(iso);
          const isCheckIn = checkIn && toIsoDate(checkIn) === iso;
          const isCheckOut = checkOut && toIsoDate(checkOut) === iso;
          const middle = inRange(day);
          const disabled = past || booked;
          const cls = [
            "h-9 rounded-lg text-sm font-semibold transition-colors",
            isCheckIn || isCheckOut
              ? "bg-shop-teal text-white shadow"
              : middle
                ? "bg-shop-tealLight text-shop-tealDark"
                : booked
                  ? "bg-slate-200 text-slate-400 line-through cursor-not-allowed"
                  : past
                    ? "text-slate-300 cursor-not-allowed"
                    : "text-slate-700 hover:bg-shop-tealLight",
          ].join(" ");
          return (
            <button
              key={day}
              type="button"
              disabled={disabled}
              onClick={() => onSelect(d)}
              className={cls}
              title={booked ? "예약 완료" : ""}
            >
              {day}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function diffDays(a: Date, b: Date): number {
  const ms = b.getTime() - a.getTime();
  return Math.max(1, Math.round(ms / 86_400_000));
}

export function ListingDetailPage() {
  const { id } = useParams();
  const { listing, loading } = useListingDetailPoll(id);
  const add = useCart((s) => s.add);
  const [tab, setTab] = useState<TabId>("info");
  const [qty, setQty] = useState(1);
  const [variantIdx, setVariantIdx] = useState(0);
  const [guests, setGuests] = useState(2);
  const [monthCursor, setMonthCursor] = useState(() => startOfMonth(new Date()));
  const [checkIn, setCheckIn] = useState<Date | null>(null);
  const [checkOut, setCheckOut] = useState<Date | null>(null);
  const [bookedDates, setBookedDates] = useState<Set<string>>(new Set());
  const [capacity, setCapacity] = useState<number | null>(null);
  const [bookedCounts, setBookedCounts] = useState<Record<string, number>>({});
  const [reviewSummary, setReviewSummary] = useState<{ count: number; average: number }>({
    count: 0,
    average: 0,
  });
  const [photoIndex, setPhotoIndex] = useState(0);

  useEffect(() => {
    if (!listing) return;
    const needsCalendar =
      listing.kind === "lodging" || listing.category === "experience";
    if (needsCalendar) {
      void api
        .getListingBookings(listing.id)
        .then((r) => {
          setBookedDates(new Set(r.booked_dates));
          setCapacity(r.capacity);
          setBookedCounts(r.booked_counts ?? {});
        })
        .catch(() => {
          setBookedDates(new Set());
          setCapacity(null);
          setBookedCounts({});
        });
    }
    void api
      .getReviews(listing.id)
      .then((r) => setReviewSummary({ count: r.count, average: r.average }))
      .catch(() => setReviewSummary({ count: 0, average: 0 }));
  }, [listing]);

  const maxGuests = listing?.max_guests ?? 8;

  const tabCls = (t: TabId) =>
    [
      "flex-1 py-3 text-center font-semibold border-b-2 transition-colors text-sm sm:text-base",
      tab === t
        ? "border-shop-teal text-shop-tealDark bg-shop-tealLight/30"
        : "border-transparent text-hades-muted hover:text-hades-text",
    ].join(" ");

  const photoList = useMemo(() => {
    if (!listing) return [] as string[];
    const cover = listingCoverPhoto(listing);
    const extras = (listing.photos ?? []).map((p) => p.url);
    return [cover, ...extras];
  }, [listing]);

  if (loading && !listing) {
    return (
      <div className="py-20 flex flex-col items-center gap-3 text-slate-500">
        <span className="inline-block h-10 w-10 rounded-full border-2 border-shop-teal border-t-transparent animate-spin" />
        <p className="text-lg">불러오는 중…</p>
      </div>
    );
  }

  if (!listing) {
    return (
      <div className="max-w-lg mx-auto text-center py-16 space-y-4">
        <p className="text-lg text-slate-600">상품을 찾을 수 없습니다.</p>
        <Link to="/" className="btn-shop inline-block no-underline">
          목록으로
        </Link>
      </div>
    );
  }

  const isLodging = listing.kind === "lodging";
  const isExperience = listing.kind !== "lodging" && listing.category === "experience";
  // 옵션 칩 — product 에만, 2개 이상일 때만 노출.
  const variantList =
    listing.kind === "product" && (listing.variants?.length ?? 0) >= 2
      ? listing.variants!
      : null;
  const safeVariantIdx =
    variantList && variantIdx < variantList.length ? variantIdx : 0;
  const selectedVariant = variantList ? variantList[safeVariantIdx] : null;
  const effectivePrice = selectedVariant?.price ?? listing.price;
  const photo = photoList[photoIndex] ?? listingCoverPhoto(listing);
  const views = listingDemoViewCount(listing.id);
  const areaLabel = isLodging ? "숙박·민박" : isExperience ? "체험·클래스" : "특산·상품";

  // 체험: 선택한 날짜의 남은 정원 (capacity - 그날 확정 예약수).
  const selectedIso = checkIn ? toIsoDate(checkIn) : null;
  const expRemaining =
    capacity != null && selectedIso
      ? Math.max(0, capacity - (bookedCounts[selectedIso] ?? 0))
      : null;
  const expMax = expRemaining != null ? Math.max(1, expRemaining) : maxGuests;

  const ratingDisplay = reviewSummary.count > 0 ? reviewSummary.average.toFixed(1) : "—";

  const handleCalendarPick = (d: Date) => {
    if (!checkIn || (checkIn && checkOut)) {
      setCheckIn(d);
      setCheckOut(null);
      return;
    }
    if (d <= checkIn) {
      setCheckIn(d);
      return;
    }
    // 사이 날짜 중 예약된 곳이 있으면 거부
    const cur = new Date(checkIn);
    while (cur < d) {
      cur.setDate(cur.getDate() + 1);
      if (bookedDates.has(toIsoDate(cur))) {
        alert("선택한 범위에 이미 예약된 날짜가 있습니다.");
        return;
      }
    }
    setCheckOut(d);
  };

  const addLodgingToCart = () => {
    if (!checkIn || !checkOut) {
      alert("체크인·체크아웃 날짜를 선택해 주세요.");
      return;
    }
    // 숙박가는 1박 기준이므로 수량 = 박 수(인원 아님). 인원은 정원 안내용.
    const nightCount = diffDays(checkIn, checkOut);
    add(listing.id, Math.max(1, nightCount), {
      stay_start: toIsoDate(checkIn),
      stay_end: toIsoDate(checkOut),
    });
  };

  const addExperience = () => {
    if (!checkIn) {
      alert("체험 날짜를 선택해 주세요.");
      return;
    }
    if (expRemaining != null && guests > expRemaining) {
      alert(`이 날짜는 남은 자리가 ${expRemaining}명입니다.`);
      return;
    }
    // 체험은 단일 날짜 예약 — stay_start == stay_end, 수량 = 인원.
    add(listing.id, Math.max(1, guests), {
      stay_start: toIsoDate(checkIn),
      stay_end: toIsoDate(checkIn),
    });
  };

  const nights = checkIn && checkOut ? diffDays(checkIn, checkOut) : 0;

  return (
    <div className="page-shell py-8 sm:py-10 pb-16 sm:pb-24 space-y-6">
      <nav className="text-sm text-slate-500 flex flex-wrap items-center gap-2">
        <Link to="/" className="text-shop-teal hover:underline font-medium">
          홈
        </Link>
        <span className="text-slate-300">/</span>
        <span className="text-slate-600">{areaLabel}</span>
        <span className="text-slate-300">/</span>
        <span className="text-slate-800 font-medium line-clamp-1">{listing.title}</span>
      </nav>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-8 lg:gap-10 items-start">
        <div>
          <div className="relative rounded-3xl border border-slate-200/90 overflow-hidden shadow-xl bg-slate-900">
            <div className="relative aspect-[4/3] sm:aspect-[16/10]">
              <img
                src={photo}
                alt=""
                className="absolute inset-0 h-full w-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-slate-900/25" />
            </div>
            <div className="absolute top-4 left-4 flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-white/95 px-3 py-1 text-xs font-bold text-slate-800 shadow">
                {listing.location}
              </span>
              <span className="rounded-full bg-black/45 text-white px-3 py-1 text-xs font-semibold backdrop-blur-md">
                {areaLabel}
              </span>
              <span
                className="rounded-full bg-white/90 w-9 h-9 flex items-center justify-center text-lg shadow"
                aria-hidden
              >
                {listing.emoji}
              </span>
            </div>
            {photoList.length > 1 && (
              <div className="absolute bottom-4 left-0 right-0 flex justify-center gap-2">
                {photoList.map((_, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setPhotoIndex(i)}
                    className={`h-1.5 rounded-full transition-all ${
                      i === photoIndex ? "w-7 bg-white" : "w-1.5 bg-white/60"
                    }`}
                    aria-label={`${i + 1}번째 사진`}
                  />
                ))}
              </div>
            )}
          </div>

          {photoList.length > 1 && (
            <ul className="mt-3 flex gap-2 overflow-x-auto pb-1">
              {photoList.map((src, i) => (
                <li key={`${src}-${i}`} className="shrink-0">
                  <button
                    type="button"
                    onClick={() => setPhotoIndex(i)}
                    className={`block w-20 h-20 rounded-lg overflow-hidden border-2 transition-colors ${
                      i === photoIndex ? "border-shop-teal" : "border-transparent"
                    }`}
                  >
                    <img src={src} alt="" className="w-full h-full object-cover" />
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
            <div className="flex flex-wrap items-center gap-3 text-slate-600">
              <span className="font-semibold text-amber-600 tabular-nums">★ {ratingDisplay}</span>
              <span className="text-slate-400">·</span>
              <button
                type="button"
                className="text-shop-tealDark font-medium hover:underline"
                onClick={() => setTab("reviews")}
              >
                리뷰 {reviewSummary.count}
              </button>
              <span className="text-slate-400">·</span>
              <span className="text-slate-500 tabular-nums">조회 {views.toLocaleString()}</span>
            </div>
            <button
              type="button"
              className="text-slate-400 hover:text-slate-600 text-sm"
              title="준비 중"
              disabled
            >
              공유
            </button>
          </div>

          <div className="mt-2 flex border border-brand-line bg-white rounded-t-2xl overflow-hidden shadow-soft">
            <button type="button" className={tabCls("info")} onClick={() => setTab("info")}>
              상품 정보
            </button>
            <button type="button" className={tabCls("guide")} onClick={() => setTab("guide")}>
              이용 안내
            </button>
            <button type="button" className={tabCls("reviews")} onClick={() => setTab("reviews")}>
              리뷰 {reviewSummary.count > 0 ? `(${reviewSummary.count})` : ""}
            </button>
          </div>

          <div className="rounded-b-2xl border border-t-0 border-brand-line bg-white p-6 sm:p-8 pb-10 sm:pb-12 shadow-soft overflow-visible">
            {tab === "info" && (
              <div className="space-y-6 sm:space-y-8">
                <p className="text-sm font-semibold text-shop-tealDark">
                  {areaLabel} · {listing.location}
                </p>
                <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 leading-snug tracking-tight">
                  {listing.title}
                </h1>
                <p className="text-3xl sm:text-4xl font-bold text-shop-tealDark tabular-nums">
                  {effectivePrice.toLocaleString()}
                  <span className="text-2xl font-bold">원</span>
                  {selectedVariant ? (
                    <span className="text-lg sm:text-xl font-semibold text-slate-500">
                      {" "}
                      / {selectedVariant.label}
                    </span>
                  ) : null}
                  {isLodging && (
                    <span className="text-lg sm:text-xl font-semibold text-slate-500">
                      {" "}
                      / 1박 기준
                    </span>
                  )}
                  {isExperience && (
                    <span className="text-lg sm:text-xl font-semibold text-slate-500">
                      {" "}
                      / 1인 기준
                    </span>
                  )}
                </p>
                <ListingInfoSections listing={listing} />
              </div>
            )}
            {tab === "guide" && (
              <div className="space-y-8 sm:space-y-10 overflow-visible">
                <ListingUsageGuideSections guide={listing.guide} listing={listing} />
                <ListingLocalGuide listing={listing} />
              </div>
            )}
            {tab === "reviews" && <ReviewSection listingId={listing.id} />}
          </div>
        </div>

        <aside className="lg:sticky lg:top-24 rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xl shadow-slate-200/50 space-y-5">
          <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-4">
            <p className="text-sm font-semibold text-slate-800">예약 · 구매</p>
            <button
              type="button"
              disabled
              className="text-sm text-slate-400 cursor-not-allowed"
              title="찜하기는 준비 중"
            >
              ♡ 찜
            </button>
          </div>

          {isLodging ? (
            <>
              <div className="flex items-center justify-between gap-2">
                <button
                  type="button"
                  className="btn-shop-outline px-3 py-2 text-sm"
                  onClick={() =>
                    setMonthCursor(
                      new Date(monthCursor.getFullYear(), monthCursor.getMonth() - 1, 1)
                    )
                  }
                >
                  이전
                </button>
                <button
                  type="button"
                  className="btn-shop-outline px-3 py-2 text-sm"
                  onClick={() =>
                    setMonthCursor(
                      new Date(monthCursor.getFullYear(), monthCursor.getMonth() + 1, 1)
                    )
                  }
                >
                  다음
                </button>
              </div>
              <MonthCalendar
                month={monthCursor}
                checkIn={checkIn}
                checkOut={checkOut}
                bookedDates={bookedDates}
                onSelect={handleCalendarPick}
              />
              <div className="text-sm rounded-xl border border-slate-200 bg-slate-50/60 p-3 space-y-1">
                <p>
                  체크인:{" "}
                  <strong>{checkIn ? toIsoDate(checkIn) : "선택"}</strong>
                </p>
                <p>
                  체크아웃:{" "}
                  <strong>{checkOut ? toIsoDate(checkOut) : "선택"}</strong>
                </p>
                {nights > 0 && (
                  <p className="text-shop-tealDark font-bold">
                    {nights}박 · {(listing.price * nights).toLocaleString()}원
                  </p>
                )}
              </div>
              <p className="text-xs text-slate-500 leading-snug">
                회색 날짜는 이미 예약되었습니다. 첫 클릭이 체크인, 두 번째 클릭이 체크아웃입니다.
              </p>

              <div>
                <p className="text-sm font-semibold text-slate-700 mb-2">인원 선택</p>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    className="w-11 h-11 rounded-xl border border-slate-200 font-bold text-lg hover:bg-slate-50"
                    onClick={() => setGuests((g) => Math.max(1, g - 1))}
                  >
                    −
                  </button>
                  <span className="flex-1 text-center text-xl font-bold">{guests}명</span>
                  <button
                    type="button"
                    className="w-11 h-11 rounded-xl border border-slate-200 font-bold text-lg hover:bg-slate-50"
                    onClick={() => setGuests((g) => Math.min(maxGuests, g + 1))}
                  >
                    +
                  </button>
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  최대 {maxGuests}명까지 가능합니다.
                </p>
              </div>

              <button
                type="button"
                className="btn-shop w-full text-lg py-4 rounded-xl"
                onClick={addLodgingToCart}
              >
                예약하기
              </button>
            </>
          ) : isExperience ? (
            <>
              <div className="flex items-center justify-between gap-2">
                <button
                  type="button"
                  className="btn-shop-outline px-3 py-2 text-sm"
                  onClick={() =>
                    setMonthCursor(
                      new Date(monthCursor.getFullYear(), monthCursor.getMonth() - 1, 1)
                    )
                  }
                >
                  이전
                </button>
                <button
                  type="button"
                  className="btn-shop-outline px-3 py-2 text-sm"
                  onClick={() =>
                    setMonthCursor(
                      new Date(monthCursor.getFullYear(), monthCursor.getMonth() + 1, 1)
                    )
                  }
                >
                  다음
                </button>
              </div>
              <MonthCalendar
                month={monthCursor}
                checkIn={checkIn}
                checkOut={checkIn}
                bookedDates={bookedDates}
                onSelect={(d) => {
                  setCheckIn(d);
                  setCheckOut(d);
                  if (capacity != null) {
                    const rem = Math.max(1, capacity - (bookedCounts[toIsoDate(d)] ?? 0));
                    setGuests((g) => Math.min(g, rem));
                  }
                }}
              />
              <div className="text-sm rounded-xl border border-slate-200 bg-slate-50/60 p-3 space-y-1">
                <p>
                  체험일: <strong>{checkIn ? toIsoDate(checkIn) : "날짜 선택"}</strong>
                </p>
                {capacity != null ? (
                  <p className="text-shop-tealDark font-semibold">
                    정원 {capacity}명
                    {expRemaining != null ? ` · 남은 자리 ${expRemaining}명` : ""}
                  </p>
                ) : null}
              </div>
              <p className="text-xs text-slate-500 leading-snug">
                원하는 체험 날짜를 선택하세요. 회색은 마감(정원 초과)·지난 날짜입니다.
              </p>

              <div>
                <p className="text-sm font-semibold text-slate-700 mb-2">인원 선택</p>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    className="w-11 h-11 rounded-xl border border-slate-200 font-bold text-lg hover:bg-slate-50"
                    onClick={() => setGuests((g) => Math.max(1, g - 1))}
                  >
                    −
                  </button>
                  <span className="flex-1 text-center text-xl font-bold">{guests}명</span>
                  <button
                    type="button"
                    className="w-11 h-11 rounded-xl border border-slate-200 font-bold text-lg hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
                    disabled={guests >= expMax}
                    onClick={() => setGuests((g) => Math.min(expMax, g + 1))}
                  >
                    +
                  </button>
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  1인 {listing.price.toLocaleString()}원 · 총{" "}
                  <strong className="text-shop-tealDark">
                    {(listing.price * guests).toLocaleString()}원
                  </strong>
                </p>
              </div>

              <button
                type="button"
                className="btn-shop w-full text-lg py-4 rounded-xl"
                onClick={addExperience}
              >
                예약하기
              </button>
            </>
          ) : (
            <>
              {variantList ? (
                <div>
                  <p className="text-sm font-semibold text-slate-700 mb-2">
                    용량을 골라 주세요
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {variantList.map((v, i) => {
                      const active = i === safeVariantIdx;
                      return (
                        <button
                          key={`${v.label}-${i}`}
                          type="button"
                          onClick={() => setVariantIdx(i)}
                          className={[
                            "px-4 py-2.5 rounded-xl border-2 text-sm font-semibold transition-colors",
                            active
                              ? "border-shop-teal bg-shop-teal/10 text-shop-tealDark shadow-sm"
                              : "border-slate-200 bg-white text-slate-600 hover:border-slate-300",
                          ].join(" ")}
                        >
                          <span>{v.label}</span>
                          <span className="ml-2 tabular-nums text-xs text-slate-500">
                            {v.price.toLocaleString()}원
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : null}
              <div>
                <p className="text-sm font-semibold text-slate-700 mb-2">수량</p>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    className="w-11 h-11 rounded-xl border border-slate-200 font-bold text-lg hover:bg-slate-50"
                    onClick={() => setQty((q) => Math.max(1, q - 1))}
                  >
                    −
                  </button>
                  <span className="flex-1 text-center text-xl font-bold">{qty}</span>
                  <button
                    type="button"
                    className="w-11 h-11 rounded-xl border border-slate-200 font-bold text-lg hover:bg-slate-50"
                    onClick={() => setQty((q) => q + 1)}
                  >
                    +
                  </button>
                </div>
                {listing.stock != null && (
                  <p className="text-xs text-slate-500 mt-2">현재 수량 {listing.stock}</p>
                )}
                {variantList ? (
                  <p className="text-xs text-slate-500 mt-1.5">
                    합계{" "}
                    <strong className="text-shop-tealDark">
                      {(effectivePrice * qty).toLocaleString()}원
                    </strong>
                  </p>
                ) : null}
              </div>
              <button
                type="button"
                className="btn-shop w-full text-lg py-4 rounded-xl"
                onClick={() =>
                  add(listing.id, qty, selectedVariant
                    ? {
                        variant_label: selectedVariant.label,
                        variant_price: selectedVariant.price,
                      }
                    : undefined)
                }
              >
                장바구니에 담기
              </button>
            </>
          )}

          <Link
            to="/checkout"
            className="block text-center btn-shop-outline py-3 no-underline w-full rounded-xl"
          >
            장바구니로 이동
          </Link>
        </aside>
      </div>
    </div>
  );
}
