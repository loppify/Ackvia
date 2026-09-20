"use client";

import { useState } from "react";
import { Bell, ChevronDown, LifeBuoy, Search } from "lucide-react";

export function TopBar() {
  const [searchOpen, setSearchOpen] = useState(false);

  return <header className="overview-topbar">
    <button className="search-trigger" type="button" onClick={() => setSearchOpen((open) => !open)} aria-expanded={searchOpen}>
      <Search size={15} /><span>Search...</span><kbd>Ctrl K</kbd>
    </button>
    <div className="topbar-actions"><button className="icon-button" aria-label="Help"><LifeBuoy size={16} /></button><button className="icon-button notification" aria-label="Notifications"><Bell size={16} /><i /></button><span className="top-avatar">RT</span><button className="agency-button" type="button">Acme Agency<ChevronDown size={13} /></button></div>
    {searchOpen && <div className="search-popover" role="status"><Search size={14} /><span>Search clients, sites, leads...</span></div>}
  </header>;
}
