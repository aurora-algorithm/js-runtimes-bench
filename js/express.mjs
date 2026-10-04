// The same Express app on every runtime. Run with PORT set, using one of:
//   node express.mjs | bun express.mjs | deno run -A express.mjs
import process from "node:process";
import express from "express";

const tags = ["a", "b"];
const app = express();

app.get("/users", (req, res) => {
  const list = [];
  for (let i = 0; i < 50; i++) {
    list.push({
      id: i, name: "User", email: "user@example.com",
      active: i % 2 === 0, tags,
    });
  }
  res.json(list);
});

app.listen(Number(process.env.PORT));
