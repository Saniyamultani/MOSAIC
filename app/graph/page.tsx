"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  MarkerType,
  Node,
  NodeMouseHandler,
  ReactFlowProvider,
} from "reactflow";
import GraphNodeCard from "@/components/GraphNodeCard";
import { api, formatFieldLabel, formatValue, GraphEdge, GraphNode } from "@/lib/api";

// Alert nodes are excluded from the Life Graph — they live on the Radar page.
const EXCLUDED_TYPES = new Set(["alert"]);

const HUB_TYPES = ["product", "asset", "subscription", "bill", "expense"];
const nodeTypes = { mosaic: GraphNodeCard };

export type CategoryKey =
  | "all"
  | "electronics"
  | "clothing"
  | "home"
  | "subscriptions"
  | "documents"
  | "warranties"
  | "expenses"
  | "other";

const CATEGORIES: { key: CategoryKey; label: string; icon: string }[] = [
  { key: "all", label: "All Ecosystem", icon: "🌐" },
  { key: "electronics", label: "Electronics", icon: "📱" },
  { key: "clothing", label: "Clothing", icon: "👕" },
  { key: "home", label: "Home & Utilities", icon: "🏠" },
  { key: "subscriptions", label: "Subscriptions", icon: "🔄" },
  { key: "documents", label: "Documents", icon: "📄" },
  { key: "warranties", label: "Warranties", icon: "🛡️" },
  { key: "expenses", label: "Expenses & Bills", icon: "💳" },
  { key: "other", label: "Other", icon: "📦" },
];

/** Classify a node into one of the 8 categories based on type, name, and attributes. */
function getNodeCategory(node: GraphNode): CategoryKey {
  const type = (node.type || "").toLowerCase();
  const name = (node.name || "").toLowerCase();
  const catAttr = String(node.attributes?.category || "").toLowerCase();

  if (type === "warranty") return "warranties";
  if (type === "subscription") return "subscriptions";
  if (type === "document") return "documents";
  if (type === "bill" || type === "expense") return "expenses";
  if (catAttr === "clothing" || name.includes("shirt") || name.includes("shoes") || name.includes("jacket")) {
    return "clothing";
  }
  if (
    catAttr === "electronics" ||
    type === "product" ||
    name.includes("phone") ||
    name.includes("galaxy") ||
    name.includes("s26") ||
    name.includes("tv") ||
    name.includes("oled") ||
    name.includes("bravia") ||
    name.includes("macbook") ||
    name.includes("laptop") ||
    name.includes("sm-")
  ) {
    return "electronics";
  }
  if (
    catAttr === "home" ||
    name.includes("broadband") ||
    name.includes("airtel") ||
    name.includes("router") ||
    name.includes("wifi") ||
    name.includes("furniture")
  ) {
    return "home";
  }
  return "other";
}

function formatRelationshipLabel(rel: string): string {
  const norm = rel.toUpperCase().replace(/_/g, " ");
  switch (norm) {
    case "PURCHASED FROM": return "purchased from";
    case "PAID WITH":
    case "PAID VIA": return "paid via";
    case "COVERED BY": return "covered by";
    case "PROVIDED BY":
    case "SUPPORTED BY": return "supported by";
    case "AFFECTED BY": return "affected by";
    case "DOCUMENTED BY":
    case "DOCUMENTED IN": return "documented in";
    case "ISSUED BY": return "issued by";
    case "MANUFACTURED BY": return "manufactured by";
    case "RELATES TO": return "relates to";
    default: return rel.replace(/_/g, " ").toLowerCase();
  }
}

const NODE_W = 210;
const NODE_H = 90;
const HUB_GAP_X = 590;
const HUB_GAP_Y = 470;

