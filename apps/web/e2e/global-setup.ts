import { execFileSync } from "node:child_process";
import path from "node:path";

export default function globalSetup() {
  const repositoryRoot = path.resolve(__dirname, "../../..");
  execFileSync(
    "docker",
    ["compose", "-p", "pals-e2e", "-f", "docker-compose.e2e.yml", "up", "-d", "--build", "--wait", "--force-recreate"],
    { cwd: repositoryRoot, stdio: "inherit" },
  );
}
