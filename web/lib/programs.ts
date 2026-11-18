// Rewards programs on the $APP network. Each program has its own points that
// work in every country it operates in. Only Treehouse is live in the demo;
// the rest are frontend-only placeholders for the "what's next" story.

export type Program = {
  id: string;
  name: string;
  description: string;
  countries: string;
  color: string; // Tailwind background class for the logo circle
  live: boolean;
};

export const PROGRAMS: Program[] = [
  {
    id: "treehouse",
    name: "Treehouse Rewards",
    description: "Treehouse Supply Co. · Treehouse Café",
    countries: "United States · Singapore",
    color: "bg-green-700",
    live: true,
  },
  {
    id: "lumen",
    name: "Lumen Coffee Club",
    description: "Specialty coffee chain",
    countries: "Japan · South Korea · Taiwan",
    color: "bg-amber-600",
    live: false,
  },
  {
    id: "indie-collective",
    name: "Indie Café Collective",
    description: "40+ independent cafés, one shared program",
    countries: "Canada · United Kingdom",
    color: "bg-sky-700",
    live: false,
  },
  {
    id: "harbor-pine",
    name: "Harbor & Pine",
    description: "Outdoor clothing",
    countries: "Australia · New Zealand",
    color: "bg-stone-700",
    live: false,
  },
];

export const CURRENT_PROGRAM = PROGRAMS[0];
