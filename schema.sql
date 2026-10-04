CREATE TABLE users (
  id     INTEGER PRIMARY KEY,
  name   TEXT    NOT NULL,
  email  TEXT    NOT NULL,
  active BOOLEAN NOT NULL,
  tags   TEXT[]  NOT NULL
);
INSERT INTO users
SELECT i, 'User ' || i, 'user' || i || '@example.com', i % 2 = 0, ARRAY['a', 'b']
FROM generate_series(1, 10000) AS i;
ANALYZE users;
