import { authHeaders } from "./authFetch";
import type {
  AssistantReply,
  AssistantTurn,
  AuthUser,
  Brand,
  FeatureFlagItem,
  Listing,
  ListingDetails,
  ListingGuide,
  ListingPhoto,
  ListingVariant,
  Order,
  Turn,
  VoiceMode,
  VoiceStatus,
  VoiceTurnResponse,
} from "../types";
import type { ListingTab, OcrListingDraft } from "./listingTabs";

const FETCH_DEADLINE_MS = 18_000;

/** 타임아웃 + (선택) 외부 AbortSignal — 미완료 fetch로 로딩이 멈추는 것 방지 */
function mergeAbortSignals(primary: AbortSignal, secondary?: AbortSignal): AbortSignal {
  if (!secondary) return primary;
  const c = new AbortController();
  const stop = () => c.abort();
  if (primary.aborted || secondary.aborted) {
    c.abort();
    return c.signal;
  }
  primary.addEventListener("abort", stop, { once: true });
  secondary.addEventListener("abort", stop, { once: true });
  return c.signal;
}

/** 실패 응답에서 백엔드 detail 메시지를 뽑아낸다(없으면 fallback). */
async function errorDetail(res: Response, fallback: string): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: string };
    if (j?.detail) return j.detail;
  } catch {
    /* 본문 파싱 실패 시 fallback */
  }
  return fallback;
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const deadline = new AbortController();
  const tid = setTimeout(() => deadline.abort(), FETCH_DEADLINE_MS);
  const extra = init?.signal ?? undefined;
  const signal = mergeAbortSignals(deadline.signal, extra);
  const headers = new Headers(init?.headers);
  const auth = authHeaders();
  Object.entries(auth).forEach(([k, v]) => headers.set(k, v));
  try {
    const res = await fetch(path, { ...init, headers, signal });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  } finally {
    clearTimeout(tid);
  }
}

