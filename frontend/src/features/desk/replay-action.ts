"use server";

import { AckviaApiError, replayDelivery } from "@/lib/api";

export async function queueDeliveryReplay(
  deliveryId: number,
): Promise<{ ok: true } | { ok: false; message: string }> {
  if (!Number.isSafeInteger(deliveryId) || deliveryId <= 0) {
    return { ok: false, message: "This delivery ID is invalid." };
  }
  try {
    await replayDelivery(deliveryId);
    return { ok: true };
  } catch (error) {
    if (error instanceof AckviaApiError) {
      if (error.status === 404) {
        return { ok: false, message: "This delivery no longer exists." };
      }

      if (error.status === 409) {
        return {
          ok: false,
          message: "This delivery is not replayable in its current state.",
        };
      }
    }

    return { ok: false, message: "We couldn't queue the delivery replay." };
  }
}
