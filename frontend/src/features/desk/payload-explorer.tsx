"use client";

import { useState } from "react";
import { Braces, ChevronRight, ChevronsDownUp, ChevronsUpDown, Search } from "lucide-react";
import { CopyButton } from "./primitives";

function matches(value: unknown, key: string, query: string): boolean {
  return !query || key.toLowerCase().includes(query) || (JSON.stringify(value) ?? "").toLowerCase().includes(query);
}

function Value({ value }: { value: unknown }) {
  const type = value === null ? "null" : typeof value;
  return <span className={`json-value json-${type}`}>{typeof value === "string" ? value === "" ? '""' : value : JSON.stringify(value)}</span>;
}

function TreeNode({ name, value, depth, query, expand }: { name: string; value: unknown; depth: number; query: string; expand: boolean | null }) {
  const [open, setOpen] = useState(expand ?? depth < 1);
  const [limit, setLimit] = useState(100);
  if (!matches(value, name, query)) return null;
  if (value === null || typeof value !== "object") {
    return <li className="json-leaf"><span className="json-key">{name}</span><Value value={value} /></li>;
  }
  const entries = Object.entries(value);
  const isArray = Array.isArray(value);
  const expanded = !!query || open;
  const childQuery = name.toLowerCase().includes(query) ? "" : query;
  const visible = entries.filter(([key, child]) => matches(child, key, childQuery));
  return <li className="json-branch"><button type="button" className="json-toggle" onClick={() => setOpen(!expanded)} aria-expanded={expanded} disabled={!!query}>
    <ChevronRight size={13} className={expanded ? "rotated" : ""} aria-hidden="true" /><span className="json-key">{name}</span><span className="json-shape">{isArray ? "[" : "{"} {entries.length} {isArray ? "items" : "keys"} {isArray ? "]" : "}"}</span>
  </button>{expanded && <ul className="json-children">{visible.slice(0, limit).map(([key, child]) => <TreeNode key={key} name={isArray ? `[${key}]` : key} value={child} depth={depth + 1} query={childQuery} expand={expand} />)}{visible.length > limit && <li><button className="button button-quiet" onClick={() => setLimit(limit + 100)}>Show next {Math.min(100, visible.length - limit)} values</button></li>}{entries.length === 0 && <li className="json-empty">{isArray ? "Empty array" : "Empty object"}</li>}</ul>}</li>;
}

export function PayloadExplorer({ payload }: { payload: unknown }) {
  const [mode, setMode] = useState<"tree" | "raw">("tree");
  const [query, setQuery] = useState("");
  const [expansion, setExpansion] = useState<{ all: boolean | null; version: number }>({ all: null, version: 0 });
  const raw = JSON.stringify(payload, null, 2) ?? "null";
  const entries = payload !== null && typeof payload === "object" ? Object.entries(payload) : null;
  const search = query.trim().toLowerCase();
  const match = matches(payload, "", search);
  return <section className="payload-panel" aria-labelledby="payload-title" id="payload-panel">
    <div className="pane-title"><span className="section-label"><Braces size={15} aria-hidden="true" /><h2 id="payload-title">Captured payload</h2></span><span className="muted mono">{entries ? `${entries.length} fields` : typeof payload}</span></div>
    <div className="payload-toolbar"><div className="segmented" aria-label="Payload view"><button type="button" aria-pressed={mode === "tree"} onClick={() => setMode("tree")}>Tree</button><button type="button" aria-pressed={mode === "raw"} onClick={() => setMode("raw")}>Raw JSON</button></div><div className="button-group">{mode === "tree" && <button className="icon-button" title={expansion.all ? "Collapse all" : "Expand all"} aria-label={expansion.all ? "Collapse all" : "Expand all"} onClick={() => setExpansion({ all: !expansion.all, version: expansion.version + 1 })}>{expansion.all ? <ChevronsDownUp size={15} /> : <ChevronsUpDown size={15} />}</button>}<CopyButton value={raw} label="Copy payload" compact /></div></div>
    <label className="search-field payload-search"><Search size={13} aria-hidden="true" /><input aria-label="Find in payload" placeholder="Find a key or value…" value={query} onChange={(event) => setQuery(event.target.value)} /><kbd>/</kbd></label>
    <div className="payload-content" tabIndex={0} aria-label="Payload contents">
      {!match ? <p className="inline-empty" role="status">No matching keys or values.</p> : mode === "raw" ? <div className="raw-json">{raw.split("\n").map((line, index) => <div className={search && line.toLowerCase().includes(search) ? "raw-line matched" : "raw-line"} key={index}><span className="line-number" aria-hidden="true">{index + 1}</span><code>{line}</code></div>)}</div> : entries ? <ul className="json-tree" key={expansion.version}>{entries.map(([key, value]) => <TreeNode key={key} name={key} value={value} depth={0} query={search} expand={expansion.all} />)}{!entries.length && <li className="json-empty">{"{}"} <span>No captured fields</span></li>}</ul> : <div className="json-scalar"><Value value={payload} /></div>}
    </div>
    <div className="payload-foot"><span className="small-dot" />Original captured data<span className="muted">Read only</span></div>
  </section>;
}
