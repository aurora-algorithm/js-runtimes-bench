// Bun's built-in HTTP server. Run: bun bun-serve.ts
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

Bun.serve({
  port: 8092,
  routes: {
    "/users": () => Response.json(users()),
    "/users-db": async () => {
      const { rows } = await pool.query(
        pageQuery, [randomStart()],
      );
      return Response.json(rows);
    },
  },
  fetch: () => new Response(null, { status: 404 }),
});
