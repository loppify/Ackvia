import { Mark } from "./primitives";

export function DeskLoading() {
  return <div className="desk" role="status" aria-label="Loading investigation desk"><header className="command-bar"><span className="brand"><Mark />ackvia.</span><span className="shell-divider" /><span className="desk-name">Loading evidence…</span></header><div className="context-bar"><span className="skeleton" style={{ width: 180, height: 24 }} /></div><div className="desk-workspace"><aside className="stream" aria-hidden="true">{Array.from({ length: 6 }, (_, index) => <div className="skeleton-row" key={index}><span className="skeleton" /><span className="skeleton" /></div>)}</aside><div className="loading-investigation" aria-hidden="true"><span className="skeleton" /><span className="skeleton" /><div className="loading-columns"><span className="skeleton" /><span className="skeleton" /></div></div></div></div>;
}
