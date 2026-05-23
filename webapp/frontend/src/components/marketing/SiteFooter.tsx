import { Link } from "react-router-dom";

import { LocalLinkLogo } from "../brand/LocalLinkLogo";

export function SiteFooter() {
  return (
    <footer className="mt-auto bg-brand-ink text-white/90">
      <div className="page-shell py-12 lg:py-16">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-10">
          <div className="max-w-md">
            <LocalLinkLogo variant="footer" className="mb-4" />
            <p className="text-sm leading-relaxed text-white/70">
              농어촌 소상공인과 이웃 구매자를 잇는 스마트 마켓플레이스.
              <br />
              음성 한 번으로 등록하고, AI가 도와드립니다.
            </p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-8 text-sm">
            <div>
              <p className="font-bold text-white mb-3">판매자</p>
              <ul className="space-y-2 text-white/65">
                <li>
                  <Link to="/seller/dashboard" className="hover:text-white">
                    상품 관리
                  </Link>
                </li>
                <li>
                  <Link to="/seller/orders" className="hover:text-white">
                    주문 처리
                  </Link>
                </li>
                <li>
                  <Link to="/seller/products" className="hover:text-white">
                    AI 등록
                  </Link>
                </li>
              </ul>
            </div>
            <div>
              <p className="font-bold text-white mb-3">구매자</p>
              <ul className="space-y-2 text-white/65">
                <li>
                  <Link to="/" className="hover:text-white">
                    지역 특산품
                  </Link>
                </li>
                <li>
                  <Link to="/?kind=lodging" className="hover:text-white">
                    숙박 예약
                  </Link>
                </li>
                <li>
                  <Link to="/checkout" className="hover:text-white">
                    장바구니
                  </Link>
                </li>
              </ul>
            </div>
            <div>
              <p className="font-bold text-white mb-3">고객센터</p>
              <ul className="space-y-2 text-white/65">
                <li>FAQ</li>
                <li>1:1 문의</li>
                <li>공지사항</li>
              </ul>
            </div>
          </div>
        </div>
        <div className="mt-12 pt-8 border-t border-white/10 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-8">
          <p className="font-serif text-2xl sm:text-3xl text-white/90 italic">
            손으로 많이 치지 않아도 된다
          </p>
          <div className="text-xs text-white/50">
            © {new Date().getFullYear()} 로컬링크 Local Link · 시연용 데모
          </div>
        </div>
      </div>
    </footer>
  );
}
