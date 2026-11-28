//! Fixed-origin Spider OSS fixture. No arbitrary URL or hosted API configuration.
use spider::{configuration::RedirectPolicy, website::Website};
use serde_json::json;
use std::time::Duration;

#[tokio::main]
async fn main() {
    let mut site = Website::new("http://127.0.0.1:18765/");
    site.with_respect_robots_txt(true)
        .with_subdomains(false)
        .with_limit(12)
        .with_depth(4)
        .with_delay(100)
        .with_user_agent(Some("ZEIBAEL-Fixture/0.1"))
        .with_redirect_policy(RedirectPolicy::None)
        .with_retry(0);
    let mut rx = site.subscribe(32);
    tokio::time::timeout(Duration::from_secs(30), site.crawl())
        .await.expect("fixture crawl timeout");
    site.unsubscribe();
    let mut records = Vec::new();
    while let Ok(page) = rx.try_recv() {
        records.push(json!({
            "url": page.get_url(),
            "status": page.status_code.as_u16(),
            "html": page.get_html()
        }));
    }
    records.sort_by(|a, b| a["url"].as_str().cmp(&b["url"].as_str()));
    println!("{}", serde_json::to_string(&records).expect("serialize fixture"));
}
