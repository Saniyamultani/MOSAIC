"use client";

import { Handle, NodeProps, Position } from "reactflow";
import { nodeStyle } from "@/lib/api";

export interface MosaicNodeData {
  label: string;
  type: string;
  subtitle?: string;
  selected?: boolean;
  dimmed?: boolean;
  highlighted?: boolean;
}

const TYPE_LABEL: Record<string, string> = {
  product: "Product",
  asset: "Asset",
  purchase: "Purchase",
  brand: "Brand",
  retailer: "Merchant",
  service: "Service",
  warranty: "Warranty",
  subscription: "Subscription",
  payment_method: "Payment",
  bill: "Bill / Expense",
  expense: "Expense",
  document: "Document",
  event: "Event",
};

export default function GraphNodeCard({ data, selected }: NodeProps<MosaicNodeData>) {
  const style = nodeStyle(data.type);
  const isSelected = selected || data.selected;
  const isDimmed = data.dimmed;
  const isHighlighted = data.highlighted;

  return (
    <div
      className={`mosaic-node w-[190px] rounded-xl border px-3.5 py-2.5 text-left transition-all duration-200 ${
        isSelected ? "ring-2 ring-accent shadow-md scale-105 z-20" : ""
      } ${isHighlighted && !isSelected ? "ring-1 ring-accent/60 z-10" : ""} ${
        isDimmed ? "opacity-25 grayscale-[20%]" : "opacity-100"
      }`}
      style={{
        background: style.bg,
        borderColor: isSelected ? style.text : isHighlighted ? style.text : style.border,
        color: style.text,
        borderWidth: isSelected || isHighlighted ? 2 : 1,
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <div className="flex items-center justify-between">
        <div className="text-[9px] uppercase tracking-[0.14em] font-semibold opacity-75">
          {TYPE_LABEL[data.type] || data.type}
        </div>
      </div>
      <div className="mt-1 text-[13px] font-semibold leading-snug line-clamp-2">{data.label}</div>
      {data.subtitle && (
        <div className="mt-0.5 text-[11px] opacity-75 truncate">{data.subtitle}</div>
      )}
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}
