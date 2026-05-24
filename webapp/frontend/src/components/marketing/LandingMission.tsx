export function LandingMission() {
  return (
    <section className="grid lg:grid-cols-[1fr_1.2fr] gap-12 lg:gap-16 items-center">
      <div className="relative">
        <div className="aspect-[4/5] rounded-[2rem] overflow-hidden bg-brand-warm shadow-card-hover">
          <img
            src="https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=1200&q=85"
            alt=""
            className="h-full w-full object-cover"
          />
        </div>
        <div className="absolute -bottom-6 -right-4 sm:right-8 bg-white rounded-2xl shadow-card-hover p-5 sm:p-6 max-w-[18rem]">
          <div className="flex items-center gap-3 mb-3">
            <div className="flex -space-x-2">
              {["🧑‍🌾", "👩‍🍳", "🧓", "👨‍🌾"].map((e, i) => (
                <span
                  key={i}
                  className="h-9 w-9 rounded-full bg-brand-warm border-2 border-white flex items-center justify-center text-base"
                >
                  {e}
                </span>
              ))}
            </div>
          </div>
          <p className="text-sm text-hades-muted">
            전국 <strong className="text-brand-ink text-base">1,200여 명</strong>의<br />
            판매자가 함께하고 있습니다
          </p>
        </div>
      </div>

      <div>
        <p className="eyebrow mb-4">Our Mission</p>
        <h2 className="display-2 text-balance">
          어르신도 쉽게 쓰는
          <br />
          스마트폰 등록 시스템
        </h2>
        <p className="mt-6 text-base sm:text-lg text-hades-muted leading-relaxed">
          로컬링크는 농어촌·어촌·산간 지역의 소상공인과 어르신 판매자를 위해
          만들어졌습니다. 복잡한 앱 입력 대신 음성과 사진만으로 상품 설명과
          사진까지 AI가 자동으로 생성합니다.
        </p>
        <ul className="mt-8 space-y-4">
          {[
            { k: "음성 등록", v: "Whisper 파인튜닝 모델로 사투리·고령자 음성 인식" },
            { k: "OCR", v: "Claude Vision이 손글씨 메모를 자동 폼 채움" },
            { k: "AI 글쓰기", v: "Multi-agent 파이프라인으로 톤·SNS 카피 자동 생성" },
          ].map((it) => (
            <li key={it.k} className="flex items-start gap-4">
              <span className="mt-1 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-ink text-white text-xs font-bold">
                ✓
              </span>
              <div>
                <p className="font-bold text-base text-brand-ink">{it.k}</p>
                <p className="mt-0.5 text-sm sm:text-base text-hades-muted leading-relaxed">
                  {it.v}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
