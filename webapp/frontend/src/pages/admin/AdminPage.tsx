import { useEffect, useRef, useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { PageHeader } from "../../components/ui/PageHeader";
import { LocalLinkLogo } from "../../components/brand/LocalLinkLogo";
import { api } from "../../lib/api";
import { useAuthRole } from "../../store/auth";
import { authHeaders } from "../../lib/authFetch";

type Tab = "stats" | "users" | "listings" | "voice-logs" | "ocr-logs";

interface StatRow {
  label: string;
  value: string;
  hint?: string;
}

type VoiceLogItem = Awaited<ReturnType<typeof api.adminListVoiceLogs>>["items"][number];
type OcrLogItem = Awaited<ReturnType<typeof api.adminListOcrLogs>>["items"][number];

/* ──────────────── 인라인 오디오 플레이어 ──────────────── */
function AudioPlayer({ logId, hasAudio }: { logId: string; hasAudio: boolean }) {
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  if (!hasAudio) {
    return <span className="text-xs text-hades-muted italic">파일 없음</span>;
  }

  const toggle = async () => {
    if (!audioRef.current) {
      // Authorization 헤더를 포함한 fetch → blob URL 생성
      try {
        const res = await fetch(api.adminVoiceLogAudioUrl(logId), {
          headers: authHeaders(),
        });
        if (!res.ok) throw new Error();
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const el = new Audio(url);
        audioRef.current = el;
        el.onended = () => setPlaying(false);
        el.play();
        setPlaying(true);
      } catch {
        setError(true);
      }
      return;
    }
    if (playing) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setPlaying(false);
    } else {
      audioRef.current.play();
      setPlaying(true);
    }
  };

  if (error) return <span className="text-xs text-red-500">재생 오류</span>;

  return (
    <button
      id={`play-voice-${logId}`}
      type="button"
      onClick={() => void toggle()}
      className={[
        "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all",
        playing
          ? "bg-shop-teal text-white shadow-md shadow-shop-teal/30"
          : "bg-shop-tealLight text-shop-tealDark hover:bg-shop-teal hover:text-white",
      ].join(" ")}
    >
      <span className="text-sm">{playing ? "⏹" : "▶"}</span>
      {playing ? "정지" : "재생"}
    </button>
  );
}

/* ──────────────── 공통 다운로드 유틸 ──────────────── */

/** 인증 fetch → blob → 파일 저장 */
async function downloadAuthBlob(url: string, filename: string) {
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error(`download failed ${res.status}`);
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(blobUrl);
}

