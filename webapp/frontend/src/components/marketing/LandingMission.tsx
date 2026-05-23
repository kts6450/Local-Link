export function LandingMission() {
  return (
    <section className="mb-14 grid lg:grid-cols-2 gap-10 items-center">
      <p className="text-sm text-hades-muted font-medium">/ Seller Guide</p>
      <div>
        <h2 className="text-2xl sm:text-3xl font-bold text-brand-ink leading-snug">
          어르신도 쉽게 쓰는
          <br />
          스마트폰 등록 시스템
        </h2>
        <p className="mt-4 text-hades-muted leading-relaxed">
          로컬링크는 농어촌·어촌·산간 지역의 소상공인과 어르신 판매자를 위해 만들어졌습니다.
          복잡한 앱 입력 대신 음성과 사진만으로 상품 설명과 사진까지 AI가 생성합니다.
        </p>
        <p className="mt-6 text-xs font-bold text-brand-orange flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-brand-orange" />
          Our Mission
        </p>
        <div className="mt-4 flex items-center gap-3">
          <div className="flex -space-x-2">
            {["🧑‍🌾", "👩‍🍳", "🧓", "👨‍🌾"].map((e, i) => (
              <span
                key={i}
                className="h-9 w-9 rounded-full bg-brand-warm border-2 border-white flex items-center justify-center text-sm"
              >
                {e}
              </span>
            ))}
          </div>
          <p className="text-sm text-hades-muted">
            전국 <strong className="text-brand-ink">1,200여 명</strong>의 판매자가 함께하고
            있습니다
          </p>
        </div>
      </div>
    </section>
  );
}
