import { Suspense } from "react";
import { Screen, Spinner } from "@/components/ui";
import { PayOrder } from "./pay-order";

export default function PayOrderPage() {
  return (
    <Suspense
      fallback={
        <Screen nav>
          <div className="pt-20 text-center text-stone-400">
            <Spinner />
          </div>
        </Screen>
      }
    >
      <PayOrder />
    </Suspense>
  );
}
