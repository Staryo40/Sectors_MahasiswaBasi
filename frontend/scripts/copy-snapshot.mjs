import { cp, mkdir, rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(frontendRoot, "..");
const sourceRoot = resolve(repositoryRoot, "data", "out");
const targetRoot = resolve(frontendRoot, "dist", "snapshots", "out");
const files = [
  "meta.json",
  "daily.json",
  "investor.json",
  "brief_daily.json",
  "brief_weekly.json",
];

await rm(targetRoot, { recursive: true, force: true });
await mkdir(targetRoot, { recursive: true });

for (const file of files)
  await cp(resolve(sourceRoot, file), resolve(targetRoot, file));

await cp(resolve(sourceRoot, "stocks"), resolve(targetRoot, "stocks"), {
  recursive: true,
});

console.log("Copied frozen market snapshot to dist/snapshots/out.");
