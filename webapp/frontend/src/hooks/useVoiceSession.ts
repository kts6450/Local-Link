import { useCallback, useEffect, useRef, type MutableRefObject } from "react";

import { api } from "../lib/api";
import { startRecording } from "../lib/recorder";
import { useAuthSellerId, useAuthSellerSector } from "../store/auth";
import { useConversation, WELCOME_SELLER } from "../store/conversation";
import { useSellerFormVoice } from "../store/sellerFormVoice";

/**
 * 판매자 Zero UI — 음성으로 상품·숙박 등록
 */
export function useVoiceSession() {
  const sellerSector = useAuthSellerSector();
  const sellerId = useAuthSellerId();
  const stopperRef = useRef<null | (() => Promise<Blob>)>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const welcomePlayedRef = useRef(false);

  useEffect(() => {
    welcomePlayedRef.current = false;
    useConversation.getState().setVoiceMode("seller");
  }, []);

  const {
    history,
    phase,
    ttsEnabled,
    appendUser,
    appendAssistant,
    mergeSlots,
    setPhase,
    setError,
    setMicLevel,
    setReadyToConfirm,
    reset,
    setListingSubmitted,
  } = useConversation();

  const playWelcomeIfNeeded = useCallback(() => {
    if (welcomePlayedRef.current || !ttsEnabled) return;
    welcomePlayedRef.current = true;
    const url = `/api/voice/tts?text=${encodeURIComponent(WELCOME_SELLER)}`;
    playTTS(url, audioRef);
  }, [ttsEnabled]);

  const begin = useCallback(async () => {
    setError(null);
    playWelcomeIfNeeded();
    try {
      const handle = await startRecording((rms) => setMicLevel(rms));
      stopperRef.current = handle.stop;
      setPhase("recording");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(`마이크를 사용할 수 없어요: ${msg}`);
    }
  }, [setError, setPhase, setMicLevel, playWelcomeIfNeeded]);

  const finish = useCallback(async () => {
    if (!stopperRef.current) return;
    setPhase("thinking");
    setMicLevel(0);
    try {
      const blob = await stopperRef.current();
      stopperRef.current = null;

      const result = await api.voiceTurn(blob, history, "seller");

      if (result.user_text) appendUser(result.user_text);
      appendAssistant(result.reply);
      mergeSlots(result.slots);
      setReadyToConfirm(result.ready_to_confirm);

      const intent = result.intent || voiceIntentFromText(result.user_text);
      if (intent === "ai_write") {
        await useSellerFormVoice.getState().runAction("ai_write");
      } else if (intent === "ai_image") {
        await useSellerFormVoice.getState().runAction("ai_image");
      }

      const merged = useConversation.getState().slots;

      if (result.ready_to_confirm) {
        const kind = merged.kind === "lodging" ? "lodging" : "product";
        const title = String(merged.title || "").trim();
        const price = Number(merged.price);
        if (title && price >= 0 && (kind === "product" || kind === "lodging")) {
          try {
            let description = String(merged.description || "").trim();
            const location = String(merged.location || "").trim();

            const imgCat =
              kind === "lodging" ? "lodging" : (sellerSector ?? "rural");
            const descTask =
              !description || description.length < 12
                ? api
                    .draftListingPackage({
                      kind,
                      title,
                      price: Math.round(price),
                      location,
                      category: imgCat,
                    })
                    .then((r) => ({ description: r.description, guide: r.guide }))
                    .catch(() => ({ description, guide: null }))
                : Promise.resolve({ description, guide: null });

            const { description: finalDesc, guide } = await descTask;
            const coverB64 = await api
              .enhanceImagePrompt({
                kind,
                title,
                location,
                category: imgCat,
                description: finalDesc,
              })
              .then((enh) =>
                api.draftListingImage({
                  kind,
                  title,
                  location,
                  category: imgCat,
                  description: finalDesc,
                  prompt_en: enh.prompt_en,
                })
              )
              .then((r) => r.image_base64)
              .catch(() => undefined);

            const category =
              kind === "lodging" ? "lodging" : (sellerSector ?? "rural");
            await api.createListing({
              kind,
              category,
              seller_id: sellerId ?? undefined,
              title,
              description: finalDesc,
              price: Math.round(price),
              location,
              emoji: merged.emoji ? String(merged.emoji) : undefined,
              stock: kind === "product" ? (merged.stock != null ? Number(merged.stock) : 99) : null,
              max_guests:
                kind === "lodging"
                  ? merged.max_guests != null
                    ? Number(merged.max_guests)
                    : 4
                  : null,
              cover_image_base64: coverB64 ?? undefined,
              guide: guide ?? undefined,
            });
            reset("seller");
            welcomePlayedRef.current = false;
            setListingSubmitted(true);
          } catch {
            /* */
          }
        }
      }

      if (ttsEnabled && result.tts_url) {
        playTTS(result.tts_url, audioRef);
        setPhase("speaking");
      } else {
        setPhase("idle");
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(`처리 중 문제가 생겼어요: ${msg}`);
    }
  }, [
    history,
    appendUser,
    appendAssistant,
    mergeSlots,
    setPhase,
    setError,
    setMicLevel,
    setReadyToConfirm,
    setListingSubmitted,
    ttsEnabled,
    reset,
  ]);

  const toggle = useCallback(async () => {
    if (phase === "recording") {
      await finish();
    } else if (phase === "idle" || phase === "error") {
      await begin();
    }
  }, [phase, begin, finish]);

  return { toggle, phase };
}

function voiceIntentFromText(text: string): string | null {
  const t = (text || "").trim();
  if (/AI|글\s*써|소개\s*글|설명\s*써|설명\s*만들|한번에\s*써/i.test(t)) return "ai_write";
  if (/(사진|이미지|그림|대표\s*사진)/i.test(t) && /(만들|그려|생성|찍)/i.test(t)) {
    return "ai_image";
  }
  return null;
}

function playTTS(url: string, ref: MutableRefObject<HTMLAudioElement | null>) {
  if (ref.current) {
    ref.current.pause();
  }
  const audio = new Audio(url);
  ref.current = audio;
  audio.addEventListener("ended", () => {
    useConversation.getState().setPhase("idle");
  });
  audio.addEventListener("error", () => {
    useConversation.getState().setPhase("idle");
  });
  audio.play().catch(() => {
    useConversation.getState().setPhase("idle");
  });
}
