import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const years = process.env.YEARS
  ? process.env.YEARS.split(",").map(Number)
  : Array.from({ length: 11 }, (_, i) => 2015 + i);

const outDir = join(process.cwd(), "data", "raw", "xauusd");
mkdirSync(outDir, { recursive: true });

for (const year of years) {
  const from = `${year}-01-01`;
  const to = `${year + 1}-01-01`;
  for (const price of ["bid", "ask"]) {
    console.log(`Downloading XAUUSD M5 ${price}: ${from} -> ${to}`);
    execFileSync("npx", [
      "--yes", "dukascopy-node", "-i", "xauusd",
      "-from", from, "-to", to, "-t", "m5", "-f", "csv",
      "-p", price, "-v", "-dir", outDir
    ], { stdio: "inherit", shell: process.platform === "win32" });
  }
}
