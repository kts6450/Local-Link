const STEPS = [
  { id: 1, icon: "📝", label: "기본 정보" },
  { id: 2, icon: "✨", label: "소개 · AI" },
  { id: 3, icon: "📷", label: "사진" },
  { id: 4, icon: "✅", label: "올리기" },
] as const;

export function SellerStepIndicator({
  current,
  onGo,
}: {
  current: number;
  onGo?: (step: number) => void;
}) {
  return (
    <nav aria-label="등록 단계" className="flex flex-wrap gap-2 sm:gap-3">
      {STEPS.map((s) => {
        const done = s.id < current;
        const active = s.id === current;
        return (
          <button
            key={s.id}
            type="button"
            onClick={() => onGo?.(s.id)}
            disabled={!onGo}
            className={[
              "flex items-center gap-2 rounded-2xl px-3 py-2 sm:px-4 sm:py-2.5 text-sm font-semibold transition-all border",
              active
                ? "bg-shop-teal text-white border-shop-teal shadow-md shadow-shop-teal/25"
                : done
                  ? "bg-shop-tealLight/80 text-shop-tealDark border-shop-teal/30"
                  : "bg-white text-slate-500 border-slate-200 hover:border-shop-teal/40",
            ].join(" ")}
          >
            <span
              className={[
                "flex h-8 w-8 items-center justify-center rounded-full text-base",
                active ? "bg-white/20" : "bg-slate-100",
              ].join(" ")}
              aria-hidden
            >
              {done ? "✓" : s.icon}
            </span>
            <span className="hidden sm:inline">{s.label}</span>
            <span className="sm:hidden">{s.id}단계</span>
          </button>
        );
      })}
    </nav>
  );
}

export { STEPS as SELLER_FORM_STEPS };