/** UTF-8 BOM CSV 생성 → 파일 저장 (한글 엑셀 깨짐 방지) */
function downloadCsv(headers: string[], rows: string[][], filename: string) {
  const escape = (v: string) => {
    const s = String(v ?? "");
    if (s.includes('"') || s.includes(",") || s.includes("\n")) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };
  const lines = [headers.map(escape).join(",")];
  for (const row of rows) lines.push(row.map(escape).join(","));
  const bom = "\uFEFF";
  const blob = new Blob([bom + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** 공통 파일명 생성 — ZIP·CSV·개별 다운로드 모두 동일 규칙 */
function voiceMappingName(log: VoiceLogItem) {
  const ts = log.created_at.slice(0, 16).replace("T", "_").replace(":", "-");
  const prefix = (log.seller_email ?? log.seller_id ?? "guest").split("@")[0];
  return `voice_${prefix}_${ts}_${log.id}.wav`;
}
function ocrMappingName(log: OcrLogItem, n: number) {
  const ts = log.created_at.slice(0, 16).replace("T", "_").replace(":", "-");
  const prefix = (log.seller_email ?? log.seller_id ?? "guest").split("@")[0];
  return `ocr_${prefix}_${ts}_${log.id}_${n + 1}.jpg`;
}

/* ──────────────── OCR 이미지 모달 ──────────────── */
function OcrImageModal({ logId, imageCount, onClose }: { logId: string; imageCount: number; onClose: () => void }) {
  const [idx, setIdx] = useState(0);
  const [blobUrls, setBlobUrls] = useState<(string | null)[]>(() => Array(imageCount).fill(null));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (blobUrls[idx]) return;

    let active = true;
    const fetchImage = async () => {
      setLoading(true);
      setError(false);
      try {
        const url = api.adminOcrLogImageUrl(logId, idx);
        const res = await fetch(url, {
          headers: authHeaders(),
        });
        if (!res.ok) throw new Error();
        const blob = await res.blob();
        if (!active) return;
        const localUrl = URL.createObjectURL(blob);
        setBlobUrls((prev) => {
          const next = [...prev];
          next[idx] = localUrl;
          return next;
        });
      } catch (err) {
        if (active) {
          setError(true);
        }
      } finally {
        if (active) setLoading(false);
      }
    };

    void fetchImage();

    return () => {
      active = false;
    };
  }, [logId, idx, blobUrls]);

  // Clean up blob URLs when component unmounts
  useEffect(() => {
    return () => {
      blobUrls.forEach((url) => {
        if (url) URL.revokeObjectURL(url);
      });
    };
  }, [blobUrls]);

  const downloadCurrentImage = () => {
    const currentBlobUrl = blobUrls[idx];
    if (!currentBlobUrl || currentBlobUrl === "error") {
      alert("다운로드할 이미지가 없습니다.");
      return;
    }
    const defaultName = `ocr_${logId.slice(0, 8)}_${idx + 1}`;
    const label = prompt("다운로드 파일 라벨을 입력하세요 (미입력 시 기본명 사용):", defaultName);
    if (label === null) return; // 취소
    const safeName = (label.trim() || defaultName).replace(/[\\/*?:"<>|]/g, "");
    const a = document.createElement("a");
    a.href = currentBlobUrl;
    a.download = `${safeName}_ocr_${logId}_${idx + 1}.jpg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div
      id="ocr-image-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative max-w-2xl w-full mx-4 bg-white rounded-2xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-hades-line">
          <span className="font-semibold text-hades-text">
            원본 이미지 {imageCount > 1 ? `(${idx + 1} / ${imageCount})` : ""}
          </span>
          <div className="flex items-center gap-3">
            {blobUrls[idx] && blobUrls[idx] !== "error" && (
              <button
                type="button"
                onClick={downloadCurrentImage}
                className="text-xs font-semibold px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 text-hades-text transition-colors flex items-center gap-1"
              >
                📥 다운로드
              </button>
            )}
            <button
              type="button"
              id="ocr-modal-close"
              onClick={onClose}
              className="text-hades-muted hover:text-hades-text text-xl font-bold leading-none"
            >
              ✕
            </button>
          </div>
        </div>
        <div className="flex items-center justify-center bg-slate-50 p-4 min-h-[300px]">
          {loading && !blobUrls[idx] ? (
            <div className="text-hades-muted text-sm flex flex-col items-center gap-2">
              <span className="animate-spin text-xl">⏳</span>
              <span>이미지를 불러오는 중...</span>
            </div>
          ) : error && !blobUrls[idx] ? (
            <div className="text-red-500 text-sm flex flex-col items-center gap-2">
              <span>⚠️ 이미지를 불러오지 못했습니다.</span>
            </div>
          ) : (
            <img
              src={blobUrls[idx] || ""}
              alt={`OCR 이미지 ${idx + 1}`}
              className="max-h-[60vh] max-w-full object-contain rounded-lg shadow"
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).src =
                  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='150' viewBox='0 0 200 150'%3E%3Crect width='200' height='150' fill='%23f1f5f9'/%3E%3Ctext x='100' y='80' text-anchor='middle' fill='%2394a3b8' font-size='14'%3E이미지 없음%3C/text%3E%3C/svg%3E";
              }}
            />
          )}
        </div>
        {imageCount > 1 && (
          <div className="flex justify-center gap-2 py-3 border-t border-hades-line">
            {Array.from({ length: imageCount }).map((_, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setIdx(i)}
                className={[
                  "w-2.5 h-2.5 rounded-full transition-colors",
                  i === idx ? "bg-shop-teal" : "bg-slate-300 hover:bg-slate-400",
                ].join(" ")}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ──────────────── 페이지네이션 ──────────────── */
function Pagination({
  page, total, limit, onPage,
}: {
  page: number; total: number; limit: number; onPage: (p: number) => void;
}) {
  const last = Math.ceil(total / limit) || 1;
  if (last <= 1) return null;
  return (
    <div className="flex items-center gap-2 justify-center py-4">
      <button
        type="button"
        disabled={page === 1}
        onClick={() => onPage(page - 1)}
        className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-slate-100 text-hades-muted disabled:opacity-40 hover:bg-slate-200 transition-colors"
      >
        ◀ 이전
      </button>
      <span className="text-sm text-hades-muted tabular-nums">
        {page} / {last}
      </span>
      <button
        type="button"
        disabled={page === last}
        onClick={() => onPage(page + 1)}
        className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-slate-100 text-hades-muted disabled:opacity-40 hover:bg-slate-200 transition-colors"
      >
        다음 ▶
      </button>
    </div>
  );
}

/* ──────────────── 메인 페이지 ──────────────── */
export function AdminPage() {
  const role = useAuthRole();
  const [tab, setTab] = useState<Tab>("stats");
  const [stats, setStats] = useState<Awaited<ReturnType<typeof api.adminStats>> | null>(null);
  const [users, setUsers] = useState<Awaited<ReturnType<typeof api.adminListUsers>>>([]);
  const [listings, setListings] = useState<Awaited<ReturnType<typeof api.adminListAllListings>>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 음성 로그
  const [voiceLogs, setVoiceLogs] = useState<VoiceLogItem[]>([]);
  const [voiceTotal, setVoiceTotal] = useState(0);
  const [voicePage, setVoicePage] = useState(1);

  // OCR 로그
  const [ocrLogs, setOcrLogs] = useState<OcrLogItem[]>([]);
  const [ocrTotal, setOcrTotal] = useState(0);
  const [ocrPage, setOcrPage] = useState(1);
  const [ocrModal, setOcrModal] = useState<{ logId: string; count: number } | null>(null);

  const LIMIT = 20;

  useEffect(() => {
    if (role !== "master") return;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        if (tab === "stats" && !stats) setStats(await api.adminStats());
        if (tab === "users") setUsers(await api.adminListUsers());
        if (tab === "listings") setListings(await api.adminListAllListings());
        if (tab === "voice-logs") {
          const res = await api.adminListVoiceLogs(voicePage, LIMIT);
          setVoiceLogs(res.items);
          setVoiceTotal(res.total);
        }
        if (tab === "ocr-logs") {
          const res = await api.adminListOcrLogs(ocrPage, LIMIT);
          setOcrLogs(res.items);
          setOcrTotal(res.total);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "불러오기 실패");
      } finally {
        setLoading(false);
      }
    })();
  }, [tab, role, stats, voicePage, ocrPage]);

  if (role !== "master") return <Navigate to="/" replace />;

  const tabCls = (t: Tab) =>
    [
      "px-4 py-2 rounded-xl text-sm font-semibold transition-colors",
      tab === t
        ? "bg-shop-teal text-white shadow-sm"
        : "text-hades-muted hover:bg-shop-tealLight hover:text-shop-tealDark",
    ].join(" ");

  const removeUser = async (uid: string, email: string) => {
    if (!confirm(`${email} 계정을 삭제할까요?`)) return;
    await api.adminDeleteUser(uid);
    setUsers((prev) => prev.filter((u) => u.id !== uid));
  };

  const removeListing = async (id: string, title: string) => {
    if (!confirm(`«${title}»을(를) 삭제할까요?`)) return;
    await api.adminDeleteListing(id);
    setListings((prev) => prev.filter((l) => l.id !== id));
  };

  const removeVoiceLog = async (id: string) => {
    if (!confirm("이 음성 로그를 삭제할까요?")) return;
    await api.adminDeleteVoiceLog(id);
    setVoiceLogs((prev) => prev.filter((l) => l.id !== id));
    setVoiceTotal((t) => t - 1);
  };

  const removeOcrLog = async (id: string) => {
    if (!confirm("이 OCR 로그를 삭제할까요?")) return;
    await api.adminDeleteOcrLog(id);
    setOcrLogs((prev) => prev.filter((l) => l.id !== id));
    setOcrTotal((t) => t - 1);
  };

  const statRows: StatRow[] = stats
    ? [
        { label: "회원", value: `${stats.users.toLocaleString()}명`, hint: `구매자 ${stats.consumers} · 공급자 ${stats.sellers}` },
        { label: "등록 상품", value: `${stats.listings.toLocaleString()}건` },
        { label: "주문", value: `${stats.orders.toLocaleString()}건`, hint: `결제 완료 ${stats.paid_orders}` },
        { label: "누적 매출", value: `${stats.revenue.toLocaleString()}원`, hint: "결제 완료 주문 합계" },
        { label: "리뷰", value: `${stats.reviews.toLocaleString()}개` },
      ]
    : [];

  return (
    <div className="min-h-screen bg-brand-cream">
      <header className="bg-white border-b border-hades-line">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/" className="no-underline text-inherit">
              <LocalLinkLogo size="sm" />
            </Link>
            <span className="text-xs font-bold text-white bg-rose-600 px-2.5 py-1 rounded-full">
              운영자
            </span>
          </div>
          <div className="flex gap-3 text-sm">
            <Link to="/" className="text-hades-muted hover:text-hades-text">
              쇼핑몰
            </Link>
            <Link to="/seller/products" className="text-hades-muted hover:text-hades-text">
              셀러오피스
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        <PageHeader badge="운영" title="어드민">
          전체 회원·상품·주문을 관리합니다.
        </PageHeader>

        <nav className="flex gap-2 flex-wrap">
          <button type="button" id="tab-stats" className={tabCls("stats")} onClick={() => setTab("stats")}>
            통계
          </button>
          <button type="button" id="tab-users" className={tabCls("users")} onClick={() => setTab("users")}>
            회원
          </button>
          <button type="button" id="tab-listings" className={tabCls("listings")} onClick={() => setTab("listings")}>
            상품
          </button>
          <button type="button" id="tab-voice-logs" className={tabCls("voice-logs")} onClick={() => setTab("voice-logs")}>
            🎙 음성 로그
          </button>
          <button type="button" id="tab-ocr-logs" className={tabCls("ocr-logs")} onClick={() => setTab("ocr-logs")}>
            📸 OCR 로그
          </button>
        </nav>

        {error ? (
          <p className="rounded-xl bg-red-50 border border-red-100 text-red-800 px-4 py-3">{error}</p>
        ) : null}

        {/* ── 통계 ── */}
        {tab === "stats" && (
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {loading && !stats ? (
              <p className="text-hades-muted">불러오는 중…</p>
            ) : (
              statRows.map((r) => (
                <div key={r.label} className="card p-5">
                  <p className="text-sm text-hades-muted">{r.label}</p>
                  <p className="mt-2 text-3xl font-bold text-hades-text tabular-nums">{r.value}</p>
                  {r.hint ? <p className="mt-1 text-xs text-hades-muted">{r.hint}</p> : null}
                </div>
              ))
            )}
          </section>
        )}

        {/* ── 회원 ── */}
        {tab === "users" && (
          <section className="card overflow-hidden p-0">
            {loading && users.length === 0 ? (
              <p className="p-6 text-hades-muted">불러오는 중…</p>
            ) : users.length === 0 ? (
              <p className="p-6 text-hades-muted">가입된 회원이 없습니다.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-hades-muted">
                    <tr>
                      <th className="px-4 py-3">이메일</th>
                      <th className="px-4 py-3">이름</th>
                      <th className="px-4 py-3">역할</th>
                      <th className="px-4 py-3">업종</th>
                      <th className="px-4 py-3">가입일</th>
                      <th className="px-4 py-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id} className="border-t border-hades-line">
                        <td className="px-4 py-3 font-mono text-xs">{u.email}</td>
                        <td className="px-4 py-3">{u.display_name}</td>
                        <td className="px-4 py-3">
                          <span
                            className={
                              u.role === "seller"
                                ? "rounded-full bg-shop-tealLight px-2 py-0.5 text-xs font-semibold text-shop-tealDark"
                                : "rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700"
                            }
                          >
                            {u.role === "seller" ? "공급자" : "구매자"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-hades-muted">{u.seller_sector ?? "—"}</td>
                        <td className="px-4 py-3 text-xs text-hades-muted">
                          {u.created_at.slice(0, 10)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            type="button"
                            className="text-sm text-red-600 font-semibold hover:underline"
                            onClick={() => void removeUser(u.id, u.email)}
                          >
                            삭제
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {/* ── 상품 ── */}
        {tab === "listings" && (
          <section className="card overflow-hidden p-0">
            {loading && listings.length === 0 ? (
              <p className="p-6 text-hades-muted">불러오는 중…</p>
            ) : listings.length === 0 ? (
              <p className="p-6 text-hades-muted">등록된 상품이 없습니다.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-hades-muted">
                    <tr>
                      <th className="px-4 py-3">상품</th>
                      <th className="px-4 py-3">분류</th>
                      <th className="px-4 py-3">가격</th>
                      <th className="px-4 py-3">공급자</th>
                      <th className="px-4 py-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {listings.map((l) => (
                      <tr key={l.id} className="border-t border-hades-line">
                        <td className="px-4 py-3">
                          <Link to={`/listing/${l.id}`} className="font-semibold hover:underline">
                            {l.title}
                          </Link>
                          <p className="text-xs text-hades-muted">{l.location}</p>
                        </td>
                        <td className="px-4 py-3 text-xs text-hades-muted">
                          {l.kind} · {l.category}
                        </td>
                        <td className="px-4 py-3 tabular-nums">{l.price.toLocaleString()}원</td>
                        <td className="px-4 py-3 text-xs text-hades-muted">
                          {l.seller_email ?? l.seller_id}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            type="button"
                            className="text-sm text-red-600 font-semibold hover:underline"
                            onClick={() => void removeListing(l.id, l.title)}
                          >
                            삭제
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {/* ── 음성 로그 ── */}
        {tab === "voice-logs" && (
          <section className="space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <p className="text-sm text-hades-muted">
                총 <span className="font-semibold text-hades-text tabular-nums">{voiceTotal.toLocaleString()}</span>건의 음성 로그
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={() => {
                    if (voiceTotal === 0) { alert("내보낼 음성 로그가 없습니다."); return; }
                    void downloadAuthBlob(api.adminVoiceLogsCsvUrl(), "voice_logs_all.csv").catch(() => alert("CSV 다운로드 실패"));
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-100 text-emerald-700 hover:bg-emerald-200 transition-colors"
                >
                  📊 학습용 엑셀(CSV) 추출
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void downloadAuthBlob(api.adminVoiceLogsZipUrl(), "voice_logs_all.zip").catch(() => alert("ZIP 다운로드 실패"));
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-100 text-blue-700 hover:bg-blue-200 transition-colors"
                >
                  📦 모든 음성 파일 다운로드 (ZIP)
                </button>
              </div>
            </div>

            {loading && voiceLogs.length === 0 ? (
              <p className="text-hades-muted text-sm">불러오는 중…</p>
            ) : voiceLogs.length === 0 ? (
              <div className="card p-10 text-center">
                <p className="text-3xl mb-3">🎙</p>
                <p className="text-hades-muted">아직 음성 로그가 없습니다.</p>
                <p className="text-xs text-hades-muted mt-1">판매자가 음성 입력을 사용하면 여기에 기록됩니다.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {voiceLogs.map((log) => (
                  <div key={log.id} className="card p-5 space-y-3">
                    {/* 헤더 */}
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                      <div className="flex items-center gap-3 flex-wrap">
                        <span
                          className={[
                            "text-xs font-bold px-2.5 py-1 rounded-full",
                            log.source === "asr"
                              ? "bg-blue-100 text-blue-700"
                              : "bg-purple-100 text-purple-700",
                          ].join(" ")}
                        >
                          {log.source === "asr" ? "ASR (단일)" : "TURN (대화형)"}
                        </span>
                        <span className="text-xs text-hades-muted">
                          {log.seller_email ?? log.seller_id ?? "비로그인"}
                        </span>
                        <span className="text-xs text-hades-muted tabular-nums">
                          {log.created_at.slice(0, 16).replace("T", " ")}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <AudioPlayer logId={log.id} hasAudio={log.has_audio} />
                        {log.has_audio && (
                          <button
                            type="button"
                            onClick={() => {
                              const defaultName = voiceMappingName(log).replace(".wav", "");
                              const label = prompt("다운로드 파일 라벨을 입력하세요 (미입력 시 기본명 사용):", defaultName);
                              if (label === null) return;
                              const safeName = (label.trim() || defaultName).replace(/[\\/*?:"<>|]/g, "");
                              const filename = `${safeName}.wav`;
                              void downloadAuthBlob(api.adminVoiceLogAudioUrl(log.id), filename).catch(() => alert("다운로드 실패"));
                            }}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 text-hades-text hover:bg-slate-200 transition-colors"
                          >
                            📥 다운로드
                          </button>
                        )}
                        <button
                          id={`del-voice-${log.id}`}
                          type="button"
                          onClick={() => void removeVoiceLog(log.id)}
                          className="text-xs text-red-500 font-semibold hover:text-red-700 transition-colors px-2 py-1 rounded hover:bg-red-50"
                        >
                          삭제
                        </button>
                      </div>
                    </div>

                    {/* 텍스트 비교 */}
                    <div className="grid sm:grid-cols-2 gap-3">
                      <div className="rounded-xl bg-slate-50 border border-hades-line p-3">
                        <p className="text-xs font-semibold text-hades-muted mb-1.5">🔈 ASR 원문</p>
                        <p className="text-sm text-hades-text leading-relaxed">
                          {log.raw_text || <span className="italic text-hades-muted">없음</span>}
                        </p>
                      </div>
                      <div className="rounded-xl bg-shop-tealLight border border-shop-teal/20 p-3">
                        <p className="text-xs font-semibold text-shop-tealDark mb-1.5">✅ 보정 텍스트</p>
                        <p className="text-sm text-hades-text leading-relaxed">
                          {log.corrected_text || <span className="italic text-hades-muted">없음</span>}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <Pagination
              page={voicePage}
              total={voiceTotal}
              limit={LIMIT}
              onPage={(p) => {
                setVoicePage(p);
                setVoiceLogs([]);
              }}
            />
          </section>
        )}

        {/* ── OCR 로그 ── */}
        {tab === "ocr-logs" && (
          <section className="space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <p className="text-sm text-hades-muted">
                총 <span className="font-semibold text-hades-text tabular-nums">{ocrTotal.toLocaleString()}</span>건의 OCR 로그
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={() => {
                    if (ocrTotal === 0) { alert("내보낼 OCR 로그가 없습니다."); return; }
                    void downloadAuthBlob(api.adminOcrLogsCsvUrl(), "ocr_logs_all.csv").catch(() => alert("CSV 다운로드 실패"));
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-100 text-emerald-700 hover:bg-emerald-200 transition-colors"
                >
                  📊 학습용 엑셀(CSV) 추출
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void downloadAuthBlob(api.adminOcrLogsZipUrl(), "ocr_logs_all.zip").catch(() => alert("ZIP 다운로드 실패"));
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-100 text-blue-700 hover:bg-blue-200 transition-colors"
                >
                  📦 모든 OCR 이미지 다운로드 (ZIP)
                </button>
              </div>
            </div>

            {loading && ocrLogs.length === 0 ? (
              <p className="text-hades-muted text-sm">불러오는 중…</p>
            ) : ocrLogs.length === 0 ? (
              <div className="card p-10 text-center">
                <p className="text-3xl mb-3">📸</p>
                <p className="text-hades-muted">아직 OCR 로그가 없습니다.</p>
                <p className="text-xs text-hades-muted mt-1">판매자가 수기 메모 사진을 올리면 여기에 기록됩니다.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {ocrLogs.map((log) => (
                  <div key={log.id} className="card p-5 space-y-3">
                    {/* 헤더 */}
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                      <div className="flex items-center gap-3 flex-wrap">
                        {log.listing_tab && (
                          <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-amber-100 text-amber-700">
                            {log.listing_tab === "product" ? "상품" : log.listing_tab === "lodging" ? "숙박" : "체험"}
                          </span>
                        )}
                        {log.confidence != null && (
                          <span
                            className={[
                              "text-xs font-semibold px-2.5 py-1 rounded-full",
                              log.confidence >= 0.9
                                ? "bg-green-100 text-green-700"
                                : log.confidence >= 0.7
                                ? "bg-yellow-100 text-yellow-700"
                                : "bg-red-100 text-red-700",
                            ].join(" ")}
                          >
                            신뢰도 {(log.confidence * 100).toFixed(0)}%
                          </span>
                        )}
                        <span className="text-xs text-hades-muted">
                          {log.seller_email ?? log.seller_id ?? "미상"}
                        </span>
                        <span className="text-xs text-hades-muted tabular-nums">
                          {log.created_at.slice(0, 16).replace("T", " ")}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {log.has_images && (
                          <button
                            id={`view-ocr-img-${log.id}`}
                            type="button"
                            onClick={() => setOcrModal({ logId: log.id, count: log.image_count })}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-100 text-amber-700 hover:bg-amber-200 transition-colors"
                          >
                            🖼 이미지 보기
                            {log.image_count > 1 && (
                              <span className="bg-amber-700 text-white rounded-full w-4 h-4 text-[10px] flex items-center justify-center">
                                {log.image_count}
                              </span>
                            )}
                          </button>
                        )}
                        <button
                          id={`del-ocr-${log.id}`}
                          type="button"
                          onClick={() => void removeOcrLog(log.id)}
                          className="text-xs text-red-500 font-semibold hover:text-red-700 transition-colors px-2 py-1 rounded hover:bg-red-50"
                        >
                          삭제
                        </button>
                      </div>
                    </div>

                    {/* OCR 텍스트 + 해석 결과 */}
                    <div className="grid sm:grid-cols-2 gap-3">
                      <div className="rounded-xl bg-slate-50 border border-hades-line p-3">
                        <p className="text-xs font-semibold text-hades-muted mb-1.5">📝 OCR 추출 텍스트</p>
                        <p className="text-sm text-hades-text leading-relaxed whitespace-pre-line overflow-y-auto max-h-48 pr-1">
                          {log.ocr_raw_text || <span className="italic text-hades-muted">없음</span>}
                        </p>
                      </div>
                      <div className="rounded-xl bg-amber-50 border border-amber-100 p-3">
                        <p className="text-xs font-semibold text-amber-700 mb-2">🏷 해석된 상품 정보</p>
                        <dl className="space-y-1">
                          {Object.entries(log.fields_summary).map(([k, v]) => (
                            <div key={k} className="flex gap-2 text-sm">
                              <dt className="text-hades-muted w-14 shrink-0">
                                {k === "title" ? "상품명" : k === "price" ? "가격" : k === "location" ? "지역" : k === "quantity" ? "수량" : k}
                              </dt>
                              <dd className="text-hades-text font-medium truncate">
                                {v != null ? String(v) : "—"}
                                {k === "price" && v != null ? "원" : ""}
                              </dd>
                            </div>
                          ))}
                          {Object.keys(log.fields_summary).length === 0 && (
                            <dd className="text-hades-muted italic text-xs">정보 없음</dd>
                          )}
                        </dl>
                        {log.warnings.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-amber-100">
                            {log.warnings.slice(0, 2).map((w, i) => (
                              <p key={i} className="text-xs text-amber-700">⚠ {w}</p>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <Pagination
              page={ocrPage}
              total={ocrTotal}
              limit={LIMIT}
              onPage={(p) => {
                setOcrPage(p);
                setOcrLogs([]);
              }}
            />
          </section>
        )}
      </main>

      {/* OCR 이미지 모달 */}
      {ocrModal && (
        <OcrImageModal
          logId={ocrModal.logId}
          imageCount={ocrModal.count}
          onClose={() => setOcrModal(null)}
        />
      )}
    </div>
  );
}
