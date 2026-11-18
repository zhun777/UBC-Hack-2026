"use client";

import { useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import { PROGRAMS, CURRENT_PROGRAM, type Program } from "@/lib/programs";

/** Shows the current rewards program; other programs are listed as coming soon. */
export function ProgramSwitcher() {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 rounded-2xl border border-stone-200 px-4 py-3 text-left hover:border-stone-400 transition"
      >
        <ProgramLogo program={CURRENT_PROGRAM} />
        <div className="flex-1">
          <p className="font-medium">{CURRENT_PROGRAM.name}</p>
          <p className="text-xs text-stone-500">{CURRENT_PROGRAM.countries}</p>
        </div>
        <ChevronDown size={18} className={`text-stone-400 transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute inset-x-0 top-full z-10 mt-2 overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-lg divide-y divide-stone-100">
          {PROGRAMS.map((program) => (
            <button
              key={program.id}
              disabled={!program.live}
              onClick={() => setOpen(false)}
              className="flex w-full items-center gap-3 px-4 py-3 text-left disabled:cursor-default"
            >
              <ProgramLogo program={program} faded={!program.live} />
              <div className="flex-1">
                <p className={`font-medium ${program.live ? "" : "text-stone-400"}`}>{program.name}</p>
                <p className="text-xs text-stone-400">{program.description}</p>
              </div>
              {program.live ? (
                <Check size={18} className="text-green-700" />
              ) : (
                <span className="rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-500">Coming soon</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ProgramLogo({ program, faded = false }: { program: Program; faded?: boolean }) {
  return (
    <div
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white ${program.color} ${
        faded ? "opacity-40" : ""
      }`}
    >
      {program.name[0]}
    </div>
  );
}