function layout(nodes: GraphNode[], edges: GraphEdge[]) {
  if (!nodes.length) return {};

  const hubs = nodes.filter((node) => HUB_TYPES.includes(node.type));
  const satellites = nodes.filter((node) => !HUB_TYPES.includes(node.type));
  const positions: Record<string, { x: number; y: number }> = {};
  const hubCols = Math.max(1, Math.ceil(Math.sqrt(hubs.length)));

  hubs.forEach((hub, index) => {
    positions[hub.id] = {
      x: (index % hubCols) * HUB_GAP_X,
      y: Math.floor(index / hubCols) * HUB_GAP_Y,
    };
  });

  const neighboursOf = (id: string) =>
    edges
      .filter((edge) => edge.source === id || edge.target === id)
      .map((edge) => (edge.source === id ? edge.target : edge.source));
  const satellitesByAnchor = new Map<string, GraphNode[]>();

  satellites.forEach((satellite) => {
    const linkedHubs = neighboursOf(satellite.id).filter((id) => positions[id]);
    const anchorIds = linkedHubs.length
      ? linkedHubs
      : hubs.length
        ? [hubs[0].id]
        : [];
    const anchorKey = anchorIds.slice().sort().join("|") || "unlinked";
    satellitesByAnchor.set(anchorKey, [...(satellitesByAnchor.get(anchorKey) || []), satellite]);
  });

  const placedPerAnchor = new Map<string, number>();
  satellitesByAnchor.forEach((group, anchorKey) => {
    const anchorIds = anchorKey === "unlinked" ? [] : anchorKey.split("|");
    const anchors = anchorIds.map((id) => positions[id]).filter(Boolean);
    const center = anchors.length
      ? {
          x: anchors.reduce((sum, point) => sum + point.x, 0) / anchors.length,
          y: anchors.reduce((sum, point) => sum + point.y, 0) / anchors.length,
        }
      : { x: 0, y: 0 };
    const alreadyPlaced = placedPerAnchor.get(anchorKey) || 0;
    const totalSlots = group.length + alreadyPlaced;
    const radius = anchorIds.length > 1 ? 365 : 285;

    group.forEach((satellite, index) => {
      const slot = index + alreadyPlaced;
      const angle = ((slot * 360) / Math.max(totalSlots, 8) - 90) * (Math.PI / 180);
      positions[satellite.id] = {
        x: center.x + Math.cos(angle) * radius,
        y: center.y + Math.sin(angle) * radius,
      };
    });
    placedPerAnchor.set(anchorKey, totalSlots);
  });

  const ids = nodes.map((node) => node.id);
  const minDX = NODE_W + 65;
  const minDY = NODE_H + 44;
  for (let pass = 0; pass < 100; pass += 1) {
    let moved = false;
    for (let i = 0; i < ids.length; i += 1) {
      for (let j = i + 1; j < ids.length; j += 1) {
        const first = positions[ids[i]];
        const second = positions[ids[j]];
        if (!first || !second) continue;
        const dx = second.x - first.x;
        const dy = second.y - first.y;
        const overlapX = minDX - Math.abs(dx);
        const overlapY = minDY - Math.abs(dy);
        if (overlapX <= 0 || overlapY <= 0) continue;
        moved = true;
        if (overlapX < overlapY) {
          const push = overlapX / 2 + 3;
          first.x -= push * (dx >= 0 ? 1 : -1);
          second.x += push * (dx >= 0 ? 1 : -1);
        } else {
          const push = overlapY / 2 + 3;
          first.y -= push * (dy >= 0 ? 1 : -1);
          second.y += push * (dy >= 0 ? 1 : -1);
        }
      }
    }
    if (!moved) break;
  }

  return positions;
}

function subtitle(node: GraphNode): string | undefined {
  const a = node.attributes || {};
  if (a.expiry_date) return `expires ${a.expiry_date}`;
  if (a.renewal_date) return `renews ${a.renewal_date}`;
  if (a.due_date) return `due ${a.due_date}`;
  if (a.purchase_date) return `bought ${a.purchase_date}`;
  if (a.price) return `₹${Number(a.price).toLocaleString("en-IN")}`;
  if (a.amount) return `₹${Number(a.amount).toLocaleString("en-IN")}`;
  if (a.model_code) return a.model_code;
  return undefined;
}

