import { create } from "zustand";

/** 상품 등록 폼 ↔ 음성 도우미 연동 (AI 작성·사진 생성 등) */
export type SellerVoiceAction = "ai_write" | "ai_image" | "submit";
export type SellerHighlight = null | "note_ocr" | "voice";

export interface SellerFormSnapshot {
  title?: string;
  price?: number | string;
  description?: string;
  location?: string;
  listing_tab?: "product" | "lodging" | "experience";
  stock?: number | string;
  max_guests?: number | string;
}

export interface SellerFormVoiceHandlers {
  onAiWrite?: () => Promise<void>;
  onAiImage?: () => Promise<void>;
  onSubmit?: () => Promise<void>;
  getFormState?: () => SellerFormSnapshot;
}

interface SellerFormVoiceState {
  handlers: SellerFormVoiceHandlers | null;
  lastAction: SellerVoiceAction | null;
  highlight: SellerHighlight;
  register: (h: SellerFormVoiceHandlers) => void;
  unregister: () => void;
  runAction: (action: SellerVoiceAction) => Promise<boolean>;
  setLastAction: (a: SellerVoiceAction | null) => void;
  setHighlight: (h: SellerHighlight) => void;
  /** 현재 폼에 채워져 있는 값을 안전하게 읽어 온다. */
  snapshotForm: () => SellerFormSnapshot;
}

export const useSellerFormVoice = create<SellerFormVoiceState>((set, get) => ({
  handlers: null,
  lastAction: null,
  highlight: null,
  register: (handlers) => set({ handlers }),
  unregister: () => set({ handlers: null, lastAction: null, highlight: null }),
  setLastAction: (lastAction) => set({ lastAction }),
  snapshotForm: () => {
    const fn = get().handlers?.getFormState;
    if (!fn) return {};
    try {
      return fn() ?? {};
    } catch {
      return {};
    }
  },
  setHighlight: (highlight) => {
    set({ highlight });
    if (highlight) {
      // 강조는 잠깐만 — 6초 뒤 자동 해제
      setTimeout(() => {
        if (get().highlight === highlight) set({ highlight: null });
      }, 6000);
    }
  },
  runAction: async (action) => {
    const h = get().handlers;
    if (!h) return false;
    set({ lastAction: action });
    try {
      if (action === "ai_write" && h.onAiWrite) {
        await h.onAiWrite();
        return true;
      }
      if (action === "ai_image" && h.onAiImage) {
        await h.onAiImage();
        return true;
      }
      if (action === "submit" && h.onSubmit) return true;
    } catch {
      return false;
    }
    return false;
  },
}));
