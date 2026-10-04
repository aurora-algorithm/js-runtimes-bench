// node-postgres (pg): the most-downloaded Postgres driver for JavaScript,
// used unchanged on every runtime.
import process from "node:process";
import pg from "pg";

const POOL_SIZE = 20;

export const pool = new pg.Pool({
  connectionString: process.env.DATABASE_URL,
  max: POOL_SIZE,
});
export const pageQuery =
  "SELECT id, name, email, active, tags FROM users " +
  "WHERE id > $1 ORDER BY id LIMIT 50";
export const randomStart = () => Math.floor(Math.random() * 9950);

// Open every connection up front, like the Rust server's pre-filled pool,
// so no run pays for connecting.
await Promise.all(
  Array.from({ length: POOL_SIZE }, () => pool.query("SELECT 1")),
);
