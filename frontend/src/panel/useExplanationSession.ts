import { useCallback, useState } from "react";
import type { Pin } from "../types";

export type StackItem = {
  pin: Pin;
  expanded: boolean;
};

type Session = {
  current: Pin | null;
  stack: StackItem[];
  panelOpen: boolean;
  everOpened: boolean;
  stackEpoch: number;
};

const emptySession: Session = {
  current: null,
  stack: [],
  panelOpen: false,
  everOpened: false,
  stackEpoch: 0,
};

export function useExplanationSession() {
  const [session, setSession] = useState<Session>(emptySession);
  const [focusPinId, setFocusPinId] = useState<string | null>(null);

  const activateFromPage = useCallback((pin: Pin) => {
    setFocusPinId(pin.id);
    setSession((prev) => {
      if (prev.current?.id === pin.id) {
        return { ...prev, panelOpen: true, everOpened: true };
      }
      const nextStack = prev.current
        ? [
            { pin: prev.current, expanded: false },
            ...prev.stack.filter(
              (item) => item.pin.id !== pin.id && item.pin.id !== prev.current!.id,
            ),
          ]
        : prev.stack.filter((item) => item.pin.id !== pin.id);
      return {
        current: pin,
        stack: nextStack,
        panelOpen: true,
        everOpened: true,
        stackEpoch: prev.current ? prev.stackEpoch + 1 : prev.stackEpoch,
      };
    });
  }, []);

  const toggleStack = useCallback((pinId: string) => {
    setFocusPinId(pinId);
    setSession((prev) => ({
      ...prev,
      stack: prev.stack.map((item) =>
        item.pin.id === pinId ? { ...item, expanded: !item.expanded } : item,
      ),
    }));
  }, []);

  const closePanel = useCallback(() => {
    setSession((prev) => ({ ...prev, panelOpen: false }));
  }, []);

  const reopenPanel = useCallback(() => {
    setSession((prev) => (prev.everOpened ? { ...prev, panelOpen: true } : prev));
  }, []);

  return {
    current: session.current,
    stack: session.stack,
    panelOpen: session.panelOpen,
    everOpened: session.everOpened,
    stackEpoch: session.stackEpoch,
    focusPinId,
    activateFromPage,
    toggleStack,
    closePanel,
    reopenPanel,
  };
}
