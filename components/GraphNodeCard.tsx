"use client";

import { Handle, NodeProps, Position } from "reactflow";
import { nodeStyle } from "@/lib/api";

export interface MosaicNodeData {
  label: string;
  type: string;
  subtitle?: string;
  selected?: boolean;
}

const TYPE_LABEL: Record<string, string> = {
  product: "Product",
  brand: "Brand",
  retailer: "Retailer",
  warranty: "Warranty",
  subscription: "Subscription",
  payment_method: "Payment",
  bill: "Bill",
  event: "Event",
};

export default function GraphNodeCard({ data, selected }: NodeProps<MosaicNodeData>) {
  const style = nodeStyle(data.type);
  return (
    <div
      className={`mosaic-node w-[172px] rounded-xl border px-3.5 py-2.5 text-left ${
        selected ? "is-selected" : ""
      }`}
      style={{
        background: style.bg,
        borderColor: selected ? style.text : style.border,
        color: style.text,
        borderWidth: selected ? 2 : 1,
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <div className="text-[9px] uppercase tracking-[0.14em] opacity-70">
        {TYPE_LABEL[data.type] || data.type}
      </div>
      <div className="mt-1 text-[13px] font-medium leading-snug">{data.label}</div>
      {data.subtitle && (
        <div className="mt-0.5 text-[11px] opacity-70">{data.subtitle}</div>
      )}
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}
