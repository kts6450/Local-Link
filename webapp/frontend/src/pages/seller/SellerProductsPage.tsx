import { FormEvent, useCallback, useEffect, useState } from "react";

import { PageHeader } from "../../components/ui/PageHeader";
import { SellerStepIndicator } from "../../components/seller/SellerStepIndicator";
import { SellerVoicePanel } from "../../components/seller/SellerVoicePanel";
import { api } from "../../lib/api";
import {
  LISTING_CATEGORIES,
  categoryLabel,
  type ListingCategory,
} from "../../lib/sellerSectors";
import { useListingsStreamVersion } from "../../hooks/useListingsStreamVersion";
import {
  useAuthDisplayName,
  useAuthSellerId,
  useAuthSellerSector,
} from "../../store/auth";
import { useConversation } from "../../store/conversation";
import { useSellerFormVoice } from "../../store/sellerFormVoice";
import type { Listing, ListingGuide } from "../../types";

const STEP_BANNERS: Record<number, { emoji: string; title: string; sub: string; img: string }> = {
  1: {
    emoji: "📝",
    title: "무엇을 올릴까요?",
    sub: "종류·이름·가격·동네만 적으면 됩니다",
    img: "https://images.unsplash.com/photo-1464226184884-fa280b87c399?auto=format&fit=crop&w=800&q=80",
  },
  2: {
    emoji: "✨",
    title: "소개 글 · 이용 안내",
    sub: "AI가 대신 써 드릴 수 있어요 — 말로 「AI로 글 써줘」도 됩니다",
    img: "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=800&q=80",
  },
  3: {
    emoji: "📷",
    title: "사진 올리기",
    sub: "대표 사진 하나 + 더 보여 줄 사진 (최대 10장)",
    img: "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?auto=format&fit=crop&w=800&q=80",
  },
  4: {
    emoji: "✅",
    title: "마지막 확인",
    sub: "수량만 확인하고 올리면 쇼핑에 보입니다",
    img: "https://images.unsplash.com/photo-1556745750-677886ec5f35?auto=format&fit=crop&w=800&q=80",
  },
};

