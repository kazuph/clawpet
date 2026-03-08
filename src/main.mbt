///|
fn main {
  log_ffi(string_to_utf8_ffi("ClawPet MoonBit server starting..."))
  // Ensure cache directory exists
  mkdir_p_ffi(string_to_utf8_ffi(cache_dir))
  // Initialize piper TTS
  log_ffi(string_to_utf8_ffi("Initializing piper TTS..."))
  piper_init_ffi()
  log_ffi(string_to_utf8_ffi("Piper TTS ready."))
  // Start TCP server
  let port = 8888
  let sfd = tcp_listen_ffi(port)
  if sfd < 0 {
    log_ffi(string_to_utf8_ffi("Failed to bind to port 8888"))
    return
  }
  log_ffi(
    string_to_utf8_ffi("ClawPet server running at http://127.0.0.1:8888"),
  )
  // Main accept loop
  while true {
    let cfd = accept_request_ffi(sfd)
    if cfd >= 0 {
      handle_request(cfd)
      close_conn_ffi(cfd)
    }
  }
}
