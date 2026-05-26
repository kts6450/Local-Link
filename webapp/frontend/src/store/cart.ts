import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { CartLine } from "../types";

interface AddOpts {
  stay_start?: string | null;
  stay_end?: string | null;
  variant_label?: string | null;
  variant_price?: number | null;
}

interface CartState {
  lines: CartLine[];
  add: (listingId: string, qty?: number, opts?: AddOpts) => void;
  setQty: (
    listingId: string,
    qty: number,
    stay_start?: string | null,
    stay_end?: string | null,
    variant_label?: string | null
  ) => void;
  remove: (
    listingId: string,
    stay_start?: string | null,
    stay_end?: string | null,
    variant_label?: string | null
  ) => void;
  clear: () => void;
}

const sameLine = (
  l: CartLine,
  listingId: string,
  stay_start: string | null,
  stay_end: string | null,
  variant_label: string | null
) =>
  l.listingId === listingId &&
  (l.stay_start ?? null) === stay_start &&
  (l.stay_end ?? null) === stay_end &&
  (l.variant_label ?? null) === variant_label;

export const useCart = create<CartState>()(
  persist(
    (set, get) => ({
      lines: [],
      add: (listingId, qty = 1, opts) => {
        const lines = [...get().lines];
        const stay_start = opts?.stay_start ?? null;
        const stay_end = opts?.stay_end ?? null;
        const variant_label = opts?.variant_label ?? null;
        const variant_price = opts?.variant_price ?? null;
        const i = lines.findIndex((l) =>
          sameLine(l, listingId, stay_start, stay_end, variant_label)
        );
        if (i >= 0) {
          lines[i] = { ...lines[i], quantity: lines[i].quantity + qty };
        } else {
          lines.push({
            listingId,
            quantity: qty,
            stay_start,
            stay_end,
            variant_label,
            variant_price,
          });
        }
        set({ lines });
      },
      setQty: (listingId, qty, stay_start = null, stay_end = null, variant_label = null) => {
        const lines = get()
          .lines.map((l) =>
            sameLine(l, listingId, stay_start, stay_end, variant_label)
              ? { ...l, quantity: Math.max(1, qty) }
              : l
          )
          .filter((l) => l.quantity > 0);
        set({ lines });
      },
      remove: (listingId, stay_start = null, stay_end = null, variant_label = null) =>
        set({
          lines: get().lines.filter(
            (l) => !sameLine(l, listingId, stay_start, stay_end, variant_label)
          ),
        }),
      clear: () => set({ lines: [] }),
    }),
    { name: "local-link-cart-v3" }
  )
);
