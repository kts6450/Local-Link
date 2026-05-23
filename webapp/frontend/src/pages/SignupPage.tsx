import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "../lib/api";
import { LocalLinkLogo } from "../components/brand/LocalLinkLogo";
import { LISTING_CATEGORIES, type ListingCategory } from "../lib/sellerSectors";
import { useAuth } from "../store/auth";

export function SignupPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const setSession = useAuth((s) => s.setSession);

  const initialRole = params.get("role") === "seller" ? "seller" : "consumer";
  const [role, setRole] = useState<"consumer" | "seller">(initialRole);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [sellerSector, setSellerSector] = useState<ListingCategory>("rural");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (password !== password2) {
      setError("비밀번호 확인이 일치하지 않습니다.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const r = await api.register({
        email: email.trim(),
        password,
        role,
        display_name: displayName.trim(),
        seller_sector: role === "seller" ? sellerSector : undefined,
      });
      setSession(r.token, r.user);
      navigate(role === "seller" ? "/seller/products" : "/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "가입에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      <aside className="lg:w-[42%] bg-gradient-to-br from-shop-teal via-shop-tealDark to-brand-greenDark text-white px-8 py-12 lg:py-16 flex flex-col justify-center">
        <LocalLinkLogo variant="inverse" size="lg" />
        <h1 className="mt-10 text-3xl sm:text-4xl font-bold leading-tight tracking-tight">
          로컬링크 회원가입
        </h1>
        <p className="mt-5 text-white/85 text-lg leading-relaxed max-w-sm">
          가입 즉시 이용할 수 있습니다. 공급자는 대표 업종을 정하고, 상품마다
          카테고리는 따로 고를 수 있어요.
        </p>
      </aside>

      <main className="flex-1 flex flex-col justify-center px-6 py-12 sm:px-12 bg-brand-cream">
        <h2 className="text-2xl font-bold text-hades-text">회원가입</h2>

        <form onSubmit={onSubmit} className="mt-8 max-w-lg space-y-5">
          <div>
            <p className="text-sm font-semibold text-hades-text mb-2">가입 유형</p>
            <div className="flex gap-2">
              <button
                type="button"
                className={role === "consumer" ? "btn-primary flex-1" : "btn-ghost flex-1"}
                onClick={() => setRole("consumer")}
              >
                구매자
              </button>
              <button
                type="button"
                className={role === "seller" ? "btn-primary flex-1" : "btn-ghost flex-1"}
                onClick={() => setRole("seller")}
              >
                공급자
              </button>
            </div>
          </div>

          <label className="block">
            <span className="text-sm font-semibold text-hades-text">이름</span>
            <input
              className="input-field mt-1.5"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="홍길동"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-hades-text">이메일</span>
            <input
              type="email"
              className="input-field mt-1.5"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-hades-text">비밀번호 (8자 이상)</span>
            <input
              type="password"
              className="input-field mt-1.5"
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-hades-text">비밀번호 확인</span>
            <input
              type="password"
              className="input-field mt-1.5"
              autoComplete="new-password"
              required
              minLength={8}
              value={password2}
              onChange={(e) => setPassword2(e.target.value)}
            />
          </label>

          {role === "seller" && (
            <div>
              <p className="text-sm font-semibold text-hades-text mb-2">대표 업종</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {LISTING_CATEGORIES.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setSellerSector(s.id)}
                    className={`rounded-xl border px-2 py-2 text-left text-sm transition-colors ${
                      sellerSector === s.id
                        ? "border-shop-teal bg-shop-tealLight font-bold text-shop-tealDark"
                        : "border-hades-line hover:border-shop-teal/40"
                    }`}
                  >
                    <span className="mr-1">{s.emoji}</span>
                    {s.short}
                  </button>
                ))}
              </div>
            </div>
          )}

          {error ? (
            <p className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </p>
          ) : null}

          <button type="submit" className="btn-shop w-full py-3.5" disabled={busy}>
            {busy ? "가입 중…" : "가입하고 시작하기"}
          </button>
        </form>

        <p className="mt-6 text-sm text-hades-muted">
          이미 계정이 있으신가요?{" "}
          <Link
            to={`/login?role=${role}`}
            className="font-semibold text-shop-tealDark hover:underline"
          >
            로그인
          </Link>
        </p>
      </main>
    </div>
  );
}
