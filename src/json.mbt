///|
/// Extract a string value for a given key from JSON body (UTF-8 Bytes)
fn json_extract_string(data : Bytes, key : String) -> String {
  let result_bytes = json_extract_ffi(data, string_to_utf8_ffi(key))
  if result_bytes.length() == 0 {
    return ""
  }
  utf8_to_string_ffi(result_bytes)
}

///|
/// Extract all text fields from Gemini API response
fn json_extract_gemini_texts(data : Bytes) -> String {
  let result_bytes = gemini_extract_texts_ffi(data)
  if result_bytes.length() == 0 {
    return ""
  }
  utf8_to_string_ffi(result_bytes)
}

///|
/// JSON-escape a string
fn json_escape(s : String) -> String {
  let escaped_bytes = json_escape_ffi(string_to_utf8_ffi(s))
  utf8_to_string_ffi(escaped_bytes)
}

///|
/// Build JSON response like {"response":"..."}
fn build_json_response(text : String) -> String {
  "{\"response\":\"" + json_escape(text) + "\"}"
}

///|
/// Build JSON response with model name like {"response":"...","model":"..."}
fn build_json_ask_response(text : String, model : String) -> String {
  "{\"response\":\"" +
  json_escape(text) +
  "\",\"model\":\"" +
  json_escape(model) +
  "\"}"
}

///|
/// Build JSON TTS URL response like {"url":"/tts-audio/xxx.wav"}
fn build_json_tts_url(fname : String) -> String {
  "{\"url\":\"/tts-audio/" + fname + "\"}"
}

///|
/// Build JSON error response like {"error":"..."}
fn build_json_error(msg : String) -> String {
  "{\"error\":\"" + json_escape(msg) + "\"}"
}

///|
/// Build Gemini API request body
fn build_gemini_request(sys_prompt : String, user_prompt : String) -> String {
  let full_prompt = "[指示]" +
    sys_prompt +
    "[/指示]\n\n" +
    user_prompt
  "{\"contents\":[{\"parts\":[{\"text\":\"" +
  json_escape(full_prompt) +
  "\"}]}],\"tools\":[{\"google_search\":{}}]}"
}

///|
/// Build Fireworks API (OpenAI-compatible) request body
fn build_fireworks_request(sys_prompt : String, user_prompt : String) -> String {
  "{\"model\":\"accounts/fireworks/models/kimi-k2p5\",\"messages\":[{\"role\":\"system\",\"content\":\"" +
  json_escape(sys_prompt) +
  "\"},{\"role\":\"user\",\"content\":\"" +
  json_escape(user_prompt) +
  "\"}],\"max_tokens\":200,\"reasoning_effort\":\"none\"}"
}
