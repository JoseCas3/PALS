import { execFileSync } from "node:child_process";
import path from "node:path";

export default function globalTeardown() {
  const repositoryRoot = path.resolve(__dirname, "../../..");
  execFileSync(
    "docker",
    ["compose", "-p", "pals-e2e", "-f", "docker-compose.e2e.yml", "down", "--volumes", "--remove-orphans"],
    { cwd: repositoryRoot, stdio: "inherit" },
  );
}
