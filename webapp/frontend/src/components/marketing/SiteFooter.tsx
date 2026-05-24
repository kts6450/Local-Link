import { Link } from "react-router-dom";

import { LocalLinkLogo } from "../brand/LocalLinkLogo";

const COLS: { title: string; items: { label: string; to: string }[] }[] = [
  {
    title: "판매자",
    items: [
      { label: "상품 관리", to: "/seller/dashboard" },
      { label: "주문 처리", to: "/seller/orders" },
      { label: "AI 등록", to: "/seller/products" },
      { label: "SNS 홍보", to: "/seller/sns" },
    ],
  },
  {
    title: "구매자",
    items: [
      { label: "지역 특산품", to: "/" },
      { label: "숙박 예약", to: "/?kind=lodging" },
      { label: "체험", to: "/?theme=experience" },
      { label: "장바구니", to: "/checkout" },
    ],
  },
  {
    title: "고객센터",
    items: [
      { label: "FAQ", to: "#" },
      { label: "1:1 문의", to: "#" },
      { label: "공지사항", to: "#" },
      { label: "이용약관", to: "#" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="mt-auto bg-brand-ink text-white">
      <div className="page-shell pt-16 lg:pt-20 pb-8">
        <div className="grid gap-12 lg:grid-cols-[1.4fr_2fr]">
          <div className="max-w-md">
            <LocalLinkLogo variant="footer" size="lg" className="mb-6" />
            <p className="text-base leading-relaxed text-white/70">
              농어촌 소상공인과 이웃 구매자를 잇는
              <br />
              스마트 마켓플레이스. 음성 한 번으로 등록하고,
              <br />
              AI가 도와드립니다.
            </p>
            <div className="mt-8 flex items-center gap-3">
              <a
                href="#"
                className="h-10 w-10 inline-flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 transition-colors"
                aria-label="Instagram"
              >
                📷
              </a>
              <a
                href="#"
                className="h-10 w-10 inline-flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 transition-colors"
                aria-label="YouTube"
              >
                ▶
              </a>
              <a
                href="#"
                className="h-10 w-10 inline-flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 transition-colors"
                aria-label="Kakao"
              >
                💬
              </a>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-8">
            {COLS.map((col) => (
              <div key={col.title}>
                <p className="font-bold text-white text-base mb-4">{col.title}</p>
                <ul className="space-y-3 text-sm text-white/65">
                  {col.items.map((it) => (
                    <li key={it.label}>
                      <Link
                        to={it.to}
                        className="hover:text-white transition-colors no-underline"
                      >
                        {it.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-16 pt-8 border-t border-white/10 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6">
          <p className="font-serif text-2xl sm:text-3xl text-white/90 italic tracking-wide">
            손으로 많이 치지 않아도 된다
          </p>
          <div className="text-xs text-white/50 leading-relaxed">
            © {new Date().getFullYear()} 로컬링크 Local Link
            <span className="mx-2 text-white/20">·</span>
            시연용 데모
          </div>
        </div>
      </div>
    </footer>
  );
}
