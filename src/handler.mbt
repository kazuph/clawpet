///|
let sys_prompt : String = "あなたは「クラッシュペット」という名前のたまごっち風キャラクターです。語尾は必ず「きゅぴ」にしてください。例:「そうだきゅぴ!」「わかったきゅぴ～」「教えるきゅぴ!」性格は明るく元気で、ユーザーのことが大好きです。ただし質問への回答は正確に行い、情報の質は落とさないでください。回答は音声で読み上げられるため、マークダウン記法は使わず、簡潔で自然な話し言葉で答えてください。回答は2〜3文以内で短くシンプルにしてください。長い説明は不要です。URLやリンクは絶対に含めないでください。出典や参照元の記載も不要です。情報だけを伝えてください。【重要】回答にアルファベットや英単語を絶対に使わないでください。全てカタカナで表記してください。例: API→エーピーアイ、Google→グーグル、iPhone→アイフォン、Python→パイソン、AI→エーアイ、OK→オーケー。数字はそのままで構いません。"

///|
let cache_dir : String = "/data/data/com.termux/files/home/claude-chat/cache/"

///|
let index_path : String = "/data/data/com.termux/files/home/claude-chat/index.html"

///|
/// Compare Bytes with a UTF-8 string
fn bytes_eq_str(b : Bytes, s : String) -> Bool {
  let s_bytes = string_to_utf8_ffi(s)
  let blen = b.length()
  let slen = s_bytes.length()
  if blen != slen {
    return false
  }
  let mut i = 0
  while i < blen {
    if b[i] != s_bytes[i] {
      return false
    }
    i = i + 1
  }
  true
}

///|
/// Check if Bytes starts with a UTF-8 string prefix
fn bytes_starts_with(b : Bytes, prefix : String) -> Bool {
  let p = string_to_utf8_ffi(prefix)
  let blen = b.length()
  let plen = p.length()
  if blen < plen {
    return false
  }
  let mut i = 0
  while i < plen {
    if b[i] != p[i] {
      return false
    }
    i = i + 1
  }
  true
}

///|
/// Extract substring from UTF-8 Bytes starting at byte offset, as a String
fn bytes_substr_to_string(b : Bytes, start : Int) -> String {
  let blen = b.length()
  if start >= blen {
    return ""
  }
  // Build an array of bytes for the substring
  let len = blen - start
  let arr : Array[Byte] = Array::new(capacity=len)
  let mut i = 0
  while i < len {
    arr.push(b[start + i])
    i = i + 1
  }
  let sub_bytes = Bytes::from_array(arr)
  utf8_to_string_ffi(sub_bytes)
}

///|
fn handle_request(fd : Int) -> Unit {
  let req_method = get_method_ffi()
  let path = get_path_ffi()
  if req_method == 0 {
    // GET
    handle_get(fd, path)
  } else if req_method == 1 {
    // POST
    let body = get_body_ffi()
    handle_post(fd, path, body)
  } else {
    send_text_response(fd, 405, "text/plain", "Method Not Allowed")
  }
}

///|
fn handle_get(fd : Int, path : Bytes) -> Unit {
  if bytes_eq_str(path, "/ping") {
    send_text_response(fd, 200, "text/plain", "pong")
  } else if bytes_starts_with(path, "/tts-audio/") {
    handle_tts_audio(fd, path)
  } else {
    // Serve index.html
    let html_bytes = file_read_ffi(string_to_utf8_ffi(index_path))
    if html_bytes.length() == 0 {
      send_text_response(fd, 500, "text/plain", "Failed to read index.html")
    } else {
      send_response_ffi(
        fd,
        200,
        string_to_utf8_ffi("text/html; charset=utf-8"),
        html_bytes,
      )
    }
  }
}

///|
fn handle_tts_audio(fd : Int, path : Bytes) -> Unit {
  // Extract filename after /tts-audio/  (11 bytes)
  let fname = bytes_substr_to_string(path, 11)
  let fpath = cache_dir + fname
  let fpath_bytes = string_to_utf8_ffi(fpath)
  if file_exists_ffi(fpath_bytes) != 0 {
    let wav_data = file_read_ffi(string_to_utf8_ffi(fpath))
    send_response_ffi(fd, 200, string_to_utf8_ffi("audio/wav"), wav_data)
    file_delete_ffi(string_to_utf8_ffi(fpath))
  } else {
    send_text_response(fd, 404, "text/plain", "Not Found")
  }
}

///|
fn handle_post(fd : Int, path : Bytes, body : Bytes) -> Unit {
  if bytes_eq_str(path, "/tts") {
    handle_tts(fd, body)
  } else if bytes_eq_str(path, "/ask") || bytes_eq_str(path, "/monologue") {
    handle_ask(fd, body)
  } else {
    send_text_response(fd, 404, "text/plain", "Not Found")
  }
}

///|
fn handle_ask(fd : Int, body : Bytes) -> Unit {
  let prompt = json_extract_string(body, "prompt")
  if prompt == "" {
    send_text_response(
      fd,
      400,
      "application/json",
      build_json_error("empty prompt"),
    )
    return
  }
  log_ffi(string_to_utf8_ffi("ASK: " + prompt))
  // Get API key
  let api_key_bytes = env_get_ffi(string_to_utf8_ffi("GEMINI_API_KEY"))
  let api_key = utf8_to_string_ffi(api_key_bytes)
  if api_key == "" {
    send_text_response(
      fd,
      500,
      "application/json",
      build_json_error("GEMINI_API_KEY not set"),
    )
    return
  }
  let url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" +
    api_key
  let req_body = build_gemini_request(sys_prompt, prompt)
  log_ffi(string_to_utf8_ffi("Calling Gemini API..."))
  let resp_bytes = curl_post_ffi(
    string_to_utf8_ffi(url),
    string_to_utf8_ffi(req_body),
  )
  if resp_bytes.length() == 0 {
    send_text_response(
      fd,
      500,
      "application/json",
      build_json_error("Gemini API call failed"),
    )
    return
  }
  let response_text = json_extract_gemini_texts(resp_bytes)
  let final_text = if response_text == "" {
    "(empty response)"
  } else {
    response_text
  }
  log_ffi(string_to_utf8_ffi("Gemini response: " + final_text))
  let json_resp = build_json_response(final_text)
  send_text_response(fd, 200, "application/json", json_resp)
}

///|
fn handle_tts(fd : Int, body : Bytes) -> Unit {
  let text = json_extract_string(body, "text")
  if text == "" {
    send_text_response(
      fd,
      500,
      "application/json",
      build_json_error("TTS failed: empty text"),
    )
    return
  }
  log_ffi(string_to_utf8_ffi("TTS: " + text))
  let wav_bytes = piper_synth_ffi(string_to_utf8_ffi(text))
  if wav_bytes.length() == 0 {
    send_text_response(
      fd,
      500,
      "application/json",
      build_json_error("TTS synthesis failed"),
    )
    return
  }
  // Save to cache
  let hex = random_hex_ffi(8)
  let fname = utf8_to_string_ffi(hex) + ".wav"
  let fpath = cache_dir + fname
  file_write_ffi(string_to_utf8_ffi(fpath), wav_bytes)
  let json_resp = build_json_tts_url(fname)
  send_text_response(fd, 200, "application/json", json_resp)
}

///|
fn send_text_response(
  fd : Int,
  status : Int,
  content_type : String,
  body : String
) -> Unit {
  send_response_ffi(
    fd,
    status,
    string_to_utf8_ffi(content_type),
    string_to_utf8_ffi(body),
  )
}
