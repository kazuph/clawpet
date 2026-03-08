///|
extern "C" fn tcp_listen_ffi(port : Int) -> Int = "tcp_listen_ffi"

///|
extern "C" fn accept_request_ffi(sfd : Int) -> Int = "accept_request_ffi"

///|
extern "C" fn get_method_ffi() -> Int = "get_method_ffi"

///|
extern "C" fn get_path_ffi() -> Bytes = "get_path_ffi"

///|
extern "C" fn get_body_ffi() -> Bytes = "get_body_ffi"

///|
extern "C" fn send_response_ffi(
  fd : Int,
  status : Int,
  ct : Bytes,
  body : Bytes
) = "send_response_ffi"

///|
extern "C" fn close_conn_ffi(fd : Int) = "close_conn_ffi"

///|
extern "C" fn curl_post_ffi(url : Bytes, body : Bytes) -> Bytes = "curl_post_ffi"

///|
extern "C" fn piper_init_ffi() = "piper_init_ffi"

///|
extern "C" fn piper_synth_ffi(text : Bytes) -> Bytes = "piper_synth_ffi"

///|
extern "C" fn file_read_ffi(path : Bytes) -> Bytes = "file_read_ffi"

///|
extern "C" fn file_write_ffi(path : Bytes, data : Bytes) = "file_write_ffi"

///|
extern "C" fn file_exists_ffi(path : Bytes) -> Int = "file_exists_ffi"

///|
extern "C" fn file_delete_ffi(path : Bytes) = "file_delete_ffi"

///|
extern "C" fn env_get_ffi(name : Bytes) -> Bytes = "env_get_ffi"

///|
extern "C" fn random_hex_ffi(n : Int) -> Bytes = "random_hex_ffi"

///|
extern "C" fn mkdir_p_ffi(path : Bytes) = "mkdir_p_ffi"

///|
extern "C" fn log_ffi(msg : Bytes) = "log_ffi"

///|
/// Convert MoonBit String (UTF-16) to UTF-8 Bytes
extern "C" fn string_to_utf8_ffi(s : String) -> Bytes = "string_to_utf8_ffi"

///|
/// Convert UTF-8 Bytes to MoonBit String (UTF-16)
extern "C" fn utf8_to_string_ffi(b : Bytes) -> String = "utf8_to_string_ffi"

///|
/// Extract a JSON string value by key from UTF-8 JSON bytes
/// Returns empty Bytes if not found
extern "C" fn json_extract_ffi(data : Bytes, key : Bytes) -> Bytes = "json_extract_ffi"

///|
/// Extract all "text" values from Gemini response, concatenated
extern "C" fn gemini_extract_texts_ffi(data : Bytes) -> Bytes = "gemini_extract_texts_ffi"

///|
/// JSON-escape a UTF-8 string, returning UTF-8 bytes
extern "C" fn json_escape_ffi(data : Bytes) -> Bytes = "json_escape_ffi"

///|
/// Concatenate two Bytes
extern "C" fn bytes_concat_ffi(a : Bytes, b : Bytes) -> Bytes = "bytes_concat_ffi"
