export type UserRole = "consumer" | "seller" | "master";

export interface AuthUser {
  id: string;
  email: string;
  role: UserRole;
  display_name: string;
  seller_sector: string | null;
  seller_id: string | null;
}

export type Role = "user" | "assistant";

export interface Turn {
  role: Role;
  content: string;
}

export type VoiceMode = "consumer" | "seller";

export interface ConsumerSlots {
  listing_id?: string;
  quantity?: number;
  contact_name?: string;
  contact_phone?: string;
}

export interface SellerSlots {
  kind?: "product" | "lodging";
  title?: string;
  price?: number;
  description?: string;
  location?: string;
  stock?: number;
  max_guests?: number;
  emoji?: string;
}

export type VoiceSlots = ConsumerSlots & SellerSlots & Record<string, unknown>;

export interface VoiceTurnResponse {
  user_text: string;
  reply: string;
  slots: VoiceSlots;
  intent: string;
  ready_to_confirm: boolean;
  tts_url: string;
}

export type ListingCategory =
  | "experience"
  | "rural"
  | "fishing"
  | "craft"
  | "leisure"
  | "lodging";

export interface ListingGuideStep {
  time?: string;
  title: string;
  body: string;
}

export interface ListingGuideSpot {
  name: string;
  address?: string;
  hours?: string;
  holiday?: string;
  parking?: string;
}

/** 루플형 상품 상세 — 이용안내·체험 STEP */
export interface ListingGuide {
  highlights?: string[];
  steps?: ListingGuideStep[];
  included?: string[];
  not_included?: string[];
  precautions?: string[];
  refund_policy?: string;
  meeting_place?: string;
  address?: string;
  nearby?: ListingGuideSpot[];
}

export interface ListingPhoto {
  id: string;
  url: string;
  sort_order: number;
  created_at?: string;
}

export interface ListingVariant {
  label: string;
  price: number;
  stock?: number;
}

/** 상품 상세 정보 — 모든 필드 옵션. 빈 값은 저장하지 않음. */
export interface ListingDetails {
  unit?: string;
  origin?: string;
  producer?: string;
  shelf_life?: string;
  storage_method?: string;
  certification?: string;
  shipping_when?: string;
  min_order?: string;
  ingredients?: string;
  allergens?: string;
}

export interface Listing {
  id: string;
  seller_id: string;
  category?: ListingCategory;
  kind: "product" | "lodging";
  title: string;
  description: string;
  price: number;
  emoji: string;
  location: string;
  stock: number | null;
  max_guests: number | null;
  created_at: string;
  cover_image_url?: string | null;
  guide?: ListingGuide | null;
  variants?: ListingVariant[] | null;
  details?: ListingDetails | null;
  photos?: ListingPhoto[];
  rating?: number;
  review_count?: number;
}

export interface AssistantCard {
  id: string;
  kind: "product" | "lodging";
  category?: ListingCategory;
  title: string;
  price: number;
  location: string;
  cover_image_url?: string | null;
  rating: number;
  review_count: number;
}

export interface AssistantTurn {
  role: "user" | "assistant";
  content: string;
  cards?: AssistantCard[];
}

export interface AssistantReply {
  reply: string;
  recommendations: AssistantCard[];
}

export interface Brand {
  name: string;
  name_en?: string;
  tagline: string;
  description: string;
}

export interface VoiceStatus {
  asr_backend: string;
  llm_configured: boolean;
  asr_backend_class?: string;
  asr_is_dummy?: boolean;
  env_ttt_asr_backend?: string;
  env_ttt_model_path?: string;
  model_requested?: string | null;
  model_resolved_before_load?: string;
  model_loaded_path?: string | null;
  device?: string | null;
  local_whisper_checkpoint_ok?: boolean | null;
  using_openai_whisper_small_fallback?: boolean;
}

export interface CartLine {
  listingId: string;
  quantity: number;
  stay_start?: string | null;
  stay_end?: string | null;
  /** 옵션 라벨 (예: "200g"). 없으면 단일가 상품. */
  variant_label?: string | null;
  /** 옵션 가격(원) — 라벨과 함께 저장해 두면 추후 옵션이 바뀌어도 결제 금액은 보존. */
  variant_price?: number | null;
}

export interface OrderItem {
  listing_id: string;
  title: string;
  quantity: number;
  unit_price: number;
}

export type FulfillmentStatus =
  | "pending"
  | "preparing"
  | "shipping"
  | "completed"
  | "cancelled";

export interface Order {
  id: string;
  created_at: string;
  buyer_id?: string | null;
  buyer_name: string;
  buyer_phone: string;
  items: OrderItem[];
  total: number;
  payment_status: string;
  fulfillment_status: FulfillmentStatus;
  stay_start?: string | null;
  stay_end?: string | null;
  payment?: { transaction_id?: string } | null;
}

export interface FeatureFlagItem {
  id: string;
  enabled: boolean;
  label: string;
  message: string;
}
