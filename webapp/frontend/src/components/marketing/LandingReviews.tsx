const REVIEWS = [
  {
    name: "김영희",
    role: "홍천 사과농장",
    text: "70대 어머니도 5분이면 등록하세요. 음성으로 말하면 AI가 알아서 채워줘요.",
    avatar: "🧓🏻",
    stars: 5,
  },
  {
    name: "박철수",
    role: "강릉 갯벌체험",
    text: "주문 관리가 한눈에 보여서 놓치는 게 없어요. 알림톡 초안도 AI가 써줍니다.",
    avatar: "👨🏻‍🌾",
    stars: 5,
  },
  {
    name: "이순자",
    role: "순창 고추장",
    text: "아버지가 사진 찍어서 10분 만에 올리셨어요. OCR이 손글씨도 읽어요.",
    avatar: "👵🏻",
    stars: 5,
  },
];

export function LandingReviews() {
  return (
    <section className="rounded-[2rem] bg-brand-warm/80 border border-brand-line/60 px-6 sm:px-10 py-14 sm:py-20">
      <div className="text-center max-w-2xl mx-auto mb-12 sm:mb-14">
        <p className="eyebrow justify-center mb-4 inline-flex">Reviews</p>
        <h2 className="display-2 text-balance">이웃 판매자들의 실제 이용 후기</h2>
        <p className="mt-4 text-base sm:text-lg text-hades-muted">
          전국 농어촌 판매자들의 생생한 이야기
        </p>
      </div>
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {REVIEWS.map((r) => (
          <article
            key={r.name}
            className="bg-white rounded-[1.5rem] p-7 sm:p-8 shadow-card hover:shadow-card-hover transition-shadow flex flex-col"
          >
            <p className="text-amber-500 text-base mb-4 tracking-wider">
              {"★".repeat(r.stars)}
            </p>
            <p className="text-base sm:text-lg text-brand-ink leading-relaxed flex-1">
              &ldquo;{r.text}&rdquo;
            </p>
            <div className="mt-6 pt-5 border-t border-brand-line/60 flex items-center gap-3">
              <span className="h-12 w-12 rounded-full bg-brand-warm flex items-center justify-center text-2xl shrink-0">
                {r.avatar}
              </span>
              <div>
                <p className="font-bold text-base text-brand-ink">{r.name}</p>
                <p className="text-sm text-hades-muted">{r.role}</p>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
