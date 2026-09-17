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

const HUB_TYPES = ["product", "subscription", "bill"];
const nodeTypes = { mosaic: GraphNodeCard };

/**
 * Deterministic radial layout: hub nodes (the things you own) on a grid, their
 * satellites fanned around them, then a few passes of collision relaxation so
 * nothing overlaps. Nodes stay draggable afterwards.
 */
const NODE_W = 210;
const NODE_H = 108;

function layout(nodes: GraphNode[], edges: GraphEdge[]) {
  const hubs = nodes.filter((n) => HUB_TYPES.includes(n.type));
  const satellites = nodes.filter((n) => !HUB_TYPES.includes(n.type));
  const positions: Record<string, { x: number; y: number }> = {};

  const columns = hubs.length > 4 ? 3 : 2;
  hubs.forEach((hub, i) => {
    positions[hub.id] = {
      x: (i % columns) * 720,
      y: Math.floor(i / columns) * 600,
    };
  });

  const neighboursOf = (id: string) =>
    edges
      .filter((e) => e.source === id || e.target === id)
      .map((e) => (e.source === id ? e.target : e.source));

  // Fan each hub's own satellites evenly around it.
  const placedAround: Record<string, number> = {};
  satellites.forEach((sat) => {
    const linkedHubs = neighboursOf(sat.id).filter((id) => positions[id]);
    const anchorIds = linkedHubs.length ? linkedHubs : [hubs[0]?.id].filter(Boolean);
    const anchors = anchorIds.map((id) => positions[id]).filter(Boolean);
    const cx = anchors.length ? anchors.reduce((s, p) => s + p.x, 0) / anchors.length : 0;
    const cy = anchors.length ? anchors.reduce((s, p) => s + p.y, 0) / anchors.length : 0;

    const shared = linkedHubs.length > 1;
    const anchorKey = shared ? "shared" : anchorIds[0] || "orphan";
    const index = placedAround[anchorKey] ?? 0;
    placedAround[anchorKey] = index + 1;

    // Sweep from -110° to +110° so satellites sit to the right of their hub.
    const spread = shared ? 360 : 220;
    const start = shared ? 0 : -110;
    const angle = ((start + (index + 0.5) * (spread / 5)) * Math.PI) / 180;
    const radius = shared ? 380 : 285;
    positions[sat.id] = { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius };
  });

  // Relaxation: push apart anything still overlapping.
  const ids = nodes.map((n) => n.id);
  for (let pass = 0; pass < 90; pass++) {
    let moved = false;
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const a = positions[ids[i]];
        const b = positions[ids[j]];
        if (!a || !b) continue;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const overlapX = NODE_W + 40 - Math.abs(dx);
        const overlapY = NODE_H + 30 - Math.abs(dy);
        if (overlapX > 0 && overlapY > 0) {
          moved = true;
          if (overlapX / NODE_W < overlapY / NODE_H) {
            const push = (overlapX / 2 + 1) * (dx >= 0 ? 1 : -1);
            a.x -= push;
            b.x += push;
          } else {
            const push = (overlapY / 2 + 1) * (dy >= 0 ? 1 : -1);
            a.y -= push;
            b.y += push;
          }
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
  if (a.model_code) return a.model_code;
  return undefined;
}

export default function GraphPage() {
  const [data, setData] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] } | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<any>(null);

  useEffect(() => {
    api.graph().then(setData).catch(() => setData({ nodes: [], edges: [] }));
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    api.entity(selectedId).then(setDetail).catch(() => setDetail(null));
  }, [selectedId]);

  const flowNodes: Node[] = useMemo(() => {
    if (!data) return [];
    const positions = layout(data.nodes, data.edges);
    return data.nodes.map((n) => ({
      id: n.id,
      type: "mosaic",
      position: positions[n.id] || { x: 0, y: 0 },
      data: { label: n.name, type: n.type, subtitle: subtitle(n) },
      selected: n.id === selectedId,
    }));
  }, [data, selectedId]);

  const flowEdges: Edge[] = useMemo(() => {
    if (!data) return [];
    return data.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.type.replace(/_/g, " ").toLowerCase(),
      type: "smoothstep",
      animated: false,
      markerEnd: { type: MarkerType.ArrowClosed, color: "#C9C2B8", width: 14, height: 14 },
      labelStyle: { fill: "#8A93A0", fontSize: 9 },
      labelBgStyle: { fill: "#FAF7F2" },
      labelBgPadding: [4, 2] as [number, number],
    }));
  }, [data]);

  const onNodeClick: NodeMouseHandler = useCallback((_, node) => setSelectedId(node.id), []);

  if (!data) return <p className="text-sm text-ink-faint">Loading the Life Graph…</p>;

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
    <div className="space-y-5">
      <div>
        <h1 className="font-serif text-[28px] text-ink">Life Graph</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-soft">
          {data.nodes.length} things, {data.edges.length} relationships. Click any node to see
          what MOSAIC knows about it and what it is connected to.
        </p>
      </div>

      <div className="flex flex-col gap-5 lg:flex-row">
        <div
          className="card h-[620px] flex-1 overflow-hidden"
          style={{ background: "#FCFAF7" }}
        >
          <ReactFlowProvider>
            <ReactFlow
              nodes={flowNodes}
              edges={flowEdges}
              nodeTypes={nodeTypes}
              onNodeClick={onNodeClick}
              onPaneClick={() => setSelectedId(null)}
              fitView
              fitViewOptions={{ padding: 0.18, maxZoom: 1 }}
              minZoom={0.25}
              proOptions={{ hideAttribution: true }}
            >
              <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#E7E1D8" />
              <Controls showInteractive={false} className="!shadow-none" />
            </ReactFlow>
          </ReactFlowProvider>
        </div>

        <aside className="card w-full shrink-0 overflow-y-auto p-5 lg:w-[340px] lg:max-h-[620px]">
          {!detail ? (
            <div className="flex h-full flex-col items-center justify-center py-14 text-center">
              <p className="text-sm text-ink-faint">Select a node to inspect it.</p>
            </div>
          ) : (
            <div className="space-y-5">
              <div>
                <span className="label">{detail.entity.type}</span>
                <h2 className="mt-1 font-serif text-[20px] leading-snug text-ink">
                  {detail.entity.name}
                </h2>
              </div>

              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  ["Links", detail.counts.connections],
                  ["Docs", detail.counts.documents],
                  ["Alerts", detail.counts.alerts],
                ].map(([label, value]) => (
                  <div key={label as string} className="rounded-xl bg-paper py-2.5">
                    <div className="font-serif text-[19px] text-ink">{value as number}</div>
                    <div className="text-[10px] uppercase tracking-wider text-ink-faint">
                      {label as string}
                    </div>
                  </div>
                ))}
              </div>

              {Object.keys(detail.entity.attributes || {}).length > 0 && (
                <div>
                  <h3 className="label">Details</h3>
                  <dl className="mt-2 divide-y divide-line">
                    {Object.entries(detail.entity.attributes)
                      .filter(([key]) => key !== "model_codes")
                      .map(([key, value]) => (
                      <div key={key} className="flex justify-between gap-3 py-1.5">
                        <dt className="text-[12px] text-ink-faint">
                          {formatFieldLabel(key)}
                        </dt>
                        <dd className="text-right text-[13px] text-ink">
                          {formatValue(value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}

              {detail.connections.length > 0 && (
                <div>
                  <h3 className="label">Connected to</h3>
                  <ul className="mt-2 space-y-1.5">
                    {detail.connections.map((c: any) => (
                      <li key={c.id}>
                        <button
                          onClick={() => setSelectedId(c.id)}
                          className="w-full rounded-lg px-2 py-1.5 text-left text-[13px] text-ink hover:bg-paper"
                        >
                          <span className="text-ink-faint">
                            {c.relationship.replace(/_/g, " ").toLowerCase()} ·{" "}
                          </span>
                          {c.name}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {detail.documents.length > 0 && (
                <div>
                  <h3 className="label">Documents</h3>
                  <ul className="mt-2 space-y-1.5 text-[13px] text-ink-soft">
                    {detail.documents.map((d: any) => (
                      <li key={d.id} className="rounded-lg bg-paper px-2.5 py-1.5">
                        {d.title}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {detail.alerts.length > 0 && (
                <div>
                  <h3 className="label">Alerts on this</h3>
                  <ul className="mt-2 space-y-1.5 text-[13px]">
                    {detail.alerts.map((a: any) => (
                      <li key={a.id} className="rounded-lg bg-paper px-2.5 py-1.5 text-ink">
                        {a.headline}
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
