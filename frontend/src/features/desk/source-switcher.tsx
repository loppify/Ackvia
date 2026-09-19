"use client";

import { useState } from "react";
import { ArrowLeft, ArrowRight, Check, RadioTower, Search } from "lucide-react";
import type { Form } from "@/lib/types";
import { PAGE_SIZE, type Resource } from "./model";
import { Dialog, Empty, Fault } from "./primitives";

type SourceSwitcherProps = {
  forms: Resource<Form[]>;
  current: string;
  offset: number;
  more: boolean;
  pending: boolean;
  onSelect: (form: string) => void;
  onPage: (offset: number) => void;
  onClose: () => void;
  refresh: () => void;
};

export function SourceSwitcher({
  forms, current, offset, more, pending, onSelect, onPage, onClose, refresh,
}: SourceSwitcherProps) {
  const [query, setQuery] = useState("");
  const visible = forms.data?.filter((form) =>
    `${form.title} ${form.id}`.toLowerCase().includes(query.toLowerCase()),
  ) ?? [];

  return (
    <Dialog title="Switch form" onClose={onClose} className="source-dialog">
      <div className="source-search">
        <Search size={17} aria-hidden="true" />
        <input
          aria-label="Find a form on this page"
          placeholder="Find a form on this page…"
          data-dialog-focus
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>
      <div className="source-list" aria-busy={pending}>
        {forms.error ? (
          <Fault error={forms.error} onRetry={refresh} />
        ) : !visible.length ? (
          <Empty icon={<RadioTower size={22} />} title={query ? "No matching forms" : "No forms here"}>
            {query ? "Try another title or form ID on this page." : "Forms appear here once they are created in Ackvia."}
          </Empty>
        ) : visible.map((form) => (
          <button className="source-option" type="button" key={form.id} onClick={() => onSelect(form.id)}>
            <span className="source-icon"><RadioTower size={16} aria-hidden="true" /></span>
            <span className="source-option-name">
              <strong>{form.title || "Untitled form"}</strong>
              <span>{form.id}</span>
            </span>
            {form.id === current && <Check size={16} aria-label="Selected form" />}
          </button>
        ))}
      </div>
      <div className="source-pagination">
        <span>{pending ? "Loading forms…" : `${offset + (forms.data?.length ? 1 : 0)}–${offset + (forms.data?.length ?? 0)} forms shown`}</span>
        <div className="button-group">
          <button
            type="button"
            className="icon-button"
            aria-label="Previous forms"
            disabled={!offset || pending}
            onClick={() => { setQuery(""); onPage(Math.max(0, offset - PAGE_SIZE)); }}
          ><ArrowLeft size={15} /></button>
          <button
            type="button"
            className="icon-button"
            aria-label="Next forms"
            disabled={!more || pending}
            onClick={() => { setQuery(""); onPage(offset + PAGE_SIZE); }}
          ><ArrowRight size={15} /></button>
        </div>
      </div>
    </Dialog>
  );
}
