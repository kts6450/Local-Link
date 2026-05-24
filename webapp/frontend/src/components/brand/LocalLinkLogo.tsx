type Props = {
  className?: string;
  /** 헤더(기본) | 푸터(밝은 톤) | 로그인 패널(반전) | 아이콘만 */
  variant?: "header" | "footer" | "inverse" | "icon";
  size?: "sm" | "md" | "lg";
};

const sizes = {
  sm: { icon: "h-9 w-9", title: "text-base", sub: "text-[11px]" },
  md: { icon: "h-10 w-10 sm:h-11 sm:w-11", title: "text-lg sm:text-xl", sub: "text-xs sm:text-sm" },
  lg: { icon: "h-14 w-14", title: "text-2xl", sub: "text-base" },
};

function LinkMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden>
      <circle cx="20" cy="20" r="20" className="fill-brand-ink" />
      <g fill="none" stroke="white" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
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
      <circle cx="20" cy="20" r="20" className="fill-white/15" />
      <circle cx="20" cy="20" r="19" fill="none" stroke="white" strokeOpacity="0.25" />
      <g fill="none" stroke="white" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
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
      <g fill="none" stroke="#1C1917" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
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
          <p className={`font-bold text-white tracking-tight ${s.title}`}>Local Link</p>
          <p className={`text-white/60 font-medium tracking-wide ${s.sub}`}>로컬링크</p>
        </div>
      </div>
    );
  }

  if (variant === "inverse") {
    return (
      <div className={`flex items-center gap-3 shrink-0 ${className}`}>
        <LinkMarkInverse className={`${s.icon} shrink-0`} />
        <div className="leading-tight">
          <p className={`font-bold text-white tracking-tight ${s.title}`}>Local Link</p>
          <p className={`text-white/75 font-medium tracking-wide ${s.sub}`}>로컬링크</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-2.5 sm:gap-3 shrink-0 ${className}`}>
      <LinkMark className={`${s.icon} shrink-0`} />
      <div className="leading-tight">
        <p className={`font-bold text-brand-ink tracking-tight ${s.title}`}>Local Link</p>
        <p className={`text-hades-muted font-medium tracking-wide ${s.sub}`}>로컬링크</p>
      </div>
    </div>
  );
}
