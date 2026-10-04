// Node's built-in HTTP server. Run: node node-http.mjs
import http from "node:http";
import { pool, pageQuery, randomStart } from "./db.mjs";

const tags = ["a", "b"];

function users() {
  const list = [];
  for (let i = 0; i < 50; i++) {
    list.push({
      id: i, name: "User", email: "user@example.com",
      active: i % 2 === 0, tags,
    });
  }
  return list;
}

function send(res, value) {
  const body = JSON.stringify(value);
  res.writeHead(200, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(body),
  });
  res.end(body);
}

http
  .createServer(async (req, res) => {
    if (req.url === "/users") return send(res, users());
    if (req.url === "/users-db") {
      const { rows } = await pool.query(
        pageQuery, [randomStart()],
      );
      return send(res, rows);
    }
    res.writeHead(404).end();
  })
  .listen(8091);
