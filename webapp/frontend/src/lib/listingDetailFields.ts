/** 등록 탭별 상세 정보 필드 — 상품 / 체험 / 숙박 */

import type { ListingDetails } from "../types";
import type { ListingTab } from "./listingTabs";

export type DetailFieldKey = keyof ListingDetails;

export type DetailFieldDef = {
  key: DetailFieldKey;
  label: string;
  placeholder: string;
  hint: string;
  voiceHint: string;
  wide?: boolean;
};

export const PRODUCT_DETAIL_FIELDS: DetailFieldDef[] = [
  {
    key: "unit",
    label: "단위",
    placeholder: "kg / 개 / 박스 / 묶음",
    hint: "옵션이 없으면 1개를 어떻게 파는지 적어 주세요.",
    voiceHint: "단위를 말로 채우기 (예: 1킬로, 한 봉지)",
  },
  {
    key: "origin",
    label: "원산지·생산지",
    placeholder: "경상북도 포항시 북구 기계면",
    hint: "동네보다 더 자세하게 — 농가가 있는 곳까지.",
    voiceHint: "원산지를 말로 채우기",
  },
  {
    key: "producer",
    label: "생산자·농가명",
    placeholder: "기계 햇살 농원",
    hint: "",
    voiceHint: "농가·생산자 이름을 말로 채우기",
  },
  {
    key: "shelf_life",
    label: "유통기한",
    placeholder: "냉장 7일 / 1년",
    hint: "",
    voiceHint: "유통기한을 말로 채우기",
  },
  {
    key: "storage_method",
    label: "보관 방법",
    placeholder: "서늘하고 통풍 잘 되는 곳 (실온/냉장/냉동)",
    hint: "",
    voiceHint: "보관 방법을 말로 채우기",
    wide: true,
  },
];

export const EXPERIENCE_DETAIL_FIELDS: DetailFieldDef[] = [
  {
    key: "duration",
    label: "소요 시간",
    placeholder: "약 3시간 / 09:00~12:00",
    hint: "체험 전체 시간이나 시작·종료 시간을 적어 주세요.",
    voiceHint: "소요 시간을 말로 채우기",
  },
  {
    key: "meeting_point",
    label: "모임 장소",
    placeholder: "강릉항 2부두 앞 주차장",
    hint: "찾아오실 곳을 구체적으로 적어 주세요.",
    voiceHint: "모임 장소를 말로 채우기",
  },
  {
    key: "includes",
    label: "포함 사항",
    placeholder: "낚시대·미끼·간식, 사진 촬영",
    hint: "참가비에 포함되는 것을 적어 주세요.",
    voiceHint: "포함 사항을 말로 채우기",
  },
  {
    key: "what_to_bring",
    label: "준비물",
    placeholder: "편한 복장, 선크림, 개인 물병",
    hint: "손님이 챙겨 오면 좋은 것을 적어 주세요.",
    voiceHint: "준비물을 말로 채우기",
  },
  {
    key: "min_age",
    label: "참가 연령",
    placeholder: "만 7세 이상 / 보호자 동반",
    hint: "",
    voiceHint: "참가 연령을 말로 채우기",
  },
  {
    key: "weather_policy",
    label: "날씨·취소 안내",
    placeholder: "강풍·폭우 시 일정 변경 또는 환불",
    hint: "",
    voiceHint: "날씨·취소 안내를 말로 채우기",
    wide: true,
  },
];

export const LODGING_DETAIL_FIELDS: DetailFieldDef[] = [
  {
    key: "check_in",
    label: "체크인",
    placeholder: "15:00 이후",
    hint: "",
    voiceHint: "체크인 시간을 말로 채우기",
  },
  {
    key: "check_out",
    label: "체크아웃",
    placeholder: "11:00 이전",
    hint: "",
    voiceHint: "체크아웃 시간을 말로 채우기",
  },
  {
    key: "amenities",
    label: "편의 시설",
    placeholder: "와이파이, 주차, 에어컨, 세탁기",
    hint: "",
    voiceHint: "편의 시설을 말로 채우기",
  },
  {
    key: "breakfast",
    label: "조식",
    placeholder: "한식 조식 포함 / 미제공",
    hint: "",
    voiceHint: "조식 안내를 말로 채우기",
  },
  {
    key: "parking",
    label: "주차",
    placeholder: "무료 주차 2대 / 마을 공영주차장 이용",
    hint: "",
    voiceHint: "주차 안내를 말로 채우기",
  },
  {
    key: "pet_policy",
    label: "반려동물",
    placeholder: "소형견 가능 / 불가",
    hint: "",
    voiceHint: "반려동물 안내를 말로 채우기",
    wide: true,
  },
];

export function detailFieldsForTab(tab: ListingTab): DetailFieldDef[] {
  if (tab === "experience") return EXPERIENCE_DETAIL_FIELDS;
  if (tab === "lodging") return LODGING_DETAIL_FIELDS;
  return PRODUCT_DETAIL_FIELDS;
}

export function detailSectionMeta(tab: ListingTab): {
  emoji: string;
  title: string;
  subtitle: string;
} {
  if (tab === "experience") {
    return {
      emoji: "🧺",
      title: "체험 상세 정보",
      subtitle: "선택 — 일정·준비물을 적으면 예약하는 분이 편해요",
    };
  }
  if (tab === "lodging") {
    return {
      emoji: "🏠",
      title: "숙박 상세 정보",
      subtitle: "선택 — 체크인·편의시설을 적어 주세요",
    };
  }
  return {
    emoji: "📦",
    title: "상품 상세 정보",
    subtitle: "선택 — 적으면 구매하는 분이 더 잘 알아봐요",
  };
}
