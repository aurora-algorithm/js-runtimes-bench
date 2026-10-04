// Bun's built-in server with Bun's built-in Postgres client (Bun.sql). Run: bun bun-sql.ts
import { SQL } from "bun";

const POOL_SIZE = 20;
const sql = new SQL({ url: process.env.DATABASE_URL, max: POOL_SIZE });
const randomStart = () => Math.floor(Math.random() * 9950);

// Open every connection up front, like the other servers' pre-filled pools.
await Promise.all(Array.from({ length: POOL_SIZE }, () => sql`SELECT 1`));

Bun.serve({
  port: 8097,
  routes: {
    "/users-db": async () => {
      const rows = await sql`
        SELECT id, name, email, active, tags FROM users
        WHERE id > ${randomStart()} ORDER BY id LIMIT 50`;
      return Response.json(rows);
    },
  },
  fetch: () => new Response(null, { status: 404 }),
});
