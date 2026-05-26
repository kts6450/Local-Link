import { useCallback, useEffect, useMemo, useState } from "react";

import { PageHeader } from "../../components/ui/PageHeader";
import { api } from "../../lib/api";
import { useAuthSellerId } from "../../store/auth";
import type { Listing } from "../../types";

/** SNS는 쇼핑몰에 안 붙고, 공급자가 인스타·페이스북에 직접 올리는 용도 */
export function SellerSnsPage() {
  const sellerId = useAuthSellerId();
  const [listings, setListings] = useState<Listing[]>([]);
  const [pickId, setPickId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null);
  const [copied, setCopied] = useState(false);

  const myListings = useMemo(
    () => (sellerId ? listings.filter((l) => l.seller_id === sellerId) : listings),
    [listings, sellerId]
  );

  const reload = useCallback(
    () => api.getListings().then(setListings).catch(() => setListings([])),
    []
  );

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (myListings.length === 0) {
      setPickId("");
      return;
    }
    if (!pickId || !myListings.some((l) => l.id === pickId)) {
      setPickId(myListings[0].id);
    }
  }, [myListings, pickId]);

  const picked = myListings.find((l) => l.id === pickId);

  const instagramText = draft
    ? [String(draft.instagram ?? ""), String(draft.hashtags ?? "")].filter(Boolean).join("\n\n")
    : "";

  const generate = async () => {
    if (!picked) {
      setError("먼저 «상품 등록»에서 글을 올려 주세요.");
      return;
    }
    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      const r = await api.sellerSnsDraft({
        kind: picked.kind,
        title: picked.title,
        description: picked.description,
        price: picked.price,
        location: picked.location,
      });
      setDraft(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "SNS 초안을 만들지 못했습니다.");
    } finally {
      setBusy(false);
    }
  };

  const copyInstagram = async () => {
    if (!instagramText) return;
    try {
      await navigator.clipboard.writeText(instagramText);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      setError("복사에 실패했습니다. 아래 글을 직접 선택해 복사해 주세요.");
    }
  };

  return (
    <div className="space-y-8 max-w-3xl">
      <PageHeader badge="공급자" title="SNS 홍보">
        만든 글은 인스타·페이스북 등에 <strong>직접 붙여 넣는</strong> 용도이며, 쇼핑몰에는
        올라가지 않습니다.
      </PageHeader>

      <ol className="card p-5 space-y-3 text-sm text-hades-text list-decimal list-inside">
        <li>홍보할 상품을 고릅니다.</li>
        <li>«인스타용 글 만들기»를 누릅니다.</li>
        <li>«복사하기» 후 인스타그램 앱 → 새 게시물에 붙여 넣습니다.</li>
        <li>쇼핑몰 링크는 프로필·댓글에 안내하면 됩니다.</li>
      </ol>

      {myListings.length === 0 ? (
        <p className="text-amber-800 bg-amber-50 border border-amber-200 rounded-xl p-4">
          등록된 상품이 없습니다. «상품 등록» 메뉴에서 먼저 올려 주세요.
        </p>
      ) : (
        <>
          <label className="block">
            <span className="text-sm font-semibold text-slate-700">홍보할 상품</span>
            <select
              className="mt-1 w-full rounded-xl border border-slate-200 px-4 py-3 text-lg"
              value={pickId}
              onChange={(e) => setPickId(e.target.value)}
            >
              {myListings.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.emoji} {l.title} — {l.price.toLocaleString()}원
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            className="btn-primary w-full sm:w-auto px-8 py-3"
            disabled={busy}
            onClick={() => void generate()}
          >
            {busy ? "작성 중…" : "인스타용 글 만들기"}
          </button>

          {error && (
            <p className="text-sm text-red-800 bg-red-50 border border-red-100 rounded-xl px-4 py-2">
              {error}
            </p>
          )}

          {draft && (
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-bold text-lg">인스타그램·스레드용</h2>
                <button
                  type="button"
                  className="btn-primary py-2 px-5"
                  onClick={() => void copyInstagram()}
                >
                  {copied ? "복사됨 ✓" : "복사하기"}
                </button>
              </div>
              <pre className="text-sm whitespace-pre-wrap bg-slate-50 rounded-xl p-4 border border-slate-100">
                {instagramText}
              </pre>
              {draft.facebook ? (
                <>
                  <h3 className="font-semibold text-slate-800 pt-2">페이스북용 (짧게)</h3>
                  <pre className="text-sm whitespace-pre-wrap bg-slate-50 rounded-xl p-4 border border-slate-100">
                    {String(draft.facebook)}
                  </pre>
                </>
              ) : null}
            </section>
          )}
        </>
      )}
    </div>
  );
}
