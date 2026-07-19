import { cpSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const standalone = join(root, ".next", "standalone");
const target = existsSync(join(standalone, "frontend")) ? join(standalone, "frontend") : standalone;
const staticSource = join(root, ".next", "static");
const publicSource = join(root, "public");

if (!existsSync(staticSource)) throw new Error(`Missing Next static output: ${staticSource}`);
mkdirSync(join(target, ".next"), { recursive: true });
cpSync(staticSource, join(target, ".next", "static"), { recursive: true });
if (existsSync(publicSource)) cpSync(publicSource, join(target, "public"), { recursive: true });
console.log(`Copied standalone assets into ${target}`);
