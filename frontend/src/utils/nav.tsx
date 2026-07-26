import type { IconType } from "react-icons";
import { FiActivity, FiClock, FiGitMerge, FiGrid, FiSearch, FiShare2 } from "react-icons/fi";

export interface NavItem {
  label: string;
  to: string;
  icon: IconType;
  /** Phase where this route becomes functional (informational for Phase 1). */
  ready: boolean;
}

/** Primary navigation. Analyze + Pipeline are shipped; History/Activity are pending. */
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", to: "/dashboard", icon: FiGrid, ready: true },
  { label: "Analyze", to: "/analyze", icon: FiSearch, ready: true },
  { label: "Pipeline", to: "/pipeline", icon: FiGitMerge, ready: true },
  { label: "Architecture", to: "/architecture", icon: FiShare2, ready: true },
  { label: "History", to: "/history", icon: FiClock, ready: false },
  { label: "Activity", to: "/activity", icon: FiActivity, ready: false },
];
