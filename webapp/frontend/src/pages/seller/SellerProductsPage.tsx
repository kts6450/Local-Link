import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { PageHeader } from "../../components/ui/PageHeader";
import { ListingGuidePreview } from "../../components/seller/ListingGuidePreview";
import { SellerNoteOcrPanel } from "../../components/seller/SellerNoteOcrPanel";
import { SellerStepIndicator } from "../../components/seller/SellerStepIndicator";
import { SellerVoicePanel } from "../../components/seller/SellerVoicePanel";
import { api } from "../../lib/api";
import {
  LISTING_TABS,
  PRODUCT_MENU_CATEGORIES,
  resolveKindCategory,
  tabDefaultCategory,
  tabLabel,
  tabToKind,
  type ListingTab,
  type OcrListingDraft,
} from "../../lib/listingTabs";
import {
  buildImagePromptFromListing,
  buildOcrImagePrompt,
  cleanOcrLocation,
  parseOcrPrice,
} from "../../lib/ocrFormUtils";
import {
  LISTING_CATEGORIES,
  categoryLabel,
  type ListingCategory,
} from "../../lib/sellerSectors";
import {
  useAuthDisplayName,
  useAuthSellerId,
  useAuthSellerSector,
} from "../../store/auth";
import { useConversation } from "../../store/conversation";
import { useSellerFormVoice } from "../../store/sellerFormVoice";
import type { ListingGuide } from "../../types";

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
  const registerVoice = useSellerFormVoice((s) => s.register);
  const unregisterVoice = useSellerFormVoice((s) => s.unregister);

  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const editId = searchParams.get("edit");

  const [step, setStep] = useState(1);
  const listingSubmitted = useConversation((s) => s.listingSubmitted);
  const setListingSubmitted = useConversation((s) => s.setListingSubmitted);
  const slots = useConversation((s) => s.slots);

  const [listingTab, setListingTab] = useState<ListingTab>("product");
  const kind = tabToKind(listingTab);
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
  const [ocrPriceDetail, setOcrPriceDetail] = useState<string | null>(null);
  const aiImageRunningRef = useRef(false); // 중복 실행 방지

  const selectListingTab = useCallback((tab: ListingTab) => {
    setListingTab(tab);
    if (tab === "lodging" || tab === "experience") {
      setCategory(tabDefaultCategory(tab));
    } else if (category === "lodging" || category === "experience") {
      setCategory(
        sellerSector && PRODUCT_MENU_CATEGORIES.includes(sellerSector)
          ? sellerSector
          : "rural"
      );
    }
  }, [category, sellerSector]);

  const applyOcrDraft = useCallback((draft: OcrListingDraft) => {
    const tab = draft.listing_tab;
    setListingTab(tab);
    setCategory(tabDefaultCategory(tab));
    const f = draft.fields ?? {};
    const ocrTitle =
      f.title?.value != null && String(f.title.value).trim()
        ? String(f.title.value).trim()
        : "";
    if (ocrTitle) setTitle(ocrTitle);
    const { price: parsedPrice, detailNote } = parseOcrPrice(f.price?.value);
    if (parsedPrice) setPrice(parsedPrice);
    setOcrPriceDetail(detailNote);
    const ocrLocation =
      f.location?.value != null ? cleanOcrLocation(String(f.location.value)) : "";
    if (ocrLocation) setLocation(ocrLocation);
    const desc = f.description?.value ?? f.notes?.value;
    let descText = desc != null ? String(desc).trim() : "";
    if (detailNote) {
      const tierLine = `[판매 단가] ${detailNote}`;
      descText = descText ? `${descText}\n\n${tierLine}` : tierLine;
    }
    if (descText) setDescription(descText);
    if (f.quantity?.value != null && tab !== "lodging") {
      const q = String(f.quantity.value);
      const m = q.match(/(\d+)/);
      if (m) setStock(m[1]);
    }
    const imgHint = buildOcrImagePrompt(f, tab, String(f.title?.value ?? ""));
    if (imgHint) setImagePromptKo(imgHint);
    // OCR 로 채워진 값을 음성 도우미가 인지하도록 conversation slots 에도 머지.
    const ocrPriceNum = parsedPrice ? Number(parsedPrice) : undefined;
    useConversation.getState().mergeSlots({
      ...(ocrTitle ? { title: ocrTitle } : {}),
      ...(ocrPriceNum != null && !Number.isNaN(ocrPriceNum) ? { price: ocrPriceNum } : {}),
      ...(ocrLocation ? { location: ocrLocation } : {}),
      ...(descText ? { description: descText } : {}),
      kind: tab === "lodging" ? "lodging" : "product",
    });
    setAiHint("OCR 결과를 채웠어요. 「확인 필요」 항목은 꼭 검토해 주세요.");
    setStep(1);
  }, []);

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
      const { kind: k, category: cat } = resolveKindCategory(listingTab, category);
      const r = await api.draftListingPackage({
        kind: k,
        title: t,
        price: p,
        location: location.trim(),
        category: cat,
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
  }, [listingTab, title, price, location, category]);

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
    // 버튼 클릭 + 음성 명령 동시에 들어올 경우 중복 실행 방지
    if (aiImageRunningRef.current) return;
    aiImageRunningRef.current = true;
    setAiBusy(true);
    setAiHint(null);
    try {
      const { kind: k, category: cat } = resolveKindCategory(listingTab, category);
      let koHint = imagePromptKo.trim();
      if (!koHint) {
        koHint = buildImagePromptFromListing(t, location.trim(), description.trim(), listingTab);
        setImagePromptKo(koHint);
      }
      let promptEn = imagePromptEn.trim();
      if (!promptEn) {
        const enhanced = await api.enhanceImagePrompt({
          kind: k,
          title: t,
          location: location.trim(),
          category: cat,
          description: description.trim(),
          user_hint: koHint,
        });
        promptEn = enhanced.prompt_en;
        setImagePromptEn(promptEn);
        setPromptSummary(enhanced.summary_ko);
      }
      const r = await api.draftListingImage({
        kind: k,
        title: t,
        location: location.trim(),
        category: cat,
        description: description.trim(),
        prompt_en: promptEn,
      });
      setCoverDataUrl(`data:${r.mime_type};base64,${r.image_base64}`);
      setStep(3);
      setAiHint("대표 사진을 만들었어요.");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "사진을 만들지 못했어요.";
      setAiHint(
        "사진 생성 중 잠시 문제가 있었어요. 다시 시도해 주시거나 「내 사진 올리기」로 직접 올려 주세요."
          + (msg ? `\n(원인: ${msg.slice(0, 120)})` : "")
      );
    } finally {
      setAiBusy(false);
      aiImageRunningRef.current = false;
    }
  }, [
    listingTab,
    category,
    title,
    location,
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

  // 폼 상태 스냅샷 — 음성 도우미가 매 turn마다 백엔드에 같이 보내서
  // OCR/직접 입력으로 채워진 값을 LLM 이 알아보고 다시 묻지 않게 한다.
  const formSnapshotRef = useRef({
    title,
    price,
    description,
    location,
    listing_tab: listingTab,
    stock,
    max_guests: maxGuests,
  });
  formSnapshotRef.current = {
    title,
    price,
    description,
    location,
    listing_tab: listingTab,
    stock,
    max_guests: maxGuests,
  };

  useEffect(() => {
    registerVoice({
      onAiWrite: voiceAiWrite,
      onAiImage: generateCoverAi,
      getFormState: () => {
        const f = formSnapshotRef.current;
        return {
          title: f.title?.trim() || undefined,
          price: f.price?.trim() ? Number(f.price) : undefined,
          description: f.description?.trim() || undefined,
          location: f.location?.trim() || undefined,
          listing_tab: f.listing_tab,
          stock: f.stock?.trim() ? Number(f.stock) : undefined,
          max_guests: f.max_guests?.trim() ? Number(f.max_guests) : undefined,
        };
      },
    });
    return () => unregisterVoice();
  }, [registerVoice, unregisterVoice, voiceAiWrite, generateCoverAi]);

  useEffect(() => {
    if (sellerSector) setCategory(sellerSector);
  }, [sellerSector]);

  useEffect(() => {
    if (slots.kind === "product" || slots.kind === "lodging") {
      selectListingTab(slots.kind === "lodging" ? "lodging" : "product");
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
  }, [slots, selectListingTab]);

  // 수정 모드: ?edit=<id> 면 기존 상품 내용을 폼에 채운다.
  useEffect(() => {
    if (!editId) return;
    let cancelled = false;
    void api
      .getListing(editId)
      .then((l) => {
        if (cancelled || !l) return;
        const tab: ListingTab =
          l.kind === "lodging"
            ? "lodging"
            : l.category === "experience"
              ? "experience"
              : "product";
        setListingTab(tab);
        if (l.category) setCategory(l.category as ListingCategory);
        setTitle(l.title ?? "");
        setPrice(l.price != null ? String(l.price) : "");
        setDescription(l.description ?? "");
        setGuide(l.guide ?? null);
        setLocation(l.location ?? "");
        if (l.stock != null) setStock(String(l.stock));
        if (l.max_guests != null) setMaxGuests(String(l.max_guests));
        setCoverDataUrl(l.cover_image_url ?? null);
        setStep(1);
      })
      .catch(() => {
        setAiHint("상품 정보를 불러오지 못했어요.");
      });
    return () => {
      cancelled = true;
    };
  }, [editId]);

  // 대표 이미지 생성은 외부 키 없이도 동작하므로 별도 가드는 두지 않는다.

  // 제목이나 한국어 힌트가 바뀌면 영문 프롬프트 캐시를 초기화해서 항상 최신 힌트가 반영되게 한다.
  useEffect(() => {
    setImagePromptEn("");
    setPromptSummary(null);
  }, [title, imagePromptKo]);

  const onPickCover = (files: FileList | null) => {
    const f = files?.[0];
    if (!f || !f.type.startsWith("image/")) return;
    const r = new FileReader();
    r.onload = () => {
      setCoverDataUrl(String(r.result || ""));
      setStep(3);
    };
    r.readAsDataURL(f);
  };

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
      const { kind: k, category: cat } = resolveKindCategory(listingTab, category);
      // 새로 만든(data:) 이미지만 전송 — 기존 URL이면 그대로 유지.
      const coverIsNew = coverDataUrl?.startsWith("data:") ?? false;
      const payload = {
        kind: k,
        category: cat,
        seller_id: sellerId ?? undefined,
        title: title.trim(),
        description: description.trim(),
        price: Math.max(0, parseInt(price, 10) || 0),
        location: location.trim(),
        stock: k === "product" ? Math.max(0, parseInt(stock, 10) || 0) : null,
        max_guests:
          k === "lodging" ? Math.max(1, parseInt(maxGuests, 10) || 4) : null,
        cover_image_base64: coverIsNew ? coverDataUrl!.split(",", 2)[1] : undefined,
        guide: guide ?? undefined,
      };
      const saved = editId
        ? await api.updateListing(editId, payload)
        : await api.createListing(payload);
      for (const data of extraPhotos) {
        const b64 = data.includes(",") ? data.split(",", 2)[1] : data;
        try {
          await api.addListingPhoto(saved.id, { image_base64: b64 });
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
      setOcrPriceDetail(null);
      setStep(1);
      if (editId) {
        navigate("/seller");
      } else {
        setListingSubmitted(true);
      }
    } finally {
      setBusy(false);
    }
  };

  const canNextStep1 = title.trim() && price.trim();
  const banner = STEP_BANNERS[step] ?? STEP_BANNERS[1];

  return (
    <div className="space-y-8">
      {listingSubmitted && (
        <div className="rounded-2xl border border-shop-teal/30 bg-shop-tealLight/60 p-5 flex flex-wrap items-center justify-between gap-3">
          <p className="font-semibold text-shop-tealDark">
            등록이 완료됐어요. 대시보드에서 등록된 상품을 확인하세요.
          </p>
          <div className="flex gap-2">
            <Link
              to="/seller"
              className="rounded-full bg-shop-tealDark text-white text-sm font-bold px-4 py-2"
              onClick={() => setListingSubmitted(false)}
            >
              대시보드로 가기
            </Link>
            <button
              type="button"
              className="btn-ghost text-shop-tealDark border-shop-teal/30"
              onClick={() => setListingSubmitted(false)}
            >
              닫기
            </button>
          </div>
        </div>
      )}

      <PageHeader badge="공급자 · BETA" title={editId ? "상품 수정" : "음성 한 번으로 올리기"}>
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

        <div className="grid grid-cols-1 xl:grid-cols-[1fr_1fr_2fr] gap-0 xl:gap-6">
          <div className="border-b xl:border-b-0 xl:border-r border-slate-100 p-5 sm:p-6 bg-slate-50/50 xl:sticky xl:top-24 xl:self-start xl:max-h-[calc(100vh-7rem)] xl:overflow-y-auto">
            <SellerNoteOcrPanel listingTab={listingTab} onApply={applyOcrDraft} />
          </div>

          <div className="border-b xl:border-b-0 xl:border-r border-slate-100 p-5 sm:p-6 bg-slate-50/50 xl:sticky xl:top-24 xl:self-start xl:max-h-[calc(100vh-7rem)] xl:overflow-y-auto">
            <SellerVoicePanel step={step} listingTab={listingTab} />
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
                    <label className="label-step">종류</label>
                    <div className="grid grid-cols-3 gap-2">
                      {LISTING_TABS.map((tab) => (
                        <button
                          key={tab.id}
                          type="button"
                          onClick={() => selectListingTab(tab.id)}
                          className={
                            listingTab === tab.id
                              ? "btn-primary py-3 px-2 text-sm sm:text-base"
                              : "btn-ghost py-3 px-2 text-sm sm:text-base border-slate-200"
                          }
                        >
                          <span className="block text-lg">{tab.emoji}</span>
                          <span className="font-bold">{tab.label}</span>
                          <span className="block text-xs opacity-80 mt-0.5">{tab.sub}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                  {listingTab === "product" ? (
                    <div>
                      <label className="label-step">쇼핑 메뉴</label>
                      <select
                        className="input-field text-lg"
                        value={category}
                        onChange={(e) => setCategory(e.target.value as ListingCategory)}
                      >
                        {LISTING_CATEGORIES.filter((c) =>
                          PRODUCT_MENU_CATEGORIES.includes(c.id)
                        ).map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-600 rounded-xl bg-slate-50 border border-slate-100 px-4 py-3">
                      쇼핑 메뉴:{" "}
                      <strong>{categoryLabel(tabDefaultCategory(listingTab))}</strong>
                    </p>
                  )}
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
                    {ocrPriceDetail ? (
                      <p className="mt-1.5 text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
                        메모에 여러 단가가 있습니다. 대표 가격만 넣었어요 — 전체: {ocrPriceDetail}
                      </p>
                    ) : null}
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
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    <div className="space-y-4">
                      <div>
                        <label className="label-step">소개 글</label>
                        <textarea
                          className="input-field text-lg min-h-[180px]"
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
                      </div>
                    </div>
                    <div>
                      {guide ? (
                        <ListingGuidePreview guide={guide} listingTab={listingTab} title={title} />
                      ) : (
                        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 p-6 text-center text-sm text-slate-500 min-h-[200px] flex items-center justify-center">
                          「소개 + 이용안내 한번에」를 누르면
                          <br />
                          포인트·순서·환불 안내가 여기에 표시됩니다.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {step === 3 && (
                <div className="space-y-4">
                  <div className="rounded-2xl border border-sky-100 bg-sky-50/50 p-4 space-y-3">
                    <p className="font-semibold text-slate-800">대표 사진</p>
                    <p className="text-sm text-slate-600">
                      사진 파일을 직접 올리거나, AI로 만들 수 있어요.
                    </p>

                    {/* 직접 업로드 — AI 없이도 항상 가능 */}
                    <label className="inline-block">
                      <span className="btn-primary py-2.5 px-4 cursor-pointer inline-block">
                        내 사진 올리기
                      </span>
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={(e) => onPickCover(e.target.files)}
                      />
                    </label>

                    {/* AI 생성 — 서버에 OpenAI 키가 있을 때만 */}
                    <div className="rounded-xl border border-slate-200 bg-white/70 p-3 space-y-2">
                      <p className="text-sm font-semibold text-slate-700">또는 AI로 만들기</p>
                      <div>
                        <label className="text-sm text-slate-600">어떤 장면? (선택)</label>
                        <input
                          className="input-field mt-1"
                          value={imagePromptKo}
                          onChange={(e) => setImagePromptKo(e.target.value)}
                          placeholder={
                            imagePromptKo.trim() ||
                            "예: 산지 고사리, 자연광 아래 정갈한 포장"
                          }
                        />
                      </div>
                      <button
                        type="button"
                        className="btn-primary py-2.5 px-4 disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={busy || aiBusy}
                        onClick={() => void generateCoverAi()}
                      >
                        {aiBusy ? "그리는 중…" : "AI로 대표 사진 만들기"}
                      </button>
                      {promptSummary ? (
                        <p className="text-sm text-shop-tealDark">{promptSummary}</p>
                      ) : null}
                    </div>

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
                    <dd>{tabLabel(listingTab)}</dd>
                    <dt className="text-slate-500">이름</dt>
                    <dd className="font-semibold">{title || "—"}</dd>
                    <dt className="text-slate-500">가격</dt>
                    <dd>{price ? `${Number(price).toLocaleString()}원` : "—"}</dd>
                    <dt className="text-slate-500">동네</dt>
                    <dd>{location || "—"}</dd>
                    <dt className="text-slate-500">사진</dt>
                    <dd>{coverDataUrl ? "대표 있음" : "없음 (나중에 추가 가능)"}</dd>
                  </dl>
                  {listingTab === "lodging" ? (
                    <div>
                      <label className="label-step">최대 몇 명</label>
                      <input
                        className="input-field"
                        inputMode="numeric"
                        value={maxGuests}
                        onChange={(e) => setMaxGuests(e.target.value.replace(/\D/g, ""))}
                      />
                    </div>
                  ) : (
                    <div>
                      <label className="label-step">남은 개수</label>
                      <input
                        className="input-field"
                        inputMode="numeric"
                        value={stock}
                        onChange={(e) => setStock(e.target.value.replace(/\D/g, ""))}
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
                    {busy
                      ? editId
                        ? "저장 중…"
                        : "올리는 중…"
                      : editId
                        ? "수정 저장"
                        : "쇼핑에 올리기"}
                  </button>
                )}
              </div>
            </form>
          </div>
        </div>
      </section>

    </div>
  );
}
