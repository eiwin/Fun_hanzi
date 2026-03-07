const http = require("node:http");
const fs = require("node:fs/promises");
const path = require("node:path");

const appDir = __dirname;
const dataDir = path.resolve(__dirname, "..", "data");

const routes = {
  "/api/rules": "session_rules.json",
  "/api/characters": "characters.json",
  "/api/progress": "progress.json",
  "/api/workflow-rules": "workflow_rules.json",
  "/api/current-week": "current_week.json",
};

const mimeTypes = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "text/javascript",
  ".json": "application/json",
};

async function readJson(name) {
  const filePath = path.join(dataDir, name);
  const content = await fs.readFile(filePath, "utf8");
  return JSON.parse(content);
}

async function writeJson(name, data) {
  const filePath = path.join(dataDir, name);
  const content = JSON.stringify(data, null, 2);
  await fs.writeFile(filePath, content);
}

function send(res, status, body, type = "text/plain") {
  res.writeHead(status, { "Content-Type": type });
  res.end(body);
}

async function serveStatic(req, res) {
  const urlPath = req.url === "/" ? "/index.html" : req.url;
  const filePath = path.join(appDir, urlPath);
  const ext = path.extname(filePath);

  try {
    const data = await fs.readFile(filePath);
    send(res, 200, data, mimeTypes[ext] || "application/octet-stream");
  } catch {
    send(res, 404, "Not found");
  }
}

async function serveApi(req, res) {
  const fileName = routes[req.url];
  if (!fileName) {
    send(res, 404, "Not found");
    return;
  }

  if (req.method === "GET") {
    const data = await readJson(fileName);
    send(res, 200, JSON.stringify(data), "application/json");
    return;
  }

  if (req.method === "POST") {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
    });
    req.on("end", async () => {
      try {
        const payload = JSON.parse(body || "{}");
        await writeJson(fileName, payload);
        send(res, 200, JSON.stringify({ ok: true }), "application/json");
      } catch {
        send(res, 400, "Invalid JSON");
      }
    });
    return;
  }

  send(res, 405, "Method not allowed");
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.url && req.url.startsWith("/api/")) {
      await serveApi(req, res);
      return;
    }
    await serveStatic(req, res);
  } catch {
    send(res, 500, "Server error");
  }
});

const PORT = 3000;
server.listen(PORT, () => {
  console.log(`Fun Hanzi running at http://localhost:${PORT}`);
});
