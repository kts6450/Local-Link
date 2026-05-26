import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "../lib/api";
import { LocalLinkLogo } from "../components/brand/LocalLinkLogo";
import { useAuth } from "../store/auth";

export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const setSession = useAuth((s) => s.setSession);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showMaster, setShowMaster] = useState(false);

  const roleHint =
    params.get("role") === "seller"
      ? "seller"
      : params.get("role") === "consumer"
        ? "consumer"
        : "consumer";

  const afterLogin = (role: string) => {
    if (role === "master" || role === "seller") {
      navigate("/seller/dashboard", { replace: true });
    } else {
      navigate("/", { replace: true });
    }
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api.login({ email: email.trim(), password });
      setSession(r.token, r.user);
      afterLogin(r.user.role);
    } catch (err) {
      setError(err instanceof Error ? err.message : "로그인에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      <aside className="lg:w-[42%] bg-gradient-to-br from-shop-teal via-shop-tealDark to-brand-greenDark text-white px-8 py-12 lg:py-16 flex flex-col justify-center">
        <LocalLinkLogo variant="inverse" size="lg" />
        <h1 className="mt-10 text-3xl sm:text-4xl font-bold leading-tight tracking-tight">
          회원만 이용할 수 있어요
        </h1>
        <p className="mt-5 text-white/85 text-lg leading-relaxed max-w-sm">
          가입한 이메일로 로그인하세요. 구매자와 공급자는 각각 다른 화면으로
          연결됩니다.
        </p>
      </aside>

      <main className="flex-1 flex flex-col justify-center px-6 py-12 sm:px-12 bg-brand-cream">
        <h2 className="text-2xl font-bold text-hades-text">로그인</h2>
        <p className="mt-2 text-hades-muted">
          {roleHint === "seller"
            ? "공급자 계정은 판매·주문 관리 전용입니다. 쇼핑·구매는 구매자 계정으로 따로 가입해 주세요."
            : "구매자 계정으로 쇼핑몰에 들어갑니다."}
        </p>

        <form onSubmit={onSubmit} className="mt-8 max-w-md space-y-4">
          <label className="block">
            <span className="text-sm font-semibold text-hades-text">이메일</span>
            <input
              type="email"
              className="input-field mt-1.5"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-hades-text">비밀번호</span>
            <input
              type="password"
              className="input-field mt-1.5"
              autoComplete="current-password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error ? (
            <p className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </p>
          ) : null}
          <button type="submit" className="btn-shop w-full py-3.5" disabled={busy}>
            {busy ? "확인 중…" : "로그인"}
          </button>
        </form>

        <p className="mt-6 text-sm text-hades-muted">
          아직 계정이 없으신가요?{" "}
          <Link
            to={`/signup?role=${roleHint}`}
            className="font-semibold text-shop-tealDark hover:underline"
          >
            회원가입
          </Link>
        </p>

        <div className="mt-10 pt-6 border-t border-hades-line max-w-md">
          <button
            type="button"
            className="text-sm text-hades-muted hover:text-hades-text"
            onClick={() => setShowMaster((v) => !v)}
          >
            {showMaster ? "운영자 로그인 닫기" : "운영자(마스터) 로그인"}
          </button>
          {showMaster ? (
            <p className="mt-2 text-xs text-hades-muted leading-relaxed">
              `.env`의 <code className="text-xs">LOCAL_LINK_MASTER_EMAIL</code> /{" "}
              <code className="text-xs">LOCAL_LINK_MASTER_PASSWORD</code> 로 로그인합니다.
              일반 회원 DB와 별도입니다.
            </p>
          ) : null}
        </div>
      </main>
    </div>
  );
}
