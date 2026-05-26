import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { PageHeader } from "../../components/ui/PageHeader";
import { ListingGuideEditor } from "../../components/seller/ListingGuideEditor";
import { SellerNoteOcrPanel } from "../../components/seller/SellerNoteOcrPanel";
import { SellerStepIndicator } from "../../components/seller/SellerStepIndicator";
import { SellerVoicePanel } from "../../components/seller/SellerVoicePanel";
import { api } from "../../lib/api";
import {
  detailFieldsForTab,
  detailSectionMeta,
} from "../../lib/listingDetailFields";
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
  buildOcrImagePrompt,
  cleanOcrLocation,
  parseOcrPrice,
  extractOcrVariants,
  cleanOcrStorageMethod,
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
import type { ListingDetails, ListingGuide, ListingVariant } from "../../types";
import { VoiceFillButton } from "../../components/seller/VoiceFillButton";

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
  const resetConversation = useConversation((s) => s.reset);
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
  const [aiStage, setAiStage] = useState<"idle" | "composing" | "drawing">("idle");
  const [coverDataUrl, setCoverDataUrl] = useState<string | null>(null);
  const [extraPhotos, setExtraPhotos] = useState<string[]>([]);
  const [imagePromptKo, setImagePromptKo] = useState("");
  const imagePromptEnRef = useRef("");
  const [promptSummary, setPromptSummary] = useState<string | null>(null);
  const [aiHint, setAiHint] = useState<string | null>(null);
  const [ocrPriceDetail, setOcrPriceDetail] = useState<string | null>(null);
  const aiImageRunningRef = useRef(false); // 중복 실행 방지
  // 가격·용량 옵션 — OCR 이 다중 단가를 감지하면 자동으로 후보가 채워진다.
  const [variants, setVariants] = useState<ListingVariant[] | null>(null);
  // 상세 정보 — 단위·원산지·생산자·유통기한·보관방법.
  const [details, setDetails] = useState<ListingDetails>({});
  const [detailsOpen, setDetailsOpen] = useState(false);
  // 한 번에 하나만 녹음 중이도록 잠금.
  const [activeVoiceField, setActiveVoiceField] = useState<string | null>(null);
  const voiceLockHandlers = useCallback(
    (key: string) => ({
      disabled: activeVoiceField !== null && activeVoiceField !== key,
      onActiveChange: (active: boolean) =>
        setActiveVoiceField(active ? key : null),
    }),
    [activeVoiceField]
  );
  // 음성 입력 후 단위/유통기한 등 짧은 텍스트는 끝의 마침표 제거 + 공백 정리.
  const cleanShort = (s: string) =>
    s
      .replace(/[.!?。·]+$/g, "")
      .replace(/\s+/g, " ")
      .trim();
  // 「열 개」, "20" 같은 숫자 표현을 정수로.
  const extractDigits = (s: string) => {
    const m = s.match(/(\d{1,6})/);
    return m ? m[1] : "";
  };

  const selectListingTab = useCallback((tab: ListingTab) => {
    if (listingTab === tab) return;

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

    // 탭 전환 시 이전 탭의 소개·이미지·옵션·음성 컨텍스트가 섞이지 않도록 초기화.
    setDescription("");
    setGuide(null);
    setCoverDataUrl(null);
    setImagePromptKo("");
    imagePromptEnRef.current = "";
    setPromptSummary(null);
    setAiHint(null);
    setOcrPriceDetail(null);
    setVariants(null);
    setDetails({});
    setDetailsOpen(false);
    resetConversation();
  }, [category, sellerSector, listingTab, resetConversation]);

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
    const ocrVariants = extractOcrVariants(draft);
    if (ocrVariants && ocrVariants.length >= 2) {
      setVariants(ocrVariants);
      setOcrPriceDetail(null);
      const minPrice = Math.min(...ocrVariants.map((v) => v.price));
      if (Number.isFinite(minPrice) && minPrice > 0) setPrice(String(minPrice));
    } else {
      setVariants(null);
      setOcrPriceDetail(detailNote);
    }
    const ocrLocation =
      f.location?.value != null ? cleanOcrLocation(String(f.location.value)) : "";
    if (ocrLocation) setLocation(ocrLocation);
    const desc = f.description?.value ?? f.notes?.value;
    let descText = desc != null ? String(desc).trim() : "";
    if (detailNote && !ocrVariants) {
      const tierLine = `[판매 단가] ${detailNote}`;
      descText = descText ? `${descText}\n\n${tierLine}` : tierLine;
    }
    if (descText) setDescription(descText);
    // 상세 정보 — OCR 이 뽑은 키를 그대로 폼 상태로 옮긴다.
    const detailFromOcr: ListingDetails = {};
    const detailKeys: (keyof ListingDetails)[] = [
      "unit",
      "origin",
      "producer",
      "shelf_life",
      "storage_method",
    ];
    for (const k of detailKeys) {
      const v = f[k]?.value;
      if (v != null && String(v).trim()) {
        let text = String(v).trim();
        if (k === "storage_method") text = cleanOcrStorageMethod(text);
        detailFromOcr[k] = text;
      }
    }
    // quantity 필드 — 「100g/200g/...」 같은 중량 표기는 stock 으로 넣으면 안 되고,
    // 단위(unit) 또는 옵션(variants)으로 옮긴다. 「10개/5박스」 같은 진짜 개수일
    // 때만 재고 수량으로 채운다.
    if (f.quantity?.value != null && tab !== "lodging") {
      const qRaw = String(f.quantity.value).trim();
      const isWeight = /\d+\s*(g|kg|그램|킬로|키로|cc|ml|리터|l)\b/i.test(qRaw);
      const countMatch = qRaw.match(
        /^\s*(\d{1,5})\s*(개|박스|봉지?|봉|묶음|단|상자|꾸러미|병|팩)\s*$/
      );
      if (countMatch) {
        // 진짜 개수만 stock 으로
        setStock(countMatch[1]);
      } else if (isWeight) {
        // 중량 표기는 단위 칸으로 옮긴다 (단일가는 그대로, 다중 옵션이면 옵션이 우선이라 라벨로 충분).
        if (!ocrVariants && !detailFromOcr.unit) {
          // 첫 단위 토큰만 추출 (예: "100g / 200g / 500g / 1kg" → "100g")
          const m = qRaw.match(/(\d+\s*(?:g|kg|그램|킬로|키로|cc|ml|리터|l))\b/i);
          if (m) detailFromOcr.unit = m[1].replace(/\s+/g, "");
        }
      }
      // 그 외(다른 형식)는 stock 을 함부로 채우지 않음 → 사용자가 직접 입력.
    }
    if (Object.keys(detailFromOcr).length > 0) {
      setDetails((prev) => ({ ...prev, ...detailFromOcr }));
      setDetailsOpen(true);
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
    // 음성 도우미 시작 방식(이어서/처음부터)을 다시 묻도록 초기화.
    useSellerFormVoice.getState().setStartMode(null);
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

  const runCoverAi = useCallback(async (regenerate = false) => {
    const t = title.trim();
    if (!t) {
      setAiHint("먼저 1단계에서 이름을 적어 주세요.");
      setStep(1);
      return;
    }
    if (aiImageRunningRef.current) return;
    aiImageRunningRef.current = true;
    setAiBusy(true);
    setAiStage("composing");
    setAiHint(null);
    try {
      const { kind: k, category: cat } = resolveKindCategory(listingTab, category);
      const koHint = (imagePromptKo.trim() || t).slice(0, 200);
      if (!imagePromptKo.trim()) setImagePromptKo(koHint);
      if (regenerate) {
        imagePromptEnRef.current = "";
      }
      const regenNote = regenerate
        ? " 다른 구도·배경·소품으로, 이전과 다르게."
        : "";
      const enhanced = await api.enhanceImagePrompt({
        kind: k,
        title: t,
        location: location.trim(),
        category: cat,
        description: description.trim(),
        user_hint: `${koHint}${regenNote}`,
      });
      imagePromptEnRef.current = enhanced.prompt_en;
      setPromptSummary(enhanced.summary_ko);

      setAiStage("drawing");
      const variantTag = `__variant_${Date.now()}_${Math.random()
        .toString(36)
        .slice(2, 8)}`;
      const r = await api.draftListingImage({
        kind: k,
        title: t,
        location: location.trim(),
        category: cat,
        description: description.trim(),
        prompt_en: `${enhanced.prompt_en} ${variantTag}`,
      });
      setCoverDataUrl(`data:${r.mime_type};base64,${r.image_base64}`);
      setStep(3);
      setAiHint(
        regenerate
          ? "다른 문구로 사진을 다시 만들었어요."
          : "대표 사진을 만들었어요."
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : "사진을 만들지 못했어요.";
      setAiHint(
        "사진 생성 중 잠시 문제가 있었어요. 다시 시도해 주시거나 「내 사진 올리기」로 직접 올려 주세요."
          + (msg ? `\n(원인: ${msg.slice(0, 120)})` : "")
      );
    } finally {
      setAiBusy(false);
      setAiStage("idle");
      setPromptSummary(null);
      aiImageRunningRef.current = false;
    }
  }, [listingTab, category, title, location, description, imagePromptKo]);

  /** 음성·레거시 호출용 */
  const generateCoverAi = useCallback(() => runCoverAi(false), [runCoverAi]);

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
    const cat = String(slots.category || "").trim();
    if (slots.kind === "lodging") {
      if (listingTab !== "lodging") {
        setListingTab("lodging");
        setCategory("lodging");
      }
    } else if (cat === "experience") {
      if (listingTab !== "experience") {
        setListingTab("experience");
        setCategory("experience");
      }
    } else if (slots.kind === "product" && listingTab !== "product") {
      setListingTab("product");
      if (cat && cat !== "experience" && cat !== "lodging") {
        setCategory(cat as ListingCategory);
      }
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
  }, [slots, listingTab]);

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
        if (l.variants && l.variants.length >= 2) setVariants(l.variants);
        if (l.details && typeof l.details === "object") {
          setDetails(l.details);
          if (Object.values(l.details).some((v) => v && String(v).trim())) {
            setDetailsOpen(true);
          }
        }
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

  // 3단계 진입 시 장면 힌트는 기본적으로 상품 이름만
  useEffect(() => {
    if (step !== 3) return;
    const t = title.trim();
    if (!t) return;
    setImagePromptKo((prev) => (prev.trim() ? prev : t));
  }, [step, title]);

  // 제목·한국어 힌트가 바뀌면 내부 영문 프롬프트만 초기화 (화면에는 노출하지 않음)
  useEffect(() => {
    imagePromptEnRef.current = "";
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
        stock:
          k === "product"
            ? Math.max(0, parseInt(stock, 10) || 0)
            : null,
        max_guests:
          k === "lodging" ? Math.max(1, parseInt(maxGuests, 10) || 4) : null,
        cover_image_base64: coverIsNew ? coverDataUrl!.split(",", 2)[1] : undefined,
        guide: guide ?? undefined,
        variants:
          k === "product" && cat !== "experience" && variants && variants.length >= 2
            ? variants
            : undefined,
        details: Object.values(details).some((v) => v && String(v).trim())
          ? details
          : undefined,
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
      imagePromptEnRef.current = "";
      setPromptSummary(null);
      setAiHint(null);
      setOcrPriceDetail(null);
      setVariants(null);
      setDetails({});
      setDetailsOpen(false);
      setStep(1);
      if (editId) {
        navigate("/seller");
      } else {
        resetConversation();
        setListingSubmitted(true);
      }
    } finally {
      setBusy(false);
    }
  };

  const canNextStep1 = title.trim() && price.trim();
  const banner = STEP_BANNERS[step] ?? STEP_BANNERS[1];

  return (
    <div className="space-y-8 pb-44 sm:pb-48">
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

        <div className="grid grid-cols-1 lg:grid-cols-2 lg:divide-x divide-slate-100 min-h-[calc(100vh-14rem)]">
          <div className="p-5 sm:p-6 bg-slate-50/50 lg:overflow-y-auto lg:max-h-[calc(100vh-14rem)]">
            <SellerNoteOcrPanel listingTab={listingTab} onApply={applyOcrDraft} />
          </div>

          <div className="p-5 sm:p-8 lg:overflow-y-auto lg:max-h-[calc(100vh-14rem)]">
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
                    <div className="flex items-center gap-2">
                      <input
                        className="input-field text-lg flex-1"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        required
                        placeholder="예: 올해 햅쌀 10kg"
                      />
                      <VoiceFillButton
                        tone="emerald"
                        size="lg"
                        hint="상품 이름을 말로 입력·고치기"
                        onInterim={(t) => setTitle(cleanShort(t))}
                        onText={(t) => setTitle(cleanShort(t))}
                        {...voiceLockHandlers("title")}
                      />
                    </div>
                  </div>
                  <div>
                    <label className="label-step">가격 (원)</label>
                    <div className="flex items-center gap-2">
                      <input
                        className="input-field text-lg flex-1"
                        inputMode="numeric"
                        value={price}
                        onChange={(e) => setPrice(e.target.value.replace(/\D/g, ""))}
                        required
                        placeholder="42000"
                      />
                      <VoiceFillButton
                        tone="emerald"
                        size="lg"
                        hint="가격을 숫자로 말로 입력·고치기"
                        onInterim={(t) => {
                          const d = extractDigits(t);
                          if (d) setPrice(d);
                        }}
                        onText={(t) => {
                          const d = extractDigits(t);
                          if (d) setPrice(d);
                        }}
                        {...voiceLockHandlers("price")}
                      />
                    </div>
                    {ocrPriceDetail && !variants ? (
                      <p className="mt-1.5 text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
                        메모에 여러 단가가 있습니다. 대표 가격만 넣었어요 — 전체: {ocrPriceDetail}
                      </p>
                    ) : null}
                    {variants && variants.length >= 2 && listingTab === "product" ? (
                      <div className="mt-3 rounded-2xl border-2 border-emerald-200 bg-emerald-50/70 p-4">
                        <div className="flex items-start gap-2 mb-3">
                          <span className="text-2xl leading-none">🧺</span>
                          <div className="flex-1">
                            <p className="font-semibold text-emerald-900 text-base">
                              용량·가격 옵션을 {variants.length}개 찾았어요
                            </p>
                            <p className="text-xs text-emerald-700 mt-0.5">
                              구매하는 분이 직접 골라 살 수 있게 「옵션」으로 등록해 드려요. 잘못된 항목이 있으면 ✕ 로 빼 주세요.
                            </p>
                          </div>
                        </div>
                        <ul className="space-y-2">
                          {variants.map((v, idx) => (
                            <li
                              key={`${v.label}-${idx}`}
                              className="flex items-center gap-2 bg-white rounded-xl px-3 py-2 border border-emerald-100"
                            >
                              <input
                                className="input-field text-sm flex-1 max-w-[140px]"
                                value={v.label}
                                onChange={(e) => {
                                  const next = [...variants];
                                  next[idx] = { ...v, label: e.target.value };
                                  setVariants(next);
                                }}
                                placeholder="100g"
                              />
                              <span className="text-slate-400 text-sm">·</span>
                              <input
                                type="number"
                                inputMode="numeric"
                                className="input-field text-sm flex-1 max-w-[140px]"
                                value={String(v.price)}
                                onChange={(e) => {
                                  const next = [...variants];
                                  next[idx] = {
                                    ...v,
                                    price: Math.max(0, parseInt(e.target.value, 10) || 0),
                                  };
                                  setVariants(next);
                                }}
                                placeholder="13000"
                              />
                              <span className="text-xs text-slate-500">원</span>
                              <button
                                type="button"
                                aria-label="옵션 삭제"
                                className="text-slate-400 hover:text-rose-500 text-xl leading-none px-1"
                                onClick={() => {
                                  const next = variants.filter((_, i) => i !== idx);
                                  setVariants(next.length >= 2 ? next : null);
                                }}
                              >
                                ✕
                              </button>
                            </li>
                          ))}
                        </ul>
                        <div className="mt-3 flex items-center gap-2 flex-wrap">
                          <button
                            type="button"
                            className="text-xs px-3 py-1.5 rounded-full bg-white border border-emerald-200 text-emerald-800 font-medium hover:bg-emerald-100"
                            onClick={() =>
                              setVariants([
                                ...variants,
                                { label: "", price: 0 },
                              ])
                            }
                          >
                            + 옵션 추가
                          </button>
                          <button
                            type="button"
                            className="text-xs px-3 py-1.5 rounded-full bg-white border border-rose-200 text-rose-700 font-medium hover:bg-rose-50"
                            onClick={() => setVariants(null)}
                          >
                            옵션 안 쓸래요 (단일가)
                          </button>
                          <span className="text-[11px] text-emerald-700 ml-auto">
                            대표가는 가장 작은 옵션가로 자동 표시돼요
                          </span>
                        </div>
                      </div>
                    ) : null}
                  </div>
                  <div>
                    <label className="label-step">동네 (시·군)</label>
                    <div className="flex items-center gap-2">
                      <input
                        className="input-field text-lg flex-1"
                        value={location}
                        onChange={(e) => setLocation(e.target.value)}
                        placeholder="전북 김제시"
                      />
                      <VoiceFillButton
                        tone="emerald"
                        size="lg"
                        hint="시·군을 말로 입력·고치기"
                        onInterim={(t) => setLocation(cleanShort(t))}
                        onText={(t) => setLocation(cleanShort(t))}
                        {...voiceLockHandlers("location")}
                      />
                    </div>
                  </div>
                  {listingTab === "lodging" ? (
                    <div>
                      <label className="label-step">정원 (명)</label>
                      <div className="flex items-center gap-2">
                        <input
                          className="input-field text-lg flex-1"
                          inputMode="numeric"
                          value={maxGuests}
                          onChange={(e) => setMaxGuests(e.target.value.replace(/\D/g, ""))}
                          placeholder="4"
                        />
                        <VoiceFillButton
                          tone="emerald"
                          size="lg"
                          hint="정원을 숫자로 말로 입력·고치기"
                          onInterim={(t) => {
                            const d = extractDigits(t);
                            if (d) setMaxGuests(d);
                          }}
                          onText={(t) => {
                            const d = extractDigits(t);
                            if (d) setMaxGuests(d);
                          }}
                          {...voiceLockHandlers("max_guests")}
                        />
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        한 번에 받을 수 있는 최대 인원이에요.
                      </p>
                    </div>
                  ) : listingTab === "experience" ? (
                    <div>
                      <label className="label-step">하루 정원 (명)</label>
                      <div className="flex items-center gap-2">
                        <input
                          className="input-field text-lg flex-1"
                          inputMode="numeric"
                          value={stock}
                          onChange={(e) => setStock(e.target.value.replace(/\D/g, ""))}
                          placeholder="20"
                        />
                        <VoiceFillButton
                          tone="emerald"
                          size="lg"
                          hint="하루 정원을 숫자로 말로 입력·고치기"
                          onInterim={(t) => {
                            const d = extractDigits(t);
                            if (d) setStock(d);
                          }}
                          onText={(t) => {
                            const d = extractDigits(t);
                            if (d) setStock(d);
                          }}
                          {...voiceLockHandlers("stock")}
                        />
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        하루(또는 회차)에 받을 수 있는 최대 인원이에요. 음성으로 「24명」처럼
                        말씀하셔도 됩니다.
                      </p>
                    </div>
                  ) : (
                    <div>
                      <label className="label-step">재고 수량</label>
                      <div className="flex items-center gap-2">
                        <input
                          className="input-field text-lg flex-1"
                          inputMode="numeric"
                          value={stock}
                          onChange={(e) => setStock(e.target.value.replace(/\D/g, ""))}
                          placeholder="10"
                        />
                        <VoiceFillButton
                          tone="emerald"
                          size="lg"
                          hint="재고 수량을 숫자로 말로 입력·고치기"
                          onInterim={(t) => {
                            const d = extractDigits(t);
                            if (d) setStock(d);
                          }}
                          onText={(t) => {
                            const d = extractDigits(t);
                            if (d) setStock(d);
                          }}
                          {...voiceLockHandlers("stock")}
                        />
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        지금 팔 수 있는 개수예요. 옵션이 있으면 옵션마다 따로 관리됩니다.
                      </p>
                    </div>
                  )}

                  {(() => {
                    const meta = detailSectionMeta(listingTab);
                    const fields = detailFieldsForTab(listingTab);
                    const filledCount = Object.values(details).filter(
                      (v) => v && String(v).trim()
                    ).length;
                    return (
                      <div className="rounded-2xl border border-slate-200 bg-white">
                        <button
                          type="button"
                          onClick={() => setDetailsOpen((v) => !v)}
                          className="w-full flex items-center justify-between gap-3 px-4 py-3.5 text-left hover:bg-slate-50 rounded-2xl"
                        >
                          <span className="flex items-center gap-2 flex-wrap">
                            <span className="text-xl">{meta.emoji}</span>
                            <span className="font-semibold text-slate-800">{meta.title}</span>
                            <span className="text-xs text-slate-500">({meta.subtitle})</span>
                            {filledCount > 0 ? (
                              <span className="ml-1 text-[11px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-semibold">
                                {filledCount}개 채움
                              </span>
                            ) : null}
                          </span>
                          <span
                            className={`text-slate-400 transition-transform ${
                              detailsOpen ? "rotate-180" : ""
                            }`}
                          >
                            ▾
                          </span>
                        </button>
                        {detailsOpen ? (
                          <div className="px-4 pb-5 pt-1 space-y-4 border-t border-slate-100">
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                              {fields.map((field) => (
                                <div
                                  key={field.key}
                                  className={field.wide ? "sm:col-span-2" : undefined}
                                >
                                  <label className="text-sm font-semibold text-slate-700 block mb-1">
                                    {field.label}
                                  </label>
                                  <div className="flex items-center gap-2">
                                    <input
                                      className="input-field flex-1"
                                      value={details[field.key] ?? ""}
                                      onChange={(e) =>
                                        setDetails((d) => ({
                                          ...d,
                                          [field.key]: e.target.value,
                                        }))
                                      }
                                      placeholder={field.placeholder}
                                    />
                                    <VoiceFillButton
                                      tone="emerald"
                                      hint={`${field.label} 말로 입력·고치기`}
                                      onInterim={(t) =>
                                        setDetails((d) => ({
                                          ...d,
                                          [field.key]: cleanShort(t),
                                        }))
                                      }
                                      onText={(t) =>
                                        setDetails((d) => ({
                                          ...d,
                                          [field.key]: cleanShort(t),
                                        }))
                                      }
                                      {...voiceLockHandlers(field.key)}
                                    />
                                  </div>
                                  {field.hint ? (
                                    <p className="text-[11px] text-slate-500 mt-0.5">
                                      {field.hint}
                                    </p>
                                  ) : null}
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    );
                  })()}
                </div>
              )}

              {step === 2 && (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    <div className="space-y-4">
                      <div>
                        <label className="label-step">소개 글</label>
                      <div className="flex items-start gap-2">
                        <textarea
                          className="input-field text-lg min-h-[180px] flex-1"
                          value={description}
                          onChange={(e) => setDescription(e.target.value)}
                          placeholder="어떤 물건인지, 왜 좋은지 적어 주세요."
                        />
                        <VoiceFillButton
                          tone="violet"
                          size="lg"
                          hint="소개 글을 말로 입력·고치기"
                          onInterim={(t) => setDescription(cleanShort(t))}
                          onText={(t) => setDescription(cleanShort(t))}
                          {...voiceLockHandlers("description")}
                        />
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        AI·OCR로 채운 글도 🎤 로 말해서 고치거나, 여기서 적어 주세요.
                      </p>
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
                        <ListingGuideEditor
                          guide={guide}
                          listingTab={listingTab}
                          title={title}
                          onChange={setGuide}
                        />
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
                    <div className="rounded-xl border border-slate-200 bg-white/70 p-3 space-y-3">
                      <p className="text-sm font-semibold text-slate-700">또는 AI로 만들기</p>
                      <div>
                        <label className="text-sm text-slate-600">어떤 장면? (선택, 한국어)</label>
                        <input
                          className="input-field mt-1"
                          value={imagePromptKo}
                          onChange={(e) => setImagePromptKo(e.target.value)}
                          placeholder={title.trim() || "예: 고사리"}
                          disabled={aiBusy}
                        />
                        <p className="mt-1 text-xs text-slate-500">
                          상품 이름만 넣어도 됩니다. 영어는 몰라도 괜찮아요 — 뒤에서 자동으로
                          번역·그림 처리합니다.
                        </p>
                      </div>
                      <button
                        type="button"
                        className="btn-primary py-2.5 px-4 disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={busy || aiBusy}
                        onClick={() => void runCoverAi(!!coverDataUrl)}
                      >
                        {aiBusy
                          ? aiStage === "composing"
                            ? "장면 구성 중…"
                            : "사진 그리는 중… (1~2분)"
                          : coverDataUrl
                            ? "문구 재생성"
                            : "AI로 사진 만들기"}
                      </button>
                      {aiBusy && promptSummary ? (
                        <p className="text-sm text-shop-tealDark animate-pulse">{promptSummary}</p>
                      ) : null}
                    </div>

                    {coverDataUrl ? (
                      <div className="rounded-xl overflow-hidden border max-w-sm relative">
                        {aiBusy ? (
                          <div className="absolute inset-0 z-10 bg-white/80 flex flex-col items-center justify-center gap-2 text-sm text-slate-600">
                            <span className="inline-block h-8 w-8 rounded-full border-2 border-shop-teal border-t-transparent animate-spin" />
                            {aiStage === "composing"
                              ? "다른 장면을 구성하고 있어요…"
                              : "새 사진을 그리고 있어요…"}
                          </div>
                        ) : null}
                        <img src={coverDataUrl} alt="대표 사진" className="w-full aspect-[16/10] object-cover" />
                        <button
                          type="button"
                          className="w-full py-2 text-sm text-red-600 bg-white border-t"
                          onClick={() => {
                            setCoverDataUrl(null);
                            imagePromptEnRef.current = "";
                          }}
                          disabled={aiBusy}
                        >
                          사진 지우기
                        </button>
                      </div>
                    ) : (
                      <div className="rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 h-40 flex flex-col items-center justify-center gap-2 text-slate-400">
                        {aiBusy ? (
                          <>
                            <span className="inline-block h-8 w-8 rounded-full border-2 border-shop-teal border-t-transparent animate-spin" />
                            <span className="text-sm text-slate-500">
                              {aiStage === "composing"
                                ? "장면을 구성하고 있어요…"
                                : "사진을 그리고 있어요… (1~2분)"}
                            </span>
                          </>
                        ) : (
                          "아직 대표 사진 없음"
                        )}
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

      <SellerVoicePanel variant="dock" step={step} listingTab={listingTab} />
    </div>
  );
}
