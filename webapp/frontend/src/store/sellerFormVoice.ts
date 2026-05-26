import { create } from "zustand";

/** 상품 등록 폼 ↔ 음성 도우미 연동 (AI 작성·사진 생성 등) */
export type SellerVoiceAction = "ai_write" | "ai_image" | "submit";
export type SellerHighlight = null | "note_ocr" | "voice";
/**
 * 음성 도우미 시작 방식.
 * - null: 아직 사용자가 선택 안 함 (폼이 비어있으면 자동으로 "fresh")
 * - "continue": 지금까지 OCR/직접 입력으로 채운 내용으로 이어서 진행
 * - "fresh": 처음부터 새로 등록 (form_state 보내지 않음)
 */
export type SellerVoiceStartMode = null | "continue" | "fresh";

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
  startMode: SellerVoiceStartMode;
  register: (h: SellerFormVoiceHandlers) => void;
  unregister: () => void;
  runAction: (action: SellerVoiceAction) => Promise<boolean>;
  setLastAction: (a: SellerVoiceAction | null) => void;
  setHighlight: (h: SellerHighlight) => void;
  setStartMode: (m: SellerVoiceStartMode) => void;
  /** 현재 폼에 채워져 있는 값을 안전하게 읽어 온다. */
  snapshotForm: () => SellerFormSnapshot;
  /** 폼이 비어있는지 (모든 주요 필드가 비어있으면 true). */
  isFormEmpty: () => boolean;
}

export const useSellerFormVoice = create<SellerFormVoiceState>((set, get) => ({
  handlers: null,
  lastAction: null,
  highlight: null,
  startMode: null,
  register: (handlers) => set({ handlers }),
  unregister: () =>
    set({ handlers: null, lastAction: null, highlight: null, startMode: null }),
  setLastAction: (lastAction) => set({ lastAction }),
  setStartMode: (startMode) => set({ startMode }),
  snapshotForm: () => {
    const fn = get().handlers?.getFormState;
    if (!fn) return {};
    try {
      return fn() ?? {};
    } catch {
      return {};
    }
  },
  isFormEmpty: () => {
    const f = get().snapshotForm();
    const v = (x: unknown) =>
      x == null || (typeof x === "string" && x.trim() === "");
    return (
      v(f.title) &&
      v(f.price) &&
      v(f.description) &&
      v(f.location)
    );
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
