import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const years = process.env.YEARS
  ? process.env.YEARS.split(",").map(Number)
  : Array.from({ length: 11 }, (_, i) => 2015 + i);

const outDir = join(process.cwd(), "data", "raw", "xauusd", "ticks");
mkdirSync(outDir, { recursive: true });

for (const year of years) {
  const from = `${year}-01-01`;
  const to = `${year + 1}-01-01`;
  console.log(`Downloading XAUUSD ticks: ${from} -> ${to}`);
  execFileSync("npx", [
    "--yes", "dukascopy-node", "-i", "xauusd",
    "-from", from, "-to", to, "-t", "tick", "-f", "csv",
    "-v", "-dir", outDir, "-fn", `xauusd-tick-${year}`
  ], { stdio: "inherit", shell: process.platform === "win32" });
}