export function SellerProductsPage() {
  const sellerSector = useAuthSellerSector();
  const sellerId = useAuthSellerId();
  const displayName = useAuthDisplayName();
  const streamTick = useListingsStreamVersion();
  const registerVoice = useSellerFormVoice((s) => s.register);
  const unregisterVoice = useSellerFormVoice((s) => s.unregister);

  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState(1);
  const listingSubmitted = useConversation((s) => s.listingSubmitted);
  const setListingSubmitted = useConversation((s) => s.setListingSubmitted);
  const slots = useConversation((s) => s.slots);

  const [kind, setKind] = useState<"product" | "lodging">("product");
  const [category, setCategory] = useState<ListingCategory>(sellerSector ?? "rural");
  const [title, setTitle] = useState("");
  const [price, setPrice] = useState("");
  const [description, setDescription] = useState("");
  const [guide, setGuide] = useState<ListingGuide | null>(null);
  const [location, setLocation] = useState("");
  const [stock, setStock] = useState("10");
  const [maxGuests, setMaxGuests] = useState("4");
  const [busy, setBusy] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [coverDataUrl, setCoverDataUrl] = useState<string | null>(null);
  const [extraPhotos, setExtraPhotos] = useState<string[]>([]);
  const [imagePromptKo, setImagePromptKo] = useState("");
  const [imagePromptEn, setImagePromptEn] = useState("");
  const [promptSummary, setPromptSummary] = useState<string | null>(null);
  const [aiHint, setAiHint] = useState<string | null>(null);

  const reload = useCallback(
    () => api.getListings().then(setListings).catch(() => setListings([])),
    []
  );

  const fillPackageAi = useCallback(async () => {
    const t = title.trim();
    const p = parseInt(price, 10) || 0;
    if (!t) {
      setAiHint("먼저 1단계에서 이름을 적어 주세요.");
      setStep(1);
      return;
    }
    setAiBusy(true);
    setAiHint(null);
    try {
      const r = await api.draftListingPackage({
        kind,
        title: t,
        price: p,
        location: location.trim(),
        category: kind === "lodging" && category !== "lodging" ? "lodging" : category,
      });
      setDescription(r.description);
      setGuide(r.guide);
      setStep(2);
      setAiHint("소개 글과 이용 안내를 채웠어요. 내용을 보시고 고치셔도 됩니다.");
    } catch (e) {
      setAiHint(e instanceof Error ? e.message : "글을 만들지 못했어요.");
    } finally {
      setAiBusy(false);
    }
  }, [kind, title, price, location, category]);

  const fillDescriptionAi = useCallback(async () => {
    const t = title.trim();
    const p = parseInt(price, 10) || 0;
    if (!t) {
      setAiHint("먼저 1단계에서 이름을 적어 주세요.");
      setStep(1);
      return;
    }
    setAiBusy(true);
    setAiHint(null);
    try {
      const r = await api.draftListingDescription({
        kind,
        title: t,
        price: p,
        location: location.trim(),
      });
      setDescription(r.description);
      setStep(2);
      setAiHint("짧은 소개만 채웠어요.");
    } catch (e) {
      setAiHint(e instanceof Error ? e.message : "글을 만들지 못했어요.");
    } finally {
      setAiBusy(false);
    }
  }, [kind, title, price, location]);

  const generateCoverAi = useCallback(async () => {
    const t = title.trim();
    if (!t) {
      setAiHint("먼저 1단계에서 이름을 적어 주세요.");
      setStep(1);
      return;
    }
    setAiBusy(true);
    setAiHint(null);
    try {
      let promptEn = imagePromptEn.trim();
      if (!promptEn) {
        const enhanced = await api.enhanceImagePrompt({
          kind,
          title: t,
          location: location.trim(),
          category,
          description: description.trim(),
          user_hint: imagePromptKo.trim(),
        });
        promptEn = enhanced.prompt_en;
        setImagePromptEn(promptEn);
        setPromptSummary(enhanced.summary_ko);
      }
      const r = await api.draftListingImage({
        kind,
        title: t,
        location: location.trim(),
        category,
        description: description.trim(),
        prompt_en: promptEn,
      });
      setCoverDataUrl(`data:${r.mime_type};base64,${r.image_base64}`);
      setStep(3);
      setAiHint("대표 사진을 만들었어요.");
    } catch (e) {
      setAiHint(e instanceof Error ? e.message : "사진을 만들지 못했어요.");
    } finally {
      setAiBusy(false);
    }
  }, [
    kind,
    title,
    location,
    category,
    description,
    imagePromptEn,
    imagePromptKo,
  ]);

  const voiceAiWrite = useCallback(async () => {
    const hist = useConversation.getState().history;
    const lastUser = [...hist].reverse().find((m) => m.role === "user")?.content ?? "";
    if (/짧게|설명만/i.test(lastUser)) {
      await fillDescriptionAi();
    } else {
      await fillPackageAi();
    }
  }, [fillPackageAi, fillDescriptionAi]);

  useEffect(() => {
    registerVoice({
      onAiWrite: voiceAiWrite,
      onAiImage: generateCoverAi,
    });
    return () => unregisterVoice();
  }, [registerVoice, unregisterVoice, voiceAiWrite, generateCoverAi]);

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, [reload]);

  useEffect(() => {
    if (listingSubmitted) reload();
  }, [listingSubmitted, reload]);

  useEffect(() => {
    void reload();
  }, [streamTick, reload]);

  useEffect(() => {
    if (sellerSector) setCategory(sellerSector);
  }, [sellerSector]);

  useEffect(() => {
    if (slots.kind === "product" || slots.kind === "lodging") {
      setKind(slots.kind);
      if (slots.kind === "lodging") setCategory("lodging");
    }
    if (typeof slots.title === "string" && slots.title.trim()) setTitle(slots.title.trim());
    if (typeof slots.price === "number" && slots.price >= 0) setPrice(String(slots.price));
    if (typeof slots.location === "string" && slots.location.trim()) {
      setLocation(slots.location.trim());
    }
    if (typeof slots.description === "string" && slots.description.trim()) {
      setDescription(slots.description.trim());
    }
    if (slots.kind === "product" && typeof slots.stock === "number") {
      setStock(String(slots.stock));
    }
    if (slots.kind === "lodging" && typeof slots.max_guests === "number") {
      setMaxGuests(String(slots.max_guests));
    }
  }, [slots]);

  const onPickExtraPhotos = async (files: FileList | null) => {
    if (!files?.length) return;
    const reads: Promise<string>[] = [];
    Array.from(files)
      .slice(0, 8)
      .forEach((f) => {
        if (!f.type.startsWith("image/")) return;
        reads.push(
          new Promise((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(String(r.result || ""));
            r.onerror = () => reject(new Error("read fail"));
            r.readAsDataURL(f);
          })
        );
      });
    try {
      const urls = await Promise.all(reads);
      setExtraPhotos((prev) => [...prev, ...urls].slice(0, 10));
    } catch {
      /* */
    }
  };

  const onSubmit = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!title.trim()) {
      setAiHint("이름을 적어 주세요.");
      setStep(1);
      return;
    }
    setBusy(true);
    try {
      const created = await api.createListing({
        kind,
        category: kind === "lodging" && category !== "lodging" ? "lodging" : category,
        seller_id: sellerId ?? undefined,
        title: title.trim(),
        description: description.trim(),
        price: Math.max(0, parseInt(price, 10) || 0),
        location: location.trim(),
        stock: kind === "product" ? Math.max(0, parseInt(stock, 10) || 0) : null,
        max_guests:
          kind === "lodging" ? Math.max(1, parseInt(maxGuests, 10) || 4) : null,
        cover_image_base64: coverDataUrl
          ? coverDataUrl.includes(",")
            ? coverDataUrl.split(",", 2)[1]
            : coverDataUrl
          : undefined,
        guide: guide ?? undefined,
      });
      for (const data of extraPhotos) {
        const b64 = data.includes(",") ? data.split(",", 2)[1] : data;
        try {
          await api.addListingPhoto(created.id, { image_base64: b64 });
        } catch {
          /* */
        }
      }
      setTitle("");
      setPrice("");
      setDescription("");
      setGuide(null);
      setLocation("");
      setCoverDataUrl(null);
      setExtraPhotos([]);
      setImagePromptKo("");
      setImagePromptEn("");
      setPromptSummary(null);
      setAiHint(null);
      setStep(1);
      await reload();
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    if (!confirm("이 글을 내릴까요?")) return;
    try {
      await api.deleteListing(id);
      await reload();
    } catch {
      /* */
    }
  };

  const canNextStep1 = title.trim() && price.trim();
  const banner = STEP_BANNERS[step] ?? STEP_BANNERS[1];
  const myListings = sellerId ? listings.filter((r) => r.seller_id === sellerId) : listings;

  return (
    <div className="space-y-8">
      {listingSubmitted && (
        <div className="rounded-2xl border border-shop-teal/30 bg-shop-tealLight/60 p-5 flex flex-wrap items-center justify-between gap-3">
          <p className="font-semibold text-shop-tealDark">
            음성으로 등록이 끝났어요. 아래 목록을 확인해 보세요.
          </p>
          <button
            type="button"
            className="btn-ghost text-shop-tealDark border-shop-teal/30"
            onClick={() => setListingSubmitted(false)}
          >
            닫기
          </button>
        </div>
      )}

      <PageHeader badge="공급자" title="물건 올리기">
        {displayName}님 · 주 업종{" "}
        <strong>{categoryLabel(sellerSector ?? "rural")}</strong>
      </PageHeader>

      <SellerStepIndicator current={step} onGo={setStep} />

      <section className="rounded-3xl border border-slate-200/90 bg-white shadow-lg overflow-hidden">
        <div className="relative h-28 sm:h-32 overflow-hidden">
          <img src={banner.img} alt="" className="absolute inset-0 w-full h-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-r from-shop-tealDark/90 via-shop-teal/75 to-transparent" />
          <div className="relative h-full flex items-center gap-4 px-6 sm:px-8 text-white">
            <span className="text-4xl sm:text-5xl" aria-hidden>
              {banner.emoji}
            </span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide opacity-90">
                {step}단계 / 4단계
              </p>
              <h2 className="text-xl sm:text-2xl font-bold">{banner.title}</h2>
              <p className="text-sm opacity-90 mt-0.5">{banner.sub}</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-[minmax(280px,340px)_1fr] gap-0 xl:gap-0">
          <div className="border-b xl:border-b-0 xl:border-r border-slate-100 p-5 sm:p-6 bg-slate-50/50">
            <SellerVoicePanel step={step} />
          </div>

          <div className="p-5 sm:p-8">
            {aiHint && (
              <p className="mb-4 text-sm text-amber-900 bg-amber-50 border border-amber-100 rounded-xl px-4 py-3">
                {aiHint}
              </p>
            )}

            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (step < 4) setStep(step + 1);
                else void onSubmit(e);
              }}
              className="space-y-5"
            >
              {step === 1 && (
                <div className="space-y-4 animate-fade-in">
                  <div>
                    <label className="label-step">파는 것</label>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setKind("product")}
                        className={kind === "product" ? "btn-primary flex-1 py-3" : "btn-ghost flex-1 py-3"}
                      >
                        🛒 물건
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setKind("lodging");
                          setCategory("lodging");
                        }}
                        className={kind === "lodging" ? "btn-primary flex-1 py-3" : "btn-ghost flex-1 py-3"}
                      >
                        🏠 숙박
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="label-step">쇼핑 메뉴</label>
                    <select
                      className="input-field text-lg"
                      value={category}
                      onChange={(e) => setCategory(e.target.value as ListingCategory)}
                    >
                      {LISTING_CATEGORIES.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="label-step">이름</label>
                    <input
                      className="input-field text-lg"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      required
                      placeholder="예: 올해 햅쌀 10kg"
                    />
                  </div>
                  <div>
                    <label className="label-step">가격 (원)</label>
                    <input
                      className="input-field text-lg"
                      inputMode="numeric"
                      value={price}
                      onChange={(e) => setPrice(e.target.value.replace(/\D/g, ""))}
                      required
                      placeholder="42000"
                    />
                  </div>
                  <div>
                    <label className="label-step">동네 (시·군)</label>
                    <input
                      className="input-field text-lg"
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                      placeholder="전북 김제시"
                    />
                  </div>
                </div>
              )}

              {step === 2 && (
                <div className="space-y-4">
                  <div>
                    <label className="label-step">소개 글</label>
                    <textarea
                      className="input-field text-lg min-h-[140px]"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="어떤 물건인지, 왜 좋은지 적어 주세요."
                    />
                  </div>
                  <div className="rounded-2xl border border-violet-100 bg-violet-50/50 p-4 space-y-3">
                    <p className="font-semibold text-slate-800">AI 도움</p>
                    <p className="text-sm text-slate-600">
                      버튼을 누르거나, 왼쪽에서 「AI로 글 써줘」라고 말씀하세요.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="btn-primary py-2.5 px-4"
                        disabled={busy || aiBusy}
                        onClick={() => void fillPackageAi()}
                      >
                        {aiBusy ? "만드는 중…" : "소개 + 이용안내 한번에"}
                      </button>
                      <button
                        type="button"
                        className="btn-ghost py-2.5 px-4 border-violet-200"
                        disabled={busy || aiBusy}
                        onClick={() => void fillDescriptionAi()}
                      >
                        소개만 짧게
                      </button>
                    </div>
                    {guide ? (
                      <p className="text-sm text-shop-tealDark bg-white rounded-lg px-3 py-2 border border-shop-teal/20">
                        이용 안내 준비됨 · 포인트 {(guide.highlights ?? []).length}개 · 순서{" "}
                        {(guide.steps ?? []).length}단계
                      </p>
                    ) : null}
                  </div>
                </div>
              )}

              {step === 3 && (
                <div className="space-y-4">
                  <div className="rounded-2xl border border-sky-100 bg-sky-50/50 p-4 space-y-3">
                    <p className="font-semibold text-slate-800">대표 사진</p>
                    <p className="text-sm text-slate-600">
                      「사진 만들어 줘」라고 말씀하거나 버튼을 누르세요.
                    </p>
                    <div>
                      <label className="text-sm text-slate-600">어떤 장면? (선택)</label>
                      <input
                        className="input-field mt-1"
                        value={imagePromptKo}
                        onChange={(e) => setImagePromptKo(e.target.value)}
                        placeholder="예: 밭에서 수확하는 모습"
                      />
                    </div>
                    <button
                      type="button"
                      className="btn-primary py-2.5 px-4"
                      disabled={busy || aiBusy}
                      onClick={() => void generateCoverAi()}
                    >
                      {aiBusy ? "그리는 중…" : "AI로 대표 사진 만들기"}
                    </button>
                    {promptSummary ? (
                      <p className="text-sm text-shop-tealDark">{promptSummary}</p>
                    ) : null}
                    {coverDataUrl ? (
                      <div className="rounded-xl overflow-hidden border max-w-sm">
                        <img src={coverDataUrl} alt="대표 사진" className="w-full aspect-[16/10] object-cover" />
                        <button
                          type="button"
                          className="w-full py-2 text-sm text-red-600 bg-white border-t"
                          onClick={() => setCoverDataUrl(null)}
                        >
                          사진 지우기
                        </button>
                      </div>
                    ) : (
                      <div className="rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 h-40 flex items-center justify-center text-slate-400">
                        아직 대표 사진 없음
                      </div>
                    )}
                  </div>
                  <div>
                    <label className="label-step">더 보여 줄 사진 (선택, 최대 10장)</label>
                    <input
                      type="file"
                      accept="image/*"
                      multiple
                      onChange={(e) => void onPickExtraPhotos(e.target.files)}
                      className="block w-full text-sm file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border file:border-shop-teal/30 file:bg-shop-tealLight file:font-semibold"
                    />
                    {extraPhotos.length > 0 && (
                      <ul className="mt-3 flex flex-wrap gap-2">
                        {extraPhotos.map((src, i) => (
                          <li key={i} className="relative">
                            <img src={src} alt="" className="w-20 h-20 object-cover rounded-lg border" />
                            <button
                              type="button"
                              className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-rose-600 text-white text-xs font-bold"
                              onClick={() => setExtraPhotos((p) => p.filter((_, j) => j !== i))}
                            >
                              ×
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              )}

              {step === 4 && (
                <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-5">
                  <h3 className="font-bold text-lg">올리기 전에 확인</h3>
                  <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm sm:text-base">
                    <dt className="text-slate-500">종류</dt>
                    <dd>{kind === "product" ? "물건" : "숙박"}</dd>
                    <dt className="text-slate-500">이름</dt>
                    <dd className="font-semibold">{title || "—"}</dd>
                    <dt className="text-slate-500">가격</dt>
                    <dd>{price ? `${Number(price).toLocaleString()}원` : "—"}</dd>
                    <dt className="text-slate-500">동네</dt>
                    <dd>{location || "—"}</dd>
                    <dt className="text-slate-500">사진</dt>
                    <dd>{coverDataUrl ? "대표 있음" : "없음 (나중에 추가 가능)"}</dd>
                  </dl>
                  {kind === "product" ? (
                    <div>
                      <label className="label-step">남은 개수</label>
                      <input
                        className="input-field"
                        inputMode="numeric"
                        value={stock}
                        onChange={(e) => setStock(e.target.value.replace(/\D/g, ""))}
                      />
                    </div>
                  ) : (
                    <div>
                      <label className="label-step">최대 몇 명</label>
                      <input
                        className="input-field"
                        inputMode="numeric"
                        value={maxGuests}
                        onChange={(e) => setMaxGuests(e.target.value.replace(/\D/g, ""))}
                      />
                    </div>
                  )}
                </div>
              )}

              <div className="flex flex-wrap gap-3 pt-4 border-t border-slate-100">
                {step > 1 && (
                  <button
                    type="button"
                    className="btn-ghost px-6 py-3"
                    onClick={() => setStep(step - 1)}
                  >
                    ← 이전
                  </button>
                )}
                {step < 4 ? (
                  <button
                    type="submit"
                    className="btn-primary flex-1 py-3 text-lg"
                    disabled={step === 1 && !canNextStep1}
                  >
                    다음 →
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn-primary flex-1 py-3 text-lg"
                    disabled={busy || aiBusy}
                    onClick={() => void onSubmit()}
                  >
                    {busy ? "올리는 중…" : "쇼핑에 올리기"}
                  </button>
                )}
              </div>
            </form>
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white overflow-hidden shadow-md">
        <div className="px-6 py-4 border-b bg-slate-50/80">
          <h2 className="text-xl font-bold">지금 판매 중</h2>
        </div>
        {loading ? (
          <p className="p-8 text-center text-slate-500">불러오는 중…</p>
        ) : myListings.length === 0 ? (
          <p className="p-10 text-center text-slate-500">아직 올린 글이 없어요.</p>
        ) : (
          <ul className="divide-y">
            {myListings.map((row) => (
              <li
                key={row.id}
                className="flex flex-wrap items-center gap-3 px-5 py-4 hover:bg-slate-50/50"
              >
                <span className="text-2xl">{row.emoji}</span>
                <div className="flex-1 min-w-[200px]">
                  <p className="font-semibold">{row.title}</p>
                  <p className="text-sm text-slate-500">
                    {row.price.toLocaleString()}원 · {row.location}
                  </p>
                </div>
                <button
                  type="button"
                  className="text-sm text-red-600 font-semibold"
                  onClick={() => remove(row.id)}
                >
                  내리기
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
