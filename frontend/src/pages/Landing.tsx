import { Link } from "react-router-dom";
import type { IconType } from "react-icons";
import { m } from "framer-motion";
import {
  FiActivity,
  FiArrowRight,
  FiBarChart2,
  FiGitMerge,
  FiMessageSquare,
  FiShield,
  FiTarget,
} from "react-icons/fi";

interface Feature {
  icon: IconType;
  title: string;
  description: string;
}

const FEATURES: Feature[] = [
  { icon: FiMessageSquare, title: "Natural Language Investigation", description: "Ask questions in plain English — the agent interprets intent, entities, and filters." },
  { icon: FiTarget, title: "AML Pattern Detection", description: "Deterministic rules for structuring, smurfing, layering, and rapid cash-out." },
  { icon: FiShield, title: "Risk Classification", description: "Flagged entities scored and banded into low, medium, and high risk." },
  { icon: FiActivity, title: "Explainable AI", description: "Every flag carries an evidence-grounded reason and a recommended action." },
  { icon: FiBarChart2, title: "Interactive Visualizations", description: "Plotly charts for timelines, distributions, and per-entity risk signals." },
  { icon: FiGitMerge, title: "Execution Pipeline", description: "A transparent, step-by-step trace of every tool the agent ran." },
];

const TECH = ["React", "TypeScript", "FastAPI", "Machine Learning", "LLM", "Plotly", "Tailwind"];

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } },
};

export default function Landing() {
  return (
    <div className="relative min-h-screen">
      {/* Top bar */}
      <header className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-accent to-accent-deep text-surface-950 shadow-glow">
            <FiShield className="h-5 w-5" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-extrabold tracking-tight text-slate-100">AEGIS</div>
            <div className="text-[11px] font-medium uppercase tracking-[0.18em] text-slate-500">AML Intelligence</div>
          </div>
        </div>
        <Link to="/dashboard" className="btn-outline">
          Launch Console
        </Link>
      </header>

      {/* Hero */}
      <m.section
        variants={container}
        initial="hidden"
        animate="show"
        className="mx-auto max-w-4xl px-6 pb-16 pt-10 text-center sm:pt-16"
      >
        <m.span variants={item} className="chip mx-auto border-accent/30 bg-accent/10 text-accent">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Enterprise AML Investigation Platform
        </m.span>
        <m.h1
          variants={item}
          className="mt-6 bg-gradient-to-b from-white to-slate-400 bg-clip-text text-4xl font-extrabold tracking-tight text-transparent sm:text-6xl"
        >
          AEGIS AML Intelligence
        </m.h1>
        <m.p variants={item} className="mt-4 text-lg font-semibold text-accent sm:text-xl">
          AI-Powered Financial Crime Investigation Platform
        </m.p>
        <m.p variants={item} className="mx-auto mt-4 max-w-2xl text-base leading-relaxed text-slate-400">
          Enterprise-grade AML investigation powered by AI, Machine Learning, Explainable Analytics and Natural
          Language Investigation.
        </m.p>
        <m.div variants={item} className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link to="/dashboard" className="btn-accent">
            Start Investigation
            <FiArrowRight className="h-4 w-4" />
          </Link>
          <Link to="/architecture" className="btn-outline">
            View Architecture
          </Link>
        </m.div>
      </m.section>

      {/* Features */}
      <section id="features" className="mx-auto max-w-7xl px-6 py-8">
        <h2 className="mb-6 text-center text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
          Capabilities
        </h2>
        <m.div
          variants={container}
          initial="hidden"
          animate="show"
          className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3"
        >
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <m.div key={title} variants={item} whileHover={{ y: -4 }} className="feature-card">
              <div className="mb-4 grid h-11 w-11 place-items-center rounded-xl border border-white/10 bg-white/5 text-accent">
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="text-base font-semibold text-slate-100">{title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-400">{description}</p>
            </m.div>
          ))}
        </m.div>
      </section>

      {/* Technology stack */}
      <section id="architecture" className="mx-auto max-w-7xl px-6 py-14">
        <div className="glass p-8 text-center">
          <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Technology Stack</h2>
          <p className="mx-auto mt-2 max-w-xl text-sm text-slate-400">
            A modern, explainable architecture — a React + TypeScript frontend over a FastAPI agent that combines
            deterministic AML rules, machine learning, and a single LLM understanding call.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-2.5">
            {TECH.map((tech) => (
              <span
                key={tech}
                className="chip border-white/10 bg-white/5 px-3 py-1.5 text-slate-300 transition-colors hover:border-accent/40 hover:text-accent"
              >
                {tech}
              </span>
            ))}
          </div>
          <div className="mt-8">
            <Link to="/dashboard" className="btn-accent">
              Start Investigation
              <FiArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mx-auto max-w-7xl px-6 py-10">
        <div className="flex flex-col items-center justify-between gap-3 border-t border-white/10 pt-6 text-sm text-slate-500 sm:flex-row">
          <div className="flex items-center gap-2 font-semibold text-slate-300">
            <FiShield className="h-4 w-4 text-accent" />
            AEGIS AML Intelligence
          </div>
          <div className="flex items-center gap-4">
            <span>v0.1.0</span>
            <span className="text-slate-600">·</span>
            <span>Team AEGIS</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
