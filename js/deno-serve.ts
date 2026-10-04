// Deno's built-in HTTP server. Run: deno run -A deno-serve.ts
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

Deno.serve({ port: 8093 }, async (req) => {
  const { pathname } = new URL(req.url);
  if (pathname === "/users") return Response.json(users());
  if (pathname === "/users-db") {
    const { rows } = await pool.query(
      pageQuery, [randomStart()],
    );
    return Response.json(rows);
  }
  return new Response(null, { status: 404 });
});