export default function GraphPage() {
  const [data, setData] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] } | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<any>(null);

  // Filters & Controls
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<CategoryKey>("all");
  const [warrantyFilter, setWarrantyFilter] = useState<"all" | "active" | "expired">("all");
  const [onlySubscriptions, setOnlySubscriptions] = useState(false);
  const [focusMode, setFocusMode] = useState(false);
  const [showGraphMenu, setShowGraphMenu] = useState(false);

  useEffect(() => {
    api.graph().then((d) => {
      // Filter out alert nodes — they belong on the Radar page, not the Life Graph
      const filtered = {
        ...d,
        nodes: d.nodes.filter((n) => !EXCLUDED_TYPES.has(n.type)),
      };
      // Also prune edges that referenced excluded nodes
      const validIds = new Set(filtered.nodes.map((n) => n.id));
      filtered.edges = d.edges.filter(
        (e) => validIds.has(e.source) && validIds.has(e.target)
      );
      setData(filtered);
    }).catch(() => setData({ nodes: [], edges: [] }));
  }, []);

  useEffect(() => {
    if (!selectedId) { setDetail(null); return; }
    if (selectedId.startsWith("doc_")) {
      setDetail({
        entity: { id: selectedId, name: "Document Record", type: "document", attributes: {} },
        connections: [], documents: [], alerts: [],
        counts: { connections: 0, documents: 0, alerts: 0 },
      });
      return;
    }
    api.entity(selectedId).then(setDetail).catch(() => setDetail(null));
  }, [selectedId]);

  // Direct connected neighbor set for selected node
  const connectedNodeIds = useMemo(() => {
    if (!selectedId || !data) return new Set<string>();
    const set = new Set<string>([selectedId]);
    data.edges.forEach((e) => {
      if (e.source === selectedId) set.add(e.target);
      if (e.target === selectedId) set.add(e.source);
    });
    return set;
  }, [selectedId, data]);

  // Check if a node matches current filter criteria
  const nodeMatchesFilter = useCallback(
    (n: GraphNode) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchTitle = n.name.toLowerCase().includes(q);
        const matchType = n.type.toLowerCase().includes(q);
        const matchAttr = JSON.stringify(n.attributes || {}).toLowerCase().includes(q);
        if (!matchTitle && !matchType && !matchAttr) return false;
      }
      if (selectedCategory !== "all" && getNodeCategory(n) !== selectedCategory) return false;
      if (warrantyFilter !== "all" && n.type === "warranty") {
        const expiry = n.attributes?.expiry_date;
        if (expiry) {
          const isExpired = new Date(expiry) < new Date();
          if (warrantyFilter === "active" && isExpired) return false;
          if (warrantyFilter === "expired" && !isExpired) return false;
        }
      }
      if (onlySubscriptions && n.type !== "subscription") return false;
      return true;
    },
    [searchQuery, selectedCategory, warrantyFilter, onlySubscriptions]
  );
  const hasGraphFilter =
    selectedCategory !== "all" ||
    warrantyFilter !== "all" ||
    onlySubscriptions ||
    Boolean(searchQuery.trim());

  // Overview Metrics calculation (no alerts counted here)
  const metrics = useMemo(() => {
    if (!data) return { totalValue: 0, activeWarranties: 0, subscriptions: 0, mainItems: 0 };
    let totalValue = 0;
    let activeWarranties = 0;
    let subscriptions = 0;
    let mainItems = 0;

    data.nodes.forEach((n) => {
      const isMainItem = HUB_TYPES.includes(n.type);
      if (isMainItem) {
        mainItems++;
        const categoryMatches =
          selectedCategory === "all" || getNodeCategory(n) === selectedCategory;
        if (categoryMatches) {
          const value = Number(n.attributes?.price ?? n.attributes?.amount ?? 0);
          if (Number.isFinite(value) && value > 0) totalValue += value;
        }
      }
      if (n.type === "warranty") {
        const exp = n.attributes?.expiry_date;
        if (!exp || new Date(exp) >= new Date()) activeWarranties++;
      }
      if (n.type === "subscription") subscriptions++;
    });

    return { totalValue, activeWarranties, subscriptions, mainItems };
  }, [data, selectedCategory]);

  // ReactFlow Nodes construction
  const visibleNodes: GraphNode[] = useMemo(() => {
    if (!data) return [];
    if (focusMode && selectedId) {
      return data.nodes.filter((n) => connectedNodeIds.has(n.id));
    }
    return data.nodes;
  }, [data, focusMode, selectedId, connectedNodeIds]);

  const flowNodes: Node[] = useMemo(() => {
    if (!data) return [];
    const positions = layout(visibleNodes, data.edges);

    return visibleNodes.map((n) => {
      const matchesFilter = nodeMatchesFilter(n);
      const dimmed = !matchesFilter;

      return {
        id: n.id,
        type: "mosaic",
        position: positions[n.id] || { x: 0, y: 0 },
        data: {
          label: n.name,
          type: n.type,
          subtitle: subtitle(n),
          selected: n.id === selectedId,
          dimmed,
          highlighted:
            connectedNodeIds.has(n.id) ||
            (hasGraphFilter && matchesFilter),
        },
      };
    });
  }, [data, visibleNodes, selectedId, connectedNodeIds, nodeMatchesFilter, hasGraphFilter]);

  // ReactFlow Edges construction
  const flowEdges: Edge[] = useMemo(() => {
    if (!data) return [];
    const visibleNodeIds = new Set(visibleNodes.map((n) => n.id));
    const graphNodeById = new Map(data.nodes.map((node) => [node.id, node]));

    return data.edges
      .filter((e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target))
      .map((e) => {
        const isConnectedToSelected = selectedId
          ? e.source === selectedId || e.target === selectedId
          : false;
        const sourceNode = graphNodeById.get(e.source);
        const targetNode = graphNodeById.get(e.target);
        const matchesActiveFilter =
          hasGraphFilter &&
          Boolean(sourceNode && targetNode) &&
          (sourceNode ? nodeMatchesFilter(sourceNode) : false) &&
          (targetNode ? nodeMatchesFilter(targetNode) : false);
        const isHighlighted = isConnectedToSelected || matchesActiveFilter;

        return {
          id: e.id,
          source: e.source,
          target: e.target,
          label: isHighlighted ? formatRelationshipLabel(e.type) : undefined,
          type: "smoothstep",
          animated: false,
          style: {
            stroke: isHighlighted ? "#8A79AB" : "#C9D1D8",
            strokeWidth: isHighlighted ? 2.5 : 1.2,
            opacity: selectedId && !isConnectedToSelected ? 0.42 : hasGraphFilter && !matchesActiveFilter ? 0.18 : 0.8,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: isHighlighted ? "#8A79AB" : "#C9D1D8",
            width: 12,
            height: 12,
          },
          labelStyle: {
            fill: "#675A7D",
            fontSize: 10,
            fontWeight: 600,
          },
          labelBgStyle: { fill: "#F8F5FA", fillOpacity: 0.96 },
          labelBgPadding: [6, 3] as [number, number],
        };
      });
  }, [data, visibleNodes, selectedId, hasGraphFilter, nodeMatchesFilter]);

  const onNodeClick: NodeMouseHandler = useCallback((_, node) => {
    setSelectedId(node.id);
  }, []);

  if (!data) return (
    <div className="flex items-center justify-center h-64">
      <div className="flex items-center gap-3 text-sm text-ink-faint">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        Loading your Life Graph…
      </div>
    </div>
  );

  if (data.nodes.length === 0) {
    return (
      <div className="card p-10 text-center">
        <h1 className="font-serif text-xl text-ink">Your Life Graph is empty</h1>
        <p className="mx-auto mt-2 max-w-md text-sm text-ink-soft">
          Add a receipt or a warranty and MOSAIC will start building the map of what you own.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header & Overview Stats Bar */}
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="font-serif text-[28px] text-ink">Life Graph</h1>
          <p className="mt-1 max-w-3xl text-sm leading-relaxed text-ink-soft">
            Your personal asset ecosystem — products, warranties, subscriptions, merchants, and payment methods.
          </p>
        </div>

        {/* Overview Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 card p-4 bg-paper/60">
          <div className="space-y-0.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
              {selectedCategory === "all"
                ? "Total Tracked Value"
                : `${CATEGORIES.find((category) => category.key === selectedCategory)?.label ?? "Selected"} Tracked Value`}
            </span>
            <p className="font-serif text-xl text-ink">₹{metrics.totalValue.toLocaleString("en-IN")}</p>
          </div>
          <div className="space-y-0.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">Active Warranties</span>
            <p className="font-serif text-xl" style={{ color: "#059669" }}>{metrics.activeWarranties} Covered</p>
          </div>
          <div className="space-y-0.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">Subscriptions</span>
            <p className="font-serif text-xl" style={{ color: "#7C3AED" }}>{metrics.subscriptions} Active</p>
          </div>
          <div className="space-y-0.5">
            <span
              className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint"
              title="Counts primary products, assets, subscriptions, bills, and expenses—not connected brands, merchants, payment methods, or documents."
            >
              Main Items
            </span>
            <p className="font-serif text-xl text-ink">{metrics.mainItems} Items</p>
          </div>
        </div>
      </div>

      {/* Filter Control Bar */}
      <div className="card p-4 space-y-4">
        {/* Row 1: Search & Toggles */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="relative flex-1 max-w-md">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search product, merchant, warranty, document, subscription..."
              className="w-full rounded-lg border border-line bg-paper px-3.5 py-2 text-sm text-ink outline-none focus:border-accent"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-2.5 text-xs text-ink-faint hover:text-ink"
              >
                Clear
              </button>
            )}
          </div>

        </div>
      </div>

      {/* Main Canvas & Inspector Drawer */}
      <div className="flex flex-col gap-5 lg:flex-row">
        <div
          className="card h-[640px] flex-1 overflow-hidden relative"
          style={{ background: "#FBF9F6" }}
        >
          <ReactFlowProvider>
            <ReactFlow
              nodes={flowNodes}
              edges={flowEdges}
              nodeTypes={nodeTypes}
              onNodeClick={onNodeClick}
              onPaneClick={() => setSelectedId(null)}
              fitView
              fitViewOptions={{ padding: 0.15, maxZoom: 0.9 }}
              minZoom={0.15}
              maxZoom={2}
              proOptions={{ hideAttribution: true }}
            >
              <Background variant={BackgroundVariant.Dots} gap={30} size={1} color="#EAE5DE" />
              <Controls
                position="bottom-left"
                showInteractive={false}
                aria-label="Graph navigation controls: zoom in, zoom out, and fit graph to view"
              />
            </ReactFlow>
          </ReactFlowProvider>

          <div className="absolute right-3 top-3 z-20">
            <button
              type="button"
              aria-label="Open graph options"
              aria-expanded={showGraphMenu}
              onClick={() => setShowGraphMenu((open) => !open)}
              className={`flex h-10 w-10 items-center justify-center rounded-xl border shadow-sm transition-colors ${
                showGraphMenu
                  ? "border-indigo-500 bg-indigo-600 text-white"
                  : "border-line bg-white/95 text-ink hover:border-indigo-400 hover:text-indigo-700"
              }`}
              title="Graph options"
            >
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
              </svg>
            </button>
            {showGraphMenu && (
              <div className="absolute right-0 top-12 w-[min(320px,calc(100vw-3rem))] rounded-xl border border-line bg-white/95 p-3 shadow-xl backdrop-blur">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-bold uppercase tracking-wider text-ink">Graph options</h2>
                  <button
                    type="button"
                    aria-label="Close graph options"
                    onClick={() => setShowGraphMenu(false)}
                    className="rounded px-2 py-1 text-xs text-ink-faint hover:bg-line/40"
                  >
                    Close
                  </button>
                </div>
                <p className="mt-1 text-[11px] text-ink-faint">Choose an option to highlight matching entities.</p>

                <div className="mt-3 grid grid-cols-2 gap-1.5">
                  {CATEGORIES.map((category) => {
                    const active = selectedCategory === category.key;
                    return (
                      <button
                        key={category.key}
                        type="button"
                        aria-pressed={active}
                        onClick={() => {
                          setSelectedCategory(category.key);
                          setOnlySubscriptions(false);
                          setShowGraphMenu(false);
                        }}
                        className={`rounded-lg border px-2.5 py-2 text-left text-[11px] font-medium transition-colors ${
                          active
                            ? "border-indigo-500 bg-indigo-600 text-white shadow-sm"
                            : "border-line bg-paper text-ink-soft hover:border-indigo-300 hover:bg-indigo-50"
                        }`}
                      >
                        <span className="mr-1.5">{category.icon}</span>
                        {category.label}
                      </button>
                    );
                  })}
                </div>

                <label className="mt-3 block text-[11px] font-semibold text-ink-soft">
                  Warranty status
                  <select
                    value={warrantyFilter}
                    onChange={(event) => setWarrantyFilter(event.target.value as "all" | "active" | "expired")}
                    className="mt-1 w-full rounded-lg border border-line bg-white px-2.5 py-2 text-xs text-ink outline-none focus:border-indigo-500"
                  >
                    <option value="all">All warranties</option>
                    <option value="active">Active warranties</option>
                    <option value="expired">Expired warranties</option>
                  </select>
                </label>

                <div className="mt-3 space-y-2 border-t border-line/70 pt-3">
                  <label className="flex items-center justify-between text-xs text-ink-soft">
                    <span>Focus selected entity and its links</span>
                    <input
                      type="checkbox"
                      checked={focusMode}
                      onChange={(event) => setFocusMode(event.target.checked)}
                      className="rounded border-line text-indigo-600 focus:ring-indigo-500"
                    />
                  </label>
                  <label className="flex items-center justify-between text-xs text-ink-soft">
                    <span>Highlight subscriptions</span>
                    <input
                      type="checkbox"
                      checked={onlySubscriptions}
                      onChange={(event) => setOnlySubscriptions(event.target.checked)}
                      className="rounded border-line text-indigo-600 focus:ring-indigo-500"
                    />
                  </label>
                </div>
              </div>
            )}
          </div>

        </div>

        {/* Structured Relationship Inspector Side Drawer */}
        <aside className="card w-full shrink-0 overflow-y-auto p-5 lg:w-[380px] lg:max-h-[640px]">
          {!detail ? (
            <div className="flex h-full flex-col items-center justify-center py-14 text-center">
              <div className="mb-4 text-4xl opacity-30">🔍</div>
              <p className="text-sm text-ink-faint">Select an entity in your Life Graph to view purchase info, warranty status, related documents, and connections.</p>
            </div>
          ) : (
            <div className="space-y-5">
              <div>
                <div className="flex items-center gap-2">
                  <span className="label uppercase tracking-wider">{detail.entity.type}</span>
                  <span className="text-[10px] font-semibold text-accent uppercase tracking-wider px-2 py-0.5 rounded bg-accent/10">
                    {getNodeCategory(detail.entity)}
                  </span>
                </div>
                <h2 className="mt-1.5 font-serif text-[22px] leading-snug text-ink">
                  {detail.entity.name}
                </h2>
              </div>

              {/* Summary Metrics */}
              <div className="grid grid-cols-2 gap-2 text-center">
                {[
                  ["Links", detail.counts.connections],
                  ["Docs", detail.counts.documents],
                ].map(([label, value]) => (
                  <div key={label as string} className="rounded-xl bg-paper py-2.5 border border-line/60">
                    <div className="font-serif text-[19px] text-ink">{value as number}</div>
                    <div className="text-[10px] uppercase tracking-wider text-ink-faint font-semibold">
                      {label as string}
                    </div>
                  </div>
                ))}
              </div>

              {/* 🛒 Purchase & Cost Information */}
              {(detail.entity.attributes?.price ||
                detail.entity.attributes?.seller ||
                detail.entity.attributes?.purchase_date ||
                detail.entity.attributes?.amount) && (
                <div className="rounded-xl bg-paper/70 p-3.5 border border-line/70 space-y-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-ink flex items-center gap-1.5">
                    <span>🛒</span> Purchase Information
                  </h3>
                  <dl className="divide-y divide-line/60 text-xs">
                    {detail.entity.attributes?.price && (
                      <div className="flex justify-between py-1">
                        <dt className="text-ink-faint">Price / Cost</dt>
                        <dd className="font-semibold text-ink">
                          ₹{Number(detail.entity.attributes.price).toLocaleString("en-IN")}
                        </dd>
                      </div>
                    )}
                    {detail.entity.attributes?.amount && (
                      <div className="flex justify-between py-1">
                        <dt className="text-ink-faint">Amount Due / Cost</dt>
                        <dd className="font-semibold text-ink">
                          ₹{Number(detail.entity.attributes.amount).toLocaleString("en-IN")}
                        </dd>
                      </div>
                    )}
                    {detail.entity.attributes?.seller && (
                      <div className="flex justify-between py-1">
                        <dt className="text-ink-faint">Merchant / Seller</dt>
                        <dd className="font-medium text-ink">{detail.entity.attributes.seller}</dd>
                      </div>
                    )}
                    {detail.entity.attributes?.purchase_date && (
                      <div className="flex justify-between py-1">
                        <dt className="text-ink-faint">Purchase Date</dt>
                        <dd className="font-medium text-ink">{detail.entity.attributes.purchase_date}</dd>
                      </div>
                    )}
                  </dl>
                </div>
              )}

              {/* 🛡️ Warranty Coverage */}
              {(detail.entity.type === "warranty" ||
                detail.entity.attributes?.expiry_date ||
                detail.entity.attributes?.provider) && (
                <div className="rounded-xl bg-amber-50/70 p-3.5 border border-amber-200/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-amber-900 flex items-center gap-1.5">
                      <span>🛡️</span> Warranty Status
                    </h3>
                    {detail.entity.attributes?.expiry_date && (
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                          new Date(detail.entity.attributes.expiry_date) >= new Date()
                            ? "bg-green-100 text-green-800"
                            : "bg-red-100 text-red-800"
                        }`}
                      >
                        {new Date(detail.entity.attributes.expiry_date) >= new Date() ? "Active" : "Expired"}
                      </span>
                    )}
                  </div>
                  <dl className="divide-y divide-amber-200/60 text-xs">
                    {detail.entity.attributes?.provider && (
                      <div className="flex justify-between py-1">
                        <dt className="text-amber-800/80">Provider</dt>
                        <dd className="font-medium text-amber-950">{detail.entity.attributes.provider}</dd>
                      </div>
                    )}
                    {detail.entity.attributes?.expiry_date && (
                      <div className="flex justify-between py-1">
                        <dt className="text-amber-800/80">Expiry Date</dt>
                        <dd className="font-medium text-amber-950">{detail.entity.attributes.expiry_date}</dd>
                      </div>
                    )}
                  </dl>
                </div>
              )}

              {/* Attributes & Details */}
              {Object.keys(detail.entity.attributes || {}).length > 0 && (
                <div>
                  <h3 className="label">Attributes</h3>
                  <dl className="mt-2 divide-y divide-line">
                    {Object.entries(detail.entity.attributes)
                      .filter(
                        ([key]) =>
                          !["model_codes", "price", "amount", "seller", "purchase_date", "expiry_date", "provider"].includes(key)
                      )
                      .map(([key, value]) => (
                        <div key={key} className="flex justify-between gap-3 py-1.5">
                          <dt className="text-[12px] text-ink-faint">{formatFieldLabel(key)}</dt>
                          <dd className="text-right text-[13px] text-ink font-medium">
                            {formatValue(value)}
                          </dd>
                        </div>
                      ))}
                  </dl>
                </div>
              )}

              {/* Connected Entities */}
              {detail.connections.length > 0 && (
                <div>
                  <h3 className="label">Connected Entities</h3>
                  <ul className="mt-2 space-y-1.5">
                    {detail.connections.map((c: any) => (
                      <li key={c.id}>
                        <button
                          onClick={() => setSelectedId(c.id)}
                          className="w-full rounded-lg border border-line bg-paper/60 px-3 py-2 text-left text-[13px] text-ink hover:bg-paper hover:border-accent transition-colors flex items-center justify-between"
                        >
                          <span className="font-medium text-accent">
                            {formatRelationshipLabel(c.relationship)} →
                          </span>
                          <span className="font-semibold text-ink truncate max-w-[170px]">{c.name}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Related Documents */}
              {detail.documents.length > 0 && (
                <div>
                  <h3 className="label">Related Documents</h3>
                  <ul className="mt-2 space-y-1.5 text-[13px] text-ink-soft">
                    {detail.documents.map((d: any) => (
                      <li key={d.id} className="rounded-lg bg-paper px-3 py-2 border border-line/60">
                        📄 {d.title}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
