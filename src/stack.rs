//! Stack headroom for upstream recursive work on unusually deep documents.
//!
//! Python worker stacks may be far smaller than Rust's main-thread stack. Keep
//! ordinary documents on the calling thread; deep trees run on a scoped worker
//! with enough virtual stack for both optimized and debug builds. No Python
//! references or GIL token may be captured by the detached operation.

use std::thread;

pub(crate) const DEEP_NODE_DEPTH: usize = 16;
pub(crate) const STACK_BYTES: usize = 64 * 1024 * 1024;

/// Conservative precheck, including inline CSS and escaped delimiters. False
/// positives only move parsing to a worker; CSS semantics stay with Takumi.
pub(crate) fn nested_css(source: &str) -> bool {
  source
    .bytes()
    .filter(|byte| matches!(byte, b'{' | b'(' | b'['))
    .take(8)
    .count()
    == 8
}

pub(crate) fn run<T, F>(deep: bool, operation: F) -> Result<T, String>
where
  T: Send,
  F: FnOnce() -> T + Send,
{
  if !deep {
    return Ok(operation());
  }
  thread::scope(|scope| {
    let worker = thread::Builder::new()
      .name("takumi-py-deep-document".to_owned())
      .stack_size(STACK_BYTES)
      .spawn_scoped(scope, operation)
      .map_err(|error| format!("failed to start deep-document worker: {error}"))?;
    worker
      .join()
      .map_err(|_| "deep-document worker panicked".to_owned())
  })
}
