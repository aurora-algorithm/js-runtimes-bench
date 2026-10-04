use axum::{extract::State, http::StatusCode, routing::get, Json, Router};
use deadpool_postgres::{Manager, ManagerConfig, Pool, RecyclingMethod};
use serde::Serialize;
use sqlx::postgres::{PgPool, PgPoolOptions};

const POOL_SIZE: usize = 20;

#[derive(Clone)]
struct Pools {
    sqlx: PgPool,
    pg: Pool,
}

const PAGE_QUERY: &str = "SELECT id, name, email, active, tags FROM users WHERE id > $1 ORDER BY id LIMIT 50";

#[derive(Serialize, sqlx::FromRow)]
struct User {
    id: i32,
    name: String,
    email: String,
    active: bool,
    tags: Vec<String>,
}

// Borrowed static data (string literals and one shared tags slice): no per-user allocations, like the JS servers.
#[derive(Serialize)]
struct StaticUser {
    id: i32,
    name: &'static str,
    email: &'static str,
    active: bool,
    tags: &'static [&'static str],
}

async fn users() -> Json<Vec<StaticUser>> {
    let list = (0..50)
        .map(|i| StaticUser {
            id: i,
            name: "User",
            email: "user@example.com",
            active: i % 2 == 0,
            tags: &["a", "b"],
        })
        .collect();
    Json(list)
}

type ApiResult = Result<Json<Vec<User>>, (StatusCode, String)>;

fn internal(e: impl std::fmt::Display) -> (StatusCode, String) {
    (StatusCode::INTERNAL_SERVER_ERROR, e.to_string())
}

async fn users_db(State(pools): State<Pools>) -> ApiResult {
    sqlx::query_as::<_, User>(PAGE_QUERY)
        .bind(fastrand::i32(0..9950))
        .fetch_all(&pools.sqlx)
        .await
        .map(Json)
        .map_err(internal)
}

async fn users_pg(State(pools): State<Pools>) -> ApiResult {
    let client = pools.pg.get().await.map_err(internal)?;
    let stmt = client
        .prepare_cached(PAGE_QUERY)
        .await
        .map_err(internal)?;
    let rows = client
        .query(&stmt, &[&fastrand::i32(0..9950)])
        .await
        .map_err(internal)?;
    let list = rows
        .iter()
        .map(|r| User {
            id: r.get(0),
            name: r.get(1),
            email: r.get(2),
            active: r.get(3),
            tags: r.get(4),
        })
        .collect();
    Ok(Json(list))
}

fn main() {
    // RUNTIME=current_thread runs everything on one thread with Tokio's single-threaded scheduler; otherwise
    // the default multi-threaded scheduler is used (TOKIO_WORKER_THREADS caps its worker count).
    let mut builder = match std::env::var("RUNTIME").as_deref() {
        Ok("current_thread") => tokio::runtime::Builder::new_current_thread(),
        _ => tokio::runtime::Builder::new_multi_thread(),
    };
    builder.enable_all().build().expect("could not start the Tokio runtime").block_on(serve());
}

async fn serve() {
    let url = std::env::var("DATABASE_URL").expect("DATABASE_URL must be set");
    let sqlx = PgPoolOptions::new()
        .max_connections(POOL_SIZE as u32)
        .min_connections(POOL_SIZE as u32)
        .test_before_acquire(false)
        .connect(&url)
        .await
        .expect("could not connect to Postgres");
    let manager = Manager::from_config(
        url.parse().expect("invalid DATABASE_URL"),
        tokio_postgres::NoTls,
        ManagerConfig { recycling_method: RecyclingMethod::Fast },
    );
    let pg = Pool::builder(manager).max_size(POOL_SIZE).build().expect("could not build pool");
    // deadpool has no minimum size; open all connections now so it starts as warm as the sqlx pool.
    let warm: Vec<_> = futures::future::join_all((0..POOL_SIZE).map(|_| pg.get()))
        .await
        .into_iter()
        .collect::<Result<_, _>>()
        .expect("could not pre-fill the tokio-postgres pool");
    drop(warm);
    let app = Router::new()
        .route("/users", get(users))
        .route("/users-db", get(users_db))
        .route("/users-pg", get(users_pg))
        .with_state(Pools { sqlx, pg });
    let listener = tokio::net::TcpListener::bind("127.0.0.1:8082").await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
