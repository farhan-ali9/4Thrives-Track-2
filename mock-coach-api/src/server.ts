import { createServer } from "node:http";
import type { CoachRequest, CoachResponse } from "../../extension/src/shared/contracts.ts";
import { evaluateCoachRequest } from "../../extension/src/shared/mock-coach-engine.ts";

const PORT = 8787;
const HOST = "127.0.0.1";

const server = createServer(async (request, response) => {
  response.setHeader("Access-Control-Allow-Origin", "*");
  response.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  response.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (request.method === "OPTIONS") {
    response.writeHead(204);
    response.end();
    return;
  }

  if (request.method !== "POST" || request.url !== "/evaluate") {
    response.writeHead(404, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ error: "not_found" }));
    return;
  }

  const body = await readBody(request);
  const payload = JSON.parse(body) as CoachRequest;
  const result: CoachResponse = evaluateCoachRequest(payload);

  response.writeHead(200, { "Content-Type": "application/json" });
  response.end(JSON.stringify(result));
});

server.listen(PORT, HOST, () => {
  console.log(`Mock coach API listening on http://${HOST}:${PORT}`);
});

async function readBody(request: NodeJS.ReadableStream): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    chunks.push(typeof chunk === "string" ? Buffer.from(chunk) : chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}
