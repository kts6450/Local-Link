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

      if (blob.size < 8000) {
        setError("녹음이 너무 짧아요. 마이크를 누른 뒤 천천히 말씀해 주세요.");
        setPhase("error");
        return;
      }

      // 폼에 이미 채워진 값(OCR/직접 입력)을 LLM 이 알 수 있도록 함께 전송.
      // 단, 사용자가 "처음부터 다시 시작" 을 선택했다면 폼 상태를 보내지 않는다.
      const sfvState = useSellerFormVoice.getState();
      // startMode 가 null 이면 폼이 비어있다는 뜻이므로 그대로 보내도 된다 (모두 빈 값).
      const sendFormState = sfvState.startMode !== "fresh";
      const formSnapshot = sendFormState ? sfvState.snapshotForm() : {};
      const result = await api.voiceTurn(
        blob,
        history,
        "seller",
        undefined,
        formSnapshot as unknown as Record<string, unknown>
      );

      if (result.user_text) appendUser(result.user_text);
      appendAssistant(result.reply);
      mergeSlots(result.slots);
      setReadyToConfirm(result.ready_to_confirm);

      const intent = result.intent || voiceIntentFromText(result.user_text);
      if (intent === "ai_write") {
        await useSellerFormVoice.getState().runAction("ai_write");
      } else if (intent === "ai_image") {
        await useSellerFormVoice.getState().runAction("ai_image");
      } else if (intent === "ocr_note") {
        // 노트 OCR 패널을 시각적으로 강조하고 안내 메시지 추가.
        // (파일 입력은 브라우저 보안상 사용자 클릭이 필요해서 자동 트리거 불가)
        useSellerFormVoice.getState().setHighlight("note_ocr");
        appendAssistant(
          "네, 화면 왼쪽 「노트 사진으로 채우기」 칸에서 사진을 골라 주세요. 사진을 읽어 자동으로 채워 드릴게요."
        );
      }

      const merged = useConversation.getState().slots;

      if (result.ready_to_confirm && result.intent === "confirm") {
        const kind = merged.kind === "lodging" ? "lodging" : "product";
        const title = String(merged.title || "").trim();
        const price = Number(merged.price);
        if (title && price >= 0 && (kind === "product" || kind === "lodging")) {
          try {
            let description = String(merged.description || "").trim();
            const location = String(merged.location || "").trim();

            // 슬롯 category 를 우선 사용. 비어있으면 sellerSector(=rural 등) fallback.
            // 체험 키워드("체험·축제·견학" 등) 가 들어 있으면 강제 experience.
            const slotCategory = String(merged.category || "").trim();
            const blob = `${title} ${description}`;
            const looksExperience =
              slotCategory === "experience" ||
              /(체험|축제|투어|견학|수확\s*체험|낚시\s*체험|갯벌|만들기\s*체험|승마|트레킹|요리\s*교실)/.test(
                blob
              );
            const category =
              kind === "lodging"
                ? "lodging"
                : looksExperience
                  ? "experience"
                  : slotCategory || sellerSector || "rural";

            const descTask =
              !description || description.length < 12
                ? api
                  .draftListingPackage({
                    kind,
                    title,
                    price: Math.round(price),
                    location,
                    category,
                  })
                  .then((r) => ({ description: r.description, guide: r.guide }))
                  .catch(() => ({ description, guide: null }))
                : Promise.resolve({ description, guide: null });

            const { description: finalDesc, guide } = await descTask;
            // prompt 에 매 호출 고유 토큰을 붙여 Pollinations 캐시 hit 을 차단.
            // (백엔드에도 random seed 가 적용돼 있어 이중 보험)
            const variantTag = `__variant_${Date.now()}_${Math.random()
              .toString(36)
              .slice(2, 8)}`;
            const coverB64 = await api
              .enhanceImagePrompt({
                kind,
                title,
                location,
                category,
                description: finalDesc,
              })
              .then((enh) =>
                api.draftListingImage({
                  kind,
                  title,
                  location,
                  category,
                  description: finalDesc,
                  prompt_en: `${enh.prompt_en} ${variantTag}`,
                })
              )
              .then((r) => r.image_base64)
              .catch(() => undefined);

            await api.createListing({
              kind,
              category,
              seller_id: sellerId ?? undefined,
              title,
              description: finalDesc,
              price: Math.round(price),
              location,
              emoji: merged.emoji ? String(merged.emoji) : undefined,
              stock:
                kind === "product"
                  ? merged.stock != null
                    ? Number(merged.stock)
                    : category === "experience"
                      ? 20
                      : 99
                  : null,
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
            appendAssistant("등록이 완료되었습니다. 감사합니다.");
          } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e);
            setError(`등록 중 문제가 생겼어요. 오른쪽 폼에서 '다음'을 눌러 주세요. (${msg})`);
            setPhase("error");
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
      setPhase("error");
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
    sellerId,
    sellerSector,
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
  // OCR(노트 사진으로 채우기)을 가장 먼저 잡는다 — "사진" 키워드가 ai_image 와
  // 충돌할 수 있으므로 더 구체적인 패턴을 우선.
  if (
    /(노트|메모|수첩|적어\s*둔|적힌)\s*사진/.test(t) ||
    /사진(으|을|로)?\s*(보고|읽고|읽어|채워|채우|올려|입력)/.test(t) ||
    /OCR/i.test(t)
  ) {
    return "ocr_note";
  }
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
  // 말하는 속도를 1.1배속으로 설정 (1.2배속은 조금 빨라 미세 조정)
  audio.defaultPlaybackRate = 1.1;
  audio.playbackRate = 1.1;
  ref.current = audio;

  audio.addEventListener("ended", () => {
    useConversation.getState().setPhase("idle");
  });
  audio.addEventListener("error", () => {
    useConversation.getState().setPhase("idle");
  });

  // 브라우저가 오디오를 로드할 때 재생 속도가 1.0으로 초기화되는 현상을 방지하기 위해 이벤트 리스너로 이중 설정
  audio.addEventListener("canplaythrough", () => {
    audio.playbackRate = 1.1;
  });

  audio.play().catch(() => {
    useConversation.getState().setPhase("idle");
  });
}
