import { create } from "zustand";

/** 상품 등록 폼 ↔ 음성 도우미 연동 (AI 작성·사진 생성 등) */
export type SellerVoiceAction = "ai_write" | "ai_image" | "submit";

export interface SellerFormVoiceHandlers {
  onAiWrite?: () => Promise<void>;
  onAiImage?: () => Promise<void>;
  onSubmit?: () => Promise<void>;
}

interface SellerFormVoiceState {
  handlers: SellerFormVoiceHandlers | null;
  lastAction: SellerVoiceAction | null;
  register: (h: SellerFormVoiceHandlers) => void;
  unregister: () => void;
  runAction: (action: SellerVoiceAction) => Promise<boolean>;
  setLastAction: (a: SellerVoiceAction | null) => void;
}

export const useSellerFormVoice = create<SellerFormVoiceState>((set, get) => ({
  handlers: null,
  lastAction: null,
  register: (handlers) => set({ handlers }),
  unregister: () => set({ handlers: null, lastAction: null }),
  setLastAction: (lastAction) => set({ lastAction }),
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
