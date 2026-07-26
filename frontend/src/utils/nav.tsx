import type { IconType } from "react-icons";
import { FiActivity, FiClock, FiGitMerge, FiGrid, FiSearch, FiShare2 } from "react-icons/fi";

export interface NavItem {
  label: string;
  to: string;
  icon: IconType;
  /** Whether the destination is a fully shipped page (drives the "Soon" badge). */
  ready: boolean;
}

/** Primary navigation. All destinations are shipped. */
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", to: "/dashboard", icon: FiGrid, ready: true },
  { label: "Analyze", to: "/analyze", icon: FiSearch, ready: true },
  { label: "Pipeline", to: "/pipeline", icon: FiGitMerge, ready: true },
  { label: "Architecture", to: "/architecture", icon: FiShare2, ready: true },
  { label: "History", to: "/history", icon: FiClock, ready: true },
  { label: "Activity", to: "/activity", icon: FiActivity, ready: true },
];
