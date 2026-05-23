type Props = {
  className?: string;
  /** 헤더(기본) | 푸터(밝은 톤) | 로그인 패널(반전) | 아이콘만 */
  variant?: "header" | "footer" | "inverse" | "icon";
  size?: "sm" | "md" | "lg";
};

const sizes = {
  sm: { icon: "h-8 w-8", title: "text-sm", sub: "text-[10px]" },
  md: { icon: "h-9 w-9 sm:h-10 sm:w-10", title: "text-base sm:text-lg", sub: "text-[11px] sm:text-xs" },
  lg: { icon: "h-12 w-12", title: "text-xl", sub: "text-sm" },
};

function LinkMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden>
      <circle cx="20" cy="20" r="20" className="fill-brand-ink" />
      <g fill="none" stroke="white" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M15.5 22.5c-2.8 0-5-2.2-5-5s2.2-5 5-5c1.4 0 2.6.6 3.5 1.5" />
        <path d="M24.5 17.5c2.8 0 5 2.2 5 5s-2.2 5-5 5c-1.4 0-2.6-.6-3.5-1.5" />
        <path d="M17.2 20.8l5.6-1.6" />
      </g>
    </svg>
  );
}

function LinkMarkFooter({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden>
      <circle cx="20" cy="20" r="20" className="fill-white/15" stroke="white/25" strokeWidth="1" />
      <g fill="none" stroke="white" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M15.5 22.5c-2.8 0-5-2.2-5-5s2.2-5 5-5c1.4 0 2.6.6 3.5 1.5" />
        <path d="M24.5 17.5c2.8 0 5 2.2 5 5s-2.2 5-5 5c-1.4 0-2.6-.6-3.5-1.5" />
        <path d="M17.2 20.8l5.6-1.6" />
      </g>
    </svg>
  );
}

function LinkMarkInverse({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden>
      <circle cx="20" cy="20" r="20" className="fill-white" />
      <g fill="none" stroke="#1C1917" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M15.5 22.5c-2.8 0-5-2.2-5-5s2.2-5 5-5c1.4 0 2.6.6 3.5 1.5" />
        <path d="M24.5 17.5c2.8 0 5 2.2 5 5s-2.2 5-5 5c-1.4 0-2.6-.6-3.5-1.5" />
        <path d="M17.2 20.8l5.6-1.6" />
      </g>
    </svg>
  );
}

export function LocalLinkLogo({ className = "", variant = "header", size = "md" }: Props) {
  const s = sizes[size];

  if (variant === "icon") {
    return <LinkMark className={`${s.icon} shrink-0 ${className}`} />;
  }

  if (variant === "footer") {
    return (
      <div className={`flex items-center gap-3 shrink-0 ${className}`}>
        <LinkMarkFooter className={`${s.icon} shrink-0`} />
        <div className="leading-tight">
          <p className={`font-bold text-white ${s.title}`}>Local Link</p>
          <p className={`text-white/60 font-medium ${s.sub}`}>로컬링크</p>
        </div>
      </div>
    );
  }

  if (variant === "inverse") {
    return (
      <div className={`flex items-center gap-2.5 shrink-0 ${className}`}>
        <LinkMarkInverse className={`${s.icon} shrink-0`} />
        <div className="leading-tight">
          <p className={`font-bold text-white tracking-tight ${s.title}`}>Local Link</p>
          <p className={`text-white/75 font-medium ${s.sub}`}>로컬링크</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-2.5 shrink-0 ${className}`}>
      <LinkMark className={`${s.icon} shrink-0`} />
      <div className="leading-tight">
        <p className={`font-bold text-brand-ink tracking-tight ${s.title}`}>Local Link</p>
        <p className={`text-hades-muted font-medium ${s.sub}`}>로컬링크</p>
      </div>
    </div>
  );
}
