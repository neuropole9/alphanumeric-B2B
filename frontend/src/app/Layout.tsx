import {
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import {
  Box,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Gauge,
  Lightbulb,
  LogOut,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  ShoppingCart,
  Truck,
  Users,
  Workflow,
  Scale,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "./AuthContext";
import { api } from "../api/client";
import type { SearchResult, Workspace } from "../types";
import { applicationPath } from "./application";

export default function Layout() {
  const { user, logout } = useAuth();
  const { workspace = "lighting" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const ws = workspace.toUpperCase() as Workspace;
  const isAdmin = user?.role === "ADMIN" || user?.role === "SUPER_ADMIN";
  const isInternal =
    isAdmin ||
    [
      "SALES_MANAGER",
      "SALES_EXECUTIVE",
      "DESIGNER",
      "ENGINEER",
      "ACCOUNTS",
      "WAREHOUSE",
      "DISPATCH",
      "SERVICE",
      "RMA",
    ].includes(user?.role || "");
  const section = (location.pathname.split("/")[3] || "dashboard").replaceAll(
    "-",
    " ",
  );

  useEffect(() => {
    if (user && !user.workspaces.includes(ws)) {
      const first = (user.workspaces[0] || "LIGHTING").toLowerCase();
      navigate(
        `/app/${first}/${user.role === "ADMIN" || user.role === "SUPER_ADMIN" ? "dashboard" : "projects"}`,
        { replace: true },
      );
    }
  }, [navigate, user, ws]);

  useEffect(() => {
    const timer = setTimeout(async () => {
      if (query.trim().length < 2) {
        setResults([]);
        setSearching(false);
        return;
      }
      setSearching(true);
      try {
        setResults(
          await api<SearchResult[]>(
            `/api/v1/search?q=${encodeURIComponent(query)}&workspace=${ws}`,
          ),
        );
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [query, ws]);

  const switchWorkspace = (next: Workspace) => {
    if (!user?.workspaces.includes(next)) return;
    if (next === ws) return;
    if (
      /\/inquiries\/(new|[^/]+\/edit)$/.test(location.pathname) &&
      !window.confirm("Discard unsaved inquiry changes and switch application?")
    )
      return;
    setQuery("");
    setResults([]);
    setSearching(false);
    sessionStorage.removeItem("catalogue-search");
    sessionStorage.removeItem("inquiry-picker-state");
    navigate(applicationPath(next, isInternal));
  };
  const link = (to: string, label: string, Icon: typeof Gauge) => (
    <NavLink
      to={`/app/${workspace}/${to}`}
      className={({ isActive }) => `side-link ${isActive ? "active" : ""}`}
    >
      <span className="side-link-icon">
        <Icon size={19} />
      </span>
      <span>{label}</span>
    </NavLink>
  );
  const openResult = (result: SearchResult) => {
    setQuery("");
    setResults([]);
    const resultWorkspace = (result.workspace || ws).toLowerCase();
    const projectBase =
      result.customer_id && result.project_id
        ? `/app/${resultWorkspace}/customers/${result.customer_id}/projects/${result.project_id}`
        : "";
    const routes: Partial<Record<SearchResult["type"], string>> = {
      product: `/app/${resultWorkspace}/products/${result.id}`,
      product_family: `/app/${resultWorkspace}/products/${result.id}`,
      customer: `/app/${resultWorkspace}/customers/${result.id}`,
      project: projectBase || `/app/${resultWorkspace}/projects/${result.id}`,
      building: `${projectBase}/buildings/${result.id}`,
      room: `${projectBase}/buildings/${result.building_id}/floors/${result.floor_id}/rooms/${result.id}`,
      inquiry: `/app/${resultWorkspace}/inquiries/${result.id}`,
      quotation: `/app/${resultWorkspace}/quotations/${result.id}`,
      order: `/app/${resultWorkspace}/orders/${result.id}`,
      invoice: `/app/${resultWorkspace}/invoices/${result.id}`,
    };
    const target = routes[result.type];
    if (target) navigate(target);
  };
  const WorkspaceIcon = ws === "LIGHTING" ? Lightbulb : Workflow;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div>AlphaNumeric</div>
          <small>SMART SOLUTIONS. BRIGHTER TOMORROW.</small>
        </div>
        <div className="workspace-toggle" aria-label="Workspace">
          <button
            type="button"
            onClick={() => switchWorkspace("LIGHTING")}
            className={ws === "LIGHTING" ? "selected" : ""}
          >
            <Lightbulb size={17} />
            <span>Lighting</span>
          </button>
          <button
            type="button"
            onClick={() => switchWorkspace("AUTOMATION")}
            className={ws === "AUTOMATION" ? "selected" : ""}
          >
            <Workflow size={17} />
            <span>Automation</span>
          </button>
        </div>
        {isAdmin && (
          <button
            className="sidebar-quick"
            type="button"
            onClick={() => navigate(`/app/${workspace}/inquiries/new`)}
          >
            <Plus size={17} />
            <span>Create Inquiry</span>
          </button>
        )}
        <nav aria-label="Primary navigation">
          <span className="sidebar-nav-label">Workspace</span>
          {isInternal ? (
            <>
              {link("dashboard", "Dashboard", Gauge)}
              {isAdmin && link("customers", "Customers", Users)}
              {link("products", "Product Catalogue", Box)}
              {isAdmin && link("catalogue", "Catalogue Management", BookOpen)}
              {link("operations", "Operations Centre", Truck)}
              {isAdmin &&
                link("commercial-control", "Commercial Control", Scale)}
              {isAdmin && link("settings", "Settings", Settings)}
              {isAdmin && link("audit", "Audit Log", ShieldCheck)}
            </>
          ) : (
            <>
              {link("projects", "My Project", Gauge)}
              {link("products", "Product Catalogue", Box)}
              {link("requests/new", "My Requests", ShoppingCart)}
              {link("approvals", "Approvals", CheckCircle2)}
            </>
          )}
        </nav>
        <div className="profile">
          <div className="avatar">{user?.name?.[0] || "U"}</div>
          <div>
            <b>{user?.name}</b>
            <small>{user?.role?.replaceAll("_", " ") || "Project User"}</small>
          </div>
          <button
            type="button"
            aria-label="Sign out"
            title="Sign out"
            onClick={logout}
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div className="topbar-context">
            <span>
              <WorkspaceIcon size={17} />
            </span>
            <div>
              <small>{ws.toLowerCase()} workspace</small>
              <b>{section}</b>
            </div>
          </div>
          <div className="global-search">
            <Search size={18} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search customers, projects, rooms, products or documents…"
              aria-label="Global search"
              aria-expanded={Boolean(query)}
            />
            {query.length > 1 && (
              <div className="search-results" role="listbox">
                {searching ? (
                  <div className="search-state">Searching…</div>
                ) : results.length ? (
                  results.map((result, index) => (
                    <button
                      type="button"
                      role="option"
                      key={`${result.type}-${result.id}-${index}`}
                      onClick={() => openResult(result)}
                    >
                      <span>
                        <b>{result.label}</b>
                        <small>
                          {result.type.replaceAll("_", " ").toUpperCase()} ·{" "}
                          {result.sub || "No additional context"}
                        </small>
                      </span>
                      <ChevronRight size={16} />
                    </button>
                  ))
                ) : (
                  <div className="search-state">
                    No authorized results found.
                  </div>
                )}
              </div>
            )}
          </div>
        </header>
        <div className="content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