async function postJson<T>(path: string, body: unknown, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  Object.entries(authHeaders()).forEach(([k, v]) => headers.set(k, v));
  const res = await fetch(path, {
    method: "POST",
    ...init,
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = (await res.json()) as { detail?: string };
      if (j.detail) detail = j.detail;
    } catch {
      /* */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  register: (body: {
    email: string;
    password: string;
    role: "consumer" | "seller";
    display_name: string;
    seller_sector?: string;
  }) => postJson<{ token: string; user: AuthUser }>("/api/auth/register", body),

  login: (body: { email: string; password: string }) =>
    postJson<{ token: string; user: AuthUser }>("/api/auth/login", body),

  getMe: () => getJson<{ user: AuthUser }>("/api/auth/me"),

  getStatus: () => getJson<VoiceStatus>("/api/voice/status"),
  getBrand: () => getJson<Brand>("/api/marketplace/brand"),
  getFeatureFlags: () => getJson<{ items: FeatureFlagItem[] }>("/api/marketplace/features"),

  sellerSnsDraft: async (body: {
    kind: "product" | "lodging";
    title: string;
    description: string;
    price: number;
    location: string;
  }) => {
    const res = await fetch("/api/marketplace/seller/sns-draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`sellerSnsDraft ${res.status}`);
    return res.json() as Promise<Record<string, unknown>>;
  },

  sellerTourism: async (body: {
    kind: "product" | "lodging";
    title: string;
    location: string;
    description?: string;
    price?: number;
  }) => {
    const res = await fetch("/api/marketplace/seller/tourism", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...body, description: body.description ?? "", price: body.price ?? 0 }),
    });
    if (!res.ok) throw new Error(`sellerTourism ${res.status}`);
    return res.json() as Promise<Record<string, unknown>>;
  },

  sellerWeather: async (body: { location: string; title?: string }) => {
    const res = await fetch("/api/marketplace/seller/weather-season", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: "product",
        title: body.title ?? "",
        description: "",
        price: 0,
        location: body.location,
      }),
    });
    if (!res.ok) throw new Error(`sellerWeather ${res.status}`);
    return res.json() as Promise<Record<string, unknown>>;
  },

  sellerAlimtalk: async (body: {
    kind: "product" | "lodging";
    title: string;
    buyer_name: string;
    order_id: string;
    description?: string;
    price?: number;
    location?: string;
  }) => {
    const res = await fetch("/api/marketplace/seller/alimtalk-draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: body.kind,
        title: body.title,
        buyer_name: body.buyer_name,
        order_id: body.order_id,
        description: body.description ?? "",
        price: body.price ?? 0,
        location: body.location ?? "",
      }),
    });
    if (!res.ok) throw new Error(`sellerAlimtalk ${res.status}`);
    return res.json() as Promise<Record<string, unknown>>;
  },

  getAgentSuggestions: () =>
    getJson<{ suggestions: string[] }>("/api/marketplace/seller/agent-suggestions"),

  getRecentOrders: (limit = 8) => getJson<Order[]>(`/api/orders/recent?limit=${limit}`),

  getMyOrders: () => getJson<Order[]>("/api/orders/mine"),
  getSellerOrders: () => getJson<Order[]>("/api/orders/seller"),
  setOrderStatus: (orderId: string, status: string) =>
    postJson<Order>(`/api/orders/${orderId}/fulfillment`, { status }),

  getSellerDashboard: () =>
    getJson<{
      listing_count: number;
      order_count: number;
      paid_count: number;
      revenue_total: number;
      units_total: number;
      today_revenue: number;
      today_order_count: number;
      pending_count: number;
      sales_by_listing: Record<string, number>;
      top_items: { listing_id: string; title: string; units: number; revenue: number }[];
      low_stock: { listing_id: string; title: string; stock: number | null }[];
      revenue_by_day: { date: string; revenue: number }[];
    }>("/api/seller/dashboard"),

  adminListUsers: () =>
    getJson<{
      id: string;
      email: string;
      role: string;
      display_name: string;
      seller_sector: string | null;
      seller_id: string | null;
      created_at: string;
    }[]>("/api/admin/users"),
  adminDeleteUser: (userId: string) =>
    fetch(`/api/admin/users/${userId}`, {
      method: "DELETE",
      headers: authHeaders(),
    }).then((r) => {
      if (!r.ok) throw new Error(`adminDeleteUser ${r.status}`);
      return r.json() as Promise<{ ok: boolean }>;
    }),
  adminListAllListings: () =>
    getJson<{
      id: string;
      title: string;
      kind: string;
      category: string;
      price: number;
      location: string;
      seller_id: string;
      seller_email: string | null;
      created_at: string;
    }[]>("/api/admin/listings"),
  adminDeleteListing: (listingId: string) =>
    fetch(`/api/admin/listings/${listingId}`, {
      method: "DELETE",
      headers: authHeaders(),
    }).then((r) => {
      if (!r.ok) throw new Error(`adminDeleteListing ${r.status}`);
      return r.json() as Promise<{ ok: boolean }>;
    }),
  adminStats: () =>
    getJson<{
      users: number;
      consumers: number;
      sellers: number;
      listings: number;
      orders: number;
      paid_orders: number;
      revenue: number;
      reviews: number;
    }>("/api/admin/stats"),

  getReviews: (listingId: string) =>
    getJson<{
      count: number;
      average: number;
      items: {
        id: string;
        listing_id: string;
        order_id: string | null;
        user_id: string;
        user_name: string;
        rating: number;
        body: string;
        created_at: string;
      }[];
    }>(`/api/marketplace/listings/${listingId}/reviews`),
  postReview: (listingId: string, body: { rating: number; body: string; order_id?: string }) =>
    postJson<{
      id: string;
      rating: number;
      body: string;
      created_at: string;
    }>(`/api/marketplace/listings/${listingId}/reviews`, body),

  getListingLocalGuide: (listingId: string) =>
    getJson<{ tourism: Record<string, unknown>; weather: Record<string, unknown> }>(
      `/api/marketplace/listings/${listingId}/local-guide`
    ),
  getListings: (kind?: "product" | "lodging", init?: RequestInit) =>
    getJson<Listing[]>(
      kind ? `/api/marketplace/listings?kind=${kind}` : "/api/marketplace/listings",
      init
    ),
  getBestListings: (limit = 12) =>
    getJson<{ items: Listing[] }>(`/api/marketplace/best-listings?limit=${limit}`),

  assistantChat: (body: {
    user_text: string;
    history: Pick<AssistantTurn, "role" | "content">[];
  }) => postJson<AssistantReply>("/api/assistant/chat", body),
  getListing: (id: string, init?: RequestInit) =>
    getJson<Listing>(`/api/marketplace/listings/${id}`, init),

  getAiCapabilities: () =>
    getJson<{
      description_ai: boolean;
      description_claude: boolean;
      image_openai: boolean;
      image_models?: string[];
    }>("/api/marketplace/ai/capabilities"),

  draftListingPackage: async (body: {
    kind: "product" | "lodging";
    title: string;
    price: number;
    location: string;
    category?: string;
  }): Promise<{ description: string; guide: ListingGuide }> => {
    const res = await fetch("/api/marketplace/ai/draft-package", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(`draftListingPackage ${res.status}: ${t}`);
    }
    return res.json();
  },

  ocrListingDraft: (body: { images_base64: string[]; hint_tab?: ListingTab }) =>
    postJson<OcrListingDraft>("/api/marketplace/ocr/listing-draft", body),

  draftListingDescription: async (body: {
    kind: "product" | "lodging";
    title: string;
    price: number;
    location: string;
  }): Promise<{ description: string }> => {
    const res = await fetch("/api/marketplace/ai/draft-description", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(`draftListingDescription ${res.status}: ${t}`);
    }
    return res.json();
  },

  enhanceImagePrompt: async (body: {
    kind: "product" | "lodging";
    title: string;
    location: string;
    category?: string;
    description?: string;
    user_hint?: string;
  }) => {
    const res = await fetch("/api/marketplace/ai/enhance-image-prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`enhanceImagePrompt ${res.status}`);
    return res.json() as Promise<{ prompt_en: string; summary_ko: string }>;
  },

  draftListingImage: async (body: {
    kind: "product" | "lodging";
    title: string;
    location: string;
    category?: string;
    description?: string;
    prompt_en?: string;
  }): Promise<{ image_base64: string; mime_type: string; prompt_used?: string }> => {
    const res = await fetch("/api/marketplace/ai/draft-image", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(`draftListingImage ${res.status}: ${t}`);
    }
    return res.json();
  },

  createListing: async (body: {
    kind: "product" | "lodging";
    category?: string;
    seller_id?: string;
    title: string;
    description: string;
    price: number;
    location: string;
    emoji?: string | null;
    stock?: number | null;
    max_guests?: number | null;
    cover_image_base64?: string | null;
    guide?: ListingGuide | null;
    variants?: ListingVariant[] | null;
    details?: ListingDetails | null;
  }): Promise<Listing> => {
    const res = await fetch("/api/marketplace/listings", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        ...body,
        seller_id: body.seller_id ?? "seller-local",
      }),
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const j = (await res.json()) as { detail?: string };
        if (j.detail) detail = j.detail;
      } catch {
        /* */
      }
      throw new Error(detail);
    }
    return res.json();
  },

  deleteListing: async (id: string) => {
    const res = await fetch(`/api/marketplace/listings/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (!res.ok) throw new Error(`deleteListing ${res.status}`);
    return res.json() as Promise<{ ok: boolean }>;
  },

  updateListing: async (
    id: string,
    body: {
      kind: "product" | "lodging";
      category?: string;
      seller_id?: string;
      title: string;
      description: string;
      price: number;
      location: string;
      emoji?: string | null;
      stock?: number | null;
      max_guests?: number | null;
      cover_image_base64?: string | null;
      guide?: ListingGuide | null;
      variants?: ListingVariant[] | null;
      details?: ListingDetails | null;
    }
  ): Promise<Listing> => {
    const res = await fetch(`/api/marketplace/listings/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ ...body, seller_id: body.seller_id ?? "seller-local" }),
    });
    if (!res.ok) throw new Error(await errorDetail(res, "수정에 실패했습니다."));
    return res.json();
  },

  createOrder: async (body: {
    items: {
      listing_id: string;
      quantity: number;
      stay_start?: string | null;
      stay_end?: string | null;
    }[];
    buyer_name: string;
    buyer_phone: string;
    stay_start?: string | null;
    stay_end?: string | null;
  }): Promise<Order> => {
    const res = await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const j = (await res.json()) as { detail?: string };
        if (j.detail) detail = j.detail;
      } catch {
        /* */
      }
      throw new Error(detail);
    }
    return res.json();
  },

  getListingBookings: (listingId: string) =>
    getJson<{
      booked_dates: string[];
      capacity: number | null;
      booked_counts: Record<string, number>;
    }>(`/api/marketplace/listings/${listingId}/bookings`),

  addListingPhoto: (listingId: string, body: { image_base64?: string; url?: string }) =>
    postJson<ListingPhoto>(`/api/marketplace/listings/${listingId}/photos`, body),

  deleteListingPhoto: (listingId: string, photoId: string) =>
    fetch(`/api/marketplace/listings/${listingId}/photos/${photoId}`, {
      method: "DELETE",
      headers: authHeaders(),
    }).then((r) => {
      if (!r.ok) throw new Error(`deleteListingPhoto ${r.status}`);
      return r.json() as Promise<{ ok: boolean }>;
    }),

  mockPay: async (orderId: string): Promise<Order> => {
    const res = await fetch(`/api/orders/${orderId}/mock-pay`, {
      method: "POST",
      headers: authHeaders(),
    });
    if (!res.ok) throw new Error(await errorDetail(res, "결제에 실패했습니다."));
    return res.json();
  },

  cardPayDemo: async (orderId: string): Promise<Order> => {
    const res = await fetch(`/api/orders/${orderId}/card-pay`, {
      method: "POST",
      headers: authHeaders(),
    });
    if (!res.ok) throw new Error(await errorDetail(res, "결제에 실패했습니다."));
    return res.json();
  },

  voiceTurn: async (
    audio: Blob,
    history: Turn[],
    mode: VoiceMode,
    timeoutMs = 120_000,
    formState?: Record<string, unknown>
  ): Promise<VoiceTurnResponse> => {
    const fd = new FormData();
    fd.append("audio", audio, "speech.wav");
    fd.append("history", JSON.stringify(history));
    fd.append("mode", mode);
    if (formState && Object.keys(formState).length > 0) {
      fd.append("form_state", JSON.stringify(formState));
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch("/api/voice/turn", {
        method: "POST",
        body: fd,
        signal: controller.signal,
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`voiceTurn ${res.status}: ${detail}`);
      }
      return res.json();
    } catch (e: unknown) {
      if (e instanceof Error && e.name === "AbortError") {
        throw new Error("음성 처리 시간이 길어졌어요. 잠시 후 다시 말씀해 주세요.");
      }
      throw e;
    } finally {
      clearTimeout(timer);
    }
  },

  /** LLM 호출 없이 ASR 만 — 단일 폼 필드를 음성으로 채울 때. */
  transcribeAudio: async (
    audioBlob: Blob,
    timeoutMs = 12_000
  ): Promise<{ text: string; raw: string }> => {
    const fd = new FormData();
    fd.append("audio", audioBlob, "audio.wav");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch("/api/voice/asr", {
        method: "POST",
        body: fd,
        signal: controller.signal,
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`transcribeAudio ${res.status}: ${detail}`);
      }
      return res.json();
    } finally {
      clearTimeout(timer);
    }
  },

  textTurn: async (
    user_text: string,
    history: Turn[],
    mode: VoiceMode
  ): Promise<VoiceTurnResponse> => {
    const res = await fetch("/api/voice/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_text, history, mode }),
    });
    if (!res.ok) throw new Error(`textTurn ${res.status}`);
    return res.json();
  },
};
