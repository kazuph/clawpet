#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <signal.h>
#include <time.h>
#include <curl/curl.h>

#include "moonbit.h"

/* ========== Helpers ========== */

/* Convert owned MoonBit Bytes to C null-terminated string. Caller frees result. Decrefs input. */
static char *bytes_to_cstr(moonbit_bytes_t b) {
    int32_t len = Moonbit_array_length(b);
    char *s = (char *)malloc(len + 1);
    memcpy(s, b, len);
    s[len] = '\0';
    moonbit_decref(b);
    return s;
}

/* Create MoonBit Bytes from C data */
static moonbit_bytes_t cdata_to_bytes(const void *data, int32_t len) {
    moonbit_bytes_t b = moonbit_make_bytes_raw(len);
    if (len > 0 && data) {
        memcpy(b, data, len);
    }
    return b;
}

/* Create MoonBit Bytes from C string */
static moonbit_bytes_t cstr_to_bytes(const char *s) {
    if (!s) return moonbit_make_bytes_raw(0);
    int32_t len = (int32_t)strlen(s);
    return cdata_to_bytes(s, len);
}

/* ========== UTF-8 <-> UTF-16 Conversion ========== */

MOONBIT_FFI_EXPORT
moonbit_bytes_t string_to_utf8_ffi(moonbit_string_t str) {
    int32_t str_len = Moonbit_array_length(str);

    /* First pass: calculate UTF-8 length */
    int32_t utf8_len = 0;
    for (int32_t i = 0; i < str_len; i++) {
        uint16_t ch = str[i];
        if (ch >= 0xD800 && ch <= 0xDBFF && i + 1 < str_len) {
            uint16_t lo = str[i + 1];
            if (lo >= 0xDC00 && lo <= 0xDFFF) {
                utf8_len += 4;
                i++;
                continue;
            }
        }
        if (ch < 0x80) utf8_len += 1;
        else if (ch < 0x800) utf8_len += 2;
        else utf8_len += 3;
    }

    moonbit_bytes_t result = moonbit_make_bytes_raw(utf8_len);
    int32_t pos = 0;
    for (int32_t i = 0; i < str_len; i++) {
        uint16_t ch = str[i];
        if (ch >= 0xD800 && ch <= 0xDBFF && i + 1 < str_len) {
            uint16_t lo = str[i + 1];
            if (lo >= 0xDC00 && lo <= 0xDFFF) {
                uint32_t cp = 0x10000 + ((uint32_t)(ch - 0xD800) << 10) + (lo - 0xDC00);
                result[pos++] = 0xF0 | ((cp >> 18) & 0x07);
                result[pos++] = 0x80 | ((cp >> 12) & 0x3F);
                result[pos++] = 0x80 | ((cp >> 6) & 0x3F);
                result[pos++] = 0x80 | (cp & 0x3F);
                i++;
                continue;
            }
        }
        if (ch < 0x80) {
            result[pos++] = (uint8_t)ch;
        } else if (ch < 0x800) {
            result[pos++] = 0xC0 | ((ch >> 6) & 0x1F);
            result[pos++] = 0x80 | (ch & 0x3F);
        } else {
            result[pos++] = 0xE0 | ((ch >> 12) & 0x0F);
            result[pos++] = 0x80 | ((ch >> 6) & 0x3F);
            result[pos++] = 0x80 | (ch & 0x3F);
        }
    }

    return result;
}

MOONBIT_FFI_EXPORT
moonbit_string_t utf8_to_string_ffi(moonbit_bytes_t b) {
    int32_t len = Moonbit_array_length(b);

    /* First pass: count UTF-16 code units */
    int32_t u16_len = 0;
    for (int32_t i = 0; i < len; ) {
        uint8_t c = b[i];
        if (c < 0x80) { u16_len++; i++; }
        else if (c < 0xE0) { u16_len++; i += 2; }
        else if (c < 0xF0) { u16_len++; i += 3; }
        else { u16_len += 2; i += 4; } /* surrogate pair */
    }

    moonbit_string_t result = moonbit_make_string_raw(u16_len);
    int32_t pos = 0;
    for (int32_t i = 0; i < len; ) {
        uint8_t c = b[i];
        if (c < 0x80) {
            result[pos++] = c;
            i++;
        } else if (c < 0xE0) {
            uint32_t cp = ((c & 0x1F) << 6) | (b[i+1] & 0x3F);
            result[pos++] = (uint16_t)cp;
            i += 2;
        } else if (c < 0xF0) {
            uint32_t cp = ((c & 0x0F) << 12) | ((b[i+1] & 0x3F) << 6) | (b[i+2] & 0x3F);
            result[pos++] = (uint16_t)cp;
            i += 3;
        } else {
            uint32_t cp = ((c & 0x07) << 18) | ((b[i+1] & 0x3F) << 12)
                        | ((b[i+2] & 0x3F) << 6) | (b[i+3] & 0x3F);
            /* Surrogate pair */
            uint16_t hi = (uint16_t)(((cp - 0x10000) >> 10) + 0xD800);
            uint16_t lo = (uint16_t)(((cp - 0x10000) & 0x3FF) + 0xDC00);
            result[pos++] = hi;
            result[pos++] = lo;
            i += 4;
        }
    }

    moonbit_decref(b);
    return result;
}

/* ========== JSON Helpers ========== */

/* Find "key":" pattern in data, extract value string (handling escapes).
   Returns malloc'd C string or NULL. */
static char *json_extract_cstr(const char *data, int data_len, const char *key) {
    int key_len = strlen(key);
    /* Search for "key": */
    for (int i = 0; i < data_len - key_len - 3; i++) {
        if (data[i] == '"' &&
            memcmp(data + i + 1, key, key_len) == 0 &&
            data[i + 1 + key_len] == '"' &&
            data[i + 2 + key_len] == ':') {

            int j = i + 3 + key_len;
            /* Skip whitespace */
            while (j < data_len && (data[j] == ' ' || data[j] == '\t')) j++;
            if (j >= data_len || data[j] != '"') continue;
            j++; /* skip opening quote */

            /* Extract value */
            char *buf = (char *)malloc(data_len);
            int buf_len = 0;
            while (j < data_len) {
                if (data[j] == '\\' && j + 1 < data_len) {
                    char next = data[j + 1];
                    if (next == '"') buf[buf_len++] = '"';
                    else if (next == '\\') buf[buf_len++] = '\\';
                    else if (next == 'n') buf[buf_len++] = '\n';
                    else if (next == 't') buf[buf_len++] = '\t';
                    else if (next == 'r') buf[buf_len++] = '\r';
                    else if (next == '/') buf[buf_len++] = '/';
                    else if (next == 'u') {
                        /* \uXXXX - pass through as-is for now */
                        buf[buf_len++] = '\\';
                        buf[buf_len++] = 'u';
                    }
                    else { buf[buf_len++] = '\\'; buf[buf_len++] = next; }
                    j += 2;
                } else if (data[j] == '"') {
                    break;
                } else {
                    buf[buf_len++] = data[j];
                    j++;
                }
            }
            buf[buf_len] = '\0';
            return buf;
        }
    }
    return NULL;
}

MOONBIT_FFI_EXPORT
moonbit_bytes_t json_extract_ffi(moonbit_bytes_t data, moonbit_bytes_t key) {
    int32_t data_len = Moonbit_array_length(data);
    char *key_s = bytes_to_cstr(key); /* decrefs key */

    char *result = json_extract_cstr((const char *)data, data_len, key_s);
    free(key_s);
    moonbit_decref(data);

    if (!result) return moonbit_make_bytes_raw(0);
    moonbit_bytes_t ret = cstr_to_bytes(result);
    free(result);
    return ret;
}

MOONBIT_FFI_EXPORT
moonbit_bytes_t gemini_extract_texts_ffi(moonbit_bytes_t data) {
    int32_t data_len = Moonbit_array_length(data);
    const char *d = (const char *)data;

    /* Find "parts" marker */
    const char *parts = NULL;
    for (int i = 0; i < data_len - 7; i++) {
        if (memcmp(d + i, "\"parts\"", 7) == 0) {
            parts = d + i + 7;
            break;
        }
    }

    if (!parts) {
        moonbit_decref(data);
        return moonbit_make_bytes_raw(0);
    }

    /* Collect all "text":"..." values after "parts" */
    char *result = (char *)malloc(data_len + 1);
    int result_len = 0;
    int offset = parts - d;

    for (int i = offset; i < data_len - 6; i++) {
        if (memcmp(d + i, "\"text\"", 6) == 0) {
            int j = i + 6;
            while (j < data_len && (d[j] == ' ' || d[j] == '\t')) j++;
            if (j < data_len && d[j] == ':') {
                j++;
                while (j < data_len && (d[j] == ' ' || d[j] == '\t')) j++;
                if (j < data_len && d[j] == '"') {
                    j++;
                    while (j < data_len) {
                        if (d[j] == '\\' && j + 1 < data_len) {
                            char next = d[j + 1];
                            if (next == '"') result[result_len++] = '"';
                            else if (next == '\\') result[result_len++] = '\\';
                            else if (next == 'n') result[result_len++] = '\n';
                            else if (next == 't') result[result_len++] = '\t';
                            else if (next == 'r') result[result_len++] = '\r';
                            else if (next == '/') result[result_len++] = '/';
                            else { result[result_len++] = '\\'; result[result_len++] = next; }
                            j += 2;
                        } else if (d[j] == '"') {
                            break;
                        } else {
                            result[result_len++] = d[j];
                            j++;
                        }
                    }
                    i = j; /* skip past this text value */
                }
            }
        }
    }

    moonbit_decref(data);
    result[result_len] = '\0';
    moonbit_bytes_t ret = cdata_to_bytes(result, result_len);
    free(result);
    return ret;
}

MOONBIT_FFI_EXPORT
moonbit_bytes_t json_escape_ffi(moonbit_bytes_t data) {
    int32_t len = Moonbit_array_length(data);
    /* Worst case: every byte needs escaping -> 2x */
    char *buf = (char *)malloc(len * 2 + 1);
    int buf_len = 0;

    for (int i = 0; i < len; i++) {
        uint8_t b = data[i];
        if (b == '"') { buf[buf_len++] = '\\'; buf[buf_len++] = '"'; }
        else if (b == '\\') { buf[buf_len++] = '\\'; buf[buf_len++] = '\\'; }
        else if (b == '\n') { buf[buf_len++] = '\\'; buf[buf_len++] = 'n'; }
        else if (b == '\r') { buf[buf_len++] = '\\'; buf[buf_len++] = 'r'; }
        else if (b == '\t') { buf[buf_len++] = '\\'; buf[buf_len++] = 't'; }
        else if (b < 0x20) { /* skip control chars */ }
        else { buf[buf_len++] = b; }
    }

    moonbit_decref(data);
    moonbit_bytes_t ret = cdata_to_bytes(buf, buf_len);
    free(buf);
    return ret;
}

MOONBIT_FFI_EXPORT
moonbit_bytes_t bytes_concat_ffi(moonbit_bytes_t a, moonbit_bytes_t b) {
    int32_t a_len = Moonbit_array_length(a);
    int32_t b_len = Moonbit_array_length(b);
    moonbit_bytes_t result = moonbit_make_bytes_raw(a_len + b_len);
    memcpy(result, a, a_len);
    memcpy(result + a_len, b, b_len);
    moonbit_decref(a);
    moonbit_decref(b);
    return result;
}

/* ========== HTTP Request State ========== */

static int g_method = 0;
static char g_path[4096];
static char *g_body = NULL;
static int g_body_len = 0;

/* ========== TCP Server ========== */

MOONBIT_FFI_EXPORT
int32_t tcp_listen_ffi(int32_t port) {
    int sfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sfd < 0) return -1;

    int opt = 1;
    setsockopt(sfd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = inet_addr("127.0.0.1");
    addr.sin_port = htons((uint16_t)port);

    if (bind(sfd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        fprintf(stderr, "bind failed: %s\n", strerror(errno));
        close(sfd);
        return -1;
    }
    if (listen(sfd, 128) < 0) {
        close(sfd);
        return -1;
    }
    return sfd;
}

static int parse_http_request(int cfd) {
    char buf[65536];
    int total = 0;

    int n = read(cfd, buf, sizeof(buf) - 1);
    if (n <= 0) return -1;
    total = n;
    buf[total] = '\0';

    if (strncmp(buf, "GET ", 4) == 0) {
        g_method = 0;
    } else if (strncmp(buf, "POST ", 5) == 0) {
        g_method = 1;
    } else {
        g_method = -1;
        return -1;
    }

    char *path_start = strchr(buf, ' ') + 1;
    char *path_end = strchr(path_start, ' ');
    if (!path_end) return -1;
    int path_len = path_end - path_start;
    if (path_len >= (int)sizeof(g_path)) path_len = sizeof(g_path) - 1;
    memcpy(g_path, path_start, path_len);
    g_path[path_len] = '\0';

    char *q = strchr(g_path, '?');
    if (q) *q = '\0';

    if (g_body) { free(g_body); g_body = NULL; }
    g_body_len = 0;

    if (g_method == 1) {
        int content_length = 0;
        char *cl = strcasestr(buf, "Content-Length:");
        if (cl) {
            content_length = atoi(cl + 15);
        }

        char *body_start = strstr(buf, "\r\n\r\n");
        if (body_start) {
            body_start += 4;
            int header_len = body_start - buf;
            int body_in_buf = total - header_len;

            if (content_length <= 0) content_length = body_in_buf;

            g_body = (char *)malloc(content_length + 1);
            memcpy(g_body, body_start, body_in_buf);
            g_body_len = body_in_buf;

            while (g_body_len < content_length) {
                n = read(cfd, g_body + g_body_len, content_length - g_body_len);
                if (n <= 0) break;
                g_body_len += n;
            }
            g_body[g_body_len] = '\0';
        }
    }

    return 0;
}

MOONBIT_FFI_EXPORT
int32_t accept_request_ffi(int32_t sfd) {
    struct sockaddr_in client_addr;
    socklen_t client_len = sizeof(client_addr);
    int cfd = accept(sfd, (struct sockaddr *)&client_addr, &client_len);
    if (cfd < 0) return -1;

    if (parse_http_request(cfd) < 0) {
        close(cfd);
        return -1;
    }
    return cfd;
}

MOONBIT_FFI_EXPORT
int32_t get_method_ffi(void) {
    return g_method;
}

MOONBIT_FFI_EXPORT
moonbit_bytes_t get_path_ffi(void) {
    return cstr_to_bytes(g_path);
}

MOONBIT_FFI_EXPORT
moonbit_bytes_t get_body_ffi(void) {
    if (g_body && g_body_len > 0) {
        return cdata_to_bytes(g_body, g_body_len);
    }
    return moonbit_make_bytes_raw(0);
}

MOONBIT_FFI_EXPORT
void send_response_ffi(int32_t fd, int32_t status, moonbit_bytes_t ct, moonbit_bytes_t body) {
    int32_t ct_len = Moonbit_array_length(ct);
    int32_t body_len = Moonbit_array_length(body);

    char header[1024];
    const char *status_text = "OK";
    if (status == 404) status_text = "Not Found";
    else if (status == 405) status_text = "Method Not Allowed";
    else if (status == 400) status_text = "Bad Request";
    else if (status == 500) status_text = "Internal Server Error";

    int hlen = snprintf(header, sizeof(header),
        "HTTP/1.1 %d %s\r\n"
        "Content-Type: %.*s\r\n"
        "Content-Length: %d\r\n"
        "Access-Control-Allow-Origin: *\r\n"
        "Connection: close\r\n"
        "\r\n",
        status, status_text,
        ct_len, (const char *)ct,
        body_len);

    write(fd, header, hlen);
    if (body_len > 0) {
        int written = 0;
        while (written < body_len) {
            int w = write(fd, (const char *)body + written, body_len - written);
            if (w <= 0) break;
            written += w;
        }
    }

    moonbit_decref(ct);
    moonbit_decref(body);
}

MOONBIT_FFI_EXPORT
void close_conn_ffi(int32_t fd) {
    close(fd);
}

/* ========== libcurl HTTPS POST ========== */

struct curl_buf {
    char *data;
    size_t len;
};

static size_t curl_write_cb(void *ptr, size_t size, size_t nmemb, void *userdata) {
    struct curl_buf *buf = (struct curl_buf *)userdata;
    size_t total = size * nmemb;
    buf->data = realloc(buf->data, buf->len + total);
    memcpy(buf->data + buf->len, ptr, total);
    buf->len += total;
    return total;
}

MOONBIT_FFI_EXPORT
moonbit_bytes_t curl_post_ffi(moonbit_bytes_t url, moonbit_bytes_t body) {
    char *url_s = bytes_to_cstr(url);
    char *body_s = bytes_to_cstr(body);

    CURL *curl = curl_easy_init();
    if (!curl) {
        free(url_s);
        free(body_s);
        return moonbit_make_bytes_raw(0);
    }

    struct curl_buf resp = { NULL, 0 };

    struct curl_slist *headers = NULL;
    headers = curl_slist_append(headers, "Content-Type: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, url_s);
    curl_easy_setopt(curl, CURLOPT_POST, 1L);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body_s);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, (long)strlen(body_s));
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &resp);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);
    curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);

    CURLcode res = curl_easy_perform(curl);
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    free(url_s);
    free(body_s);

    if (res != CURLE_OK) {
        fprintf(stderr, "curl error: %s\n", curl_easy_strerror(res));
        free(resp.data);
        return moonbit_make_bytes_raw(0);
    }

    moonbit_bytes_t result = cdata_to_bytes(resp.data, (int32_t)resp.len);
    free(resp.data);
    return result;
}

/* ========== Piper TTS ========== */

static int piper_stdin_fd = -1;
static int piper_stdout_fd = -1;
static pid_t piper_pid = -1;

MOONBIT_FFI_EXPORT
void piper_init_ffi(void) {
    /* Ignore SIGPIPE to prevent crash when piper process dies */
    signal(SIGPIPE, SIG_IGN);
    
    int pipe_in[2], pipe_out[2];
    if (pipe(pipe_in) < 0 || pipe(pipe_out) < 0) {
        fprintf(stderr, "pipe() failed\n");
        return;
    }

    pid_t pid = fork();
    if (pid < 0) {
        fprintf(stderr, "fork() failed\n");
        return;
    }

    if (pid == 0) {
        close(pipe_in[1]);
        close(pipe_out[0]);
        dup2(pipe_in[0], STDIN_FILENO);
        dup2(pipe_out[1], STDOUT_FILENO);
        close(pipe_in[0]);
        close(pipe_out[1]);

        /* Direct piper execution with library path */
        char *lib_path = "/data/data/com.termux/files/home/piper-tts/piper/lib:/data/data/com.termux/files/home/piper-tts/piper";
        setenv("LD_LIBRARY_PATH", lib_path, 1);
        setenv("OPENJTALK_DICT_DIR", "/data/data/com.termux/files/home/piper-tts/open_jtalk_dic/open_jtalk_dic_utf_8-1.11", 1);
        setenv("OPENJTALK_PHONEMIZER_PATH", "/data/data/com.termux/files/home/piper-tts/piper/bin/open_jtalk_phonemizer", 1);
        setenv("OMP_NUM_THREADS", "2", 1);
        setenv("OMP_WAIT_POLICY", "PASSIVE", 1);

        execlp("/data/data/com.termux/files/home/piper-tts/piper/piper", "piper",
            "-m", "/data/data/com.termux/files/home/piper-tts/models/tsukuyomi/tsukuyomi.onnx",
            "-c", "/data/data/com.termux/files/home/piper-tts/models/tsukuyomi/tsukuyomi.onnx.json",
            "-d", "/data/data/com.termux/files/usr/tmp/piper_out",
            "--sentence_silence", "0.1", "--length_scale", "1.0",
            (char *)NULL);
        _exit(127);
    }

    close(pipe_in[0]);
    close(pipe_out[1]);
    piper_stdin_fd = pipe_in[1];
    piper_stdout_fd = pipe_out[0];
    piper_pid = pid;

    mkdir("/data/data/com.termux/files/usr/tmp/piper_out", 0755);

    fprintf(stderr, "Piper warmup...\n");
    const char *warmup = "ウォームアップ\n";
    write(piper_stdin_fd, warmup, strlen(warmup));

    /* Read lines until we get one ending with .wav */
    char line[4096];
    while (1) {
        int pos = 0;
        while (pos < (int)sizeof(line) - 1) {
            int n = read(piper_stdout_fd, &line[pos], 1);
            if (n <= 0) goto warmup_done;
            if (line[pos] == '\n') break;
            pos++;
        }
        line[pos] = '\0';
        while (pos > 0 && (line[pos-1] == '\r' || line[pos-1] == ' ')) {
            line[--pos] = '\0';
        }
        fprintf(stderr, "Piper warmup done (file: %s)\n", line);
        if (pos >= 4 && strcmp(line + pos - 4, ".wav") == 0) {
            unlink(line);
            break;
        }
    }
warmup_done: ;
}

MOONBIT_FFI_EXPORT
moonbit_bytes_t piper_synth_ffi(moonbit_bytes_t text) {
    char *text_s = bytes_to_cstr(text);

    if (piper_stdin_fd < 0 || piper_stdout_fd < 0) {
        fprintf(stderr, "Piper not initialized\n");
        free(text_s);
        return moonbit_make_bytes_raw(0);
    }

    /* Replace newlines with spaces */
    for (char *p = text_s; *p; p++) {
        if (*p == '\n' || *p == '\r') *p = ' ';
    }

    int tlen = strlen(text_s);
    if (write(piper_stdin_fd, text_s, tlen) < 0 || write(piper_stdin_fd, "\n", 1) < 0) {
        fprintf(stderr, "Piper write failed (broken pipe)\n");
        free(text_s);
        return moonbit_make_bytes_raw(0);
    }
    free(text_s);

    /* Read lines from piper stdout until we get a .wav path */
    char line[4096];
    int found_wav = 0;
    while (!found_wav) {
        int pos = 0;
        while (pos < (int)sizeof(line) - 1) {
            int n = read(piper_stdout_fd, &line[pos], 1);
            if (n <= 0) {
                fprintf(stderr, "Piper process died\n");
                return moonbit_make_bytes_raw(0);
            }
            if (line[pos] == '\n') break;
            pos++;
        }
        line[pos] = '\0';
        while (pos > 0 && (line[pos-1] == '\r' || line[pos-1] == ' ')) {
            line[--pos] = '\0';
        }
        if (pos >= 4 && strcmp(line + pos - 4, ".wav") == 0) {
            found_wav = 1;
        }
    }

    fprintf(stderr, "Piper output file: %s\n", line);

    FILE *f = fopen(line, "rb");
    if (!f) {
        fprintf(stderr, "Cannot open piper output: %s\n", line);
        return moonbit_make_bytes_raw(0);
    }
    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);

    moonbit_bytes_t result = moonbit_make_bytes_raw((int32_t)fsize);
    fread(result, 1, fsize, f);
    fclose(f);

    unlink(line);
    return result;
}

/* ========== File I/O ========== */

MOONBIT_FFI_EXPORT
moonbit_bytes_t file_read_ffi(moonbit_bytes_t path) {
    char *path_s = bytes_to_cstr(path);
    FILE *f = fopen(path_s, "rb");
    free(path_s);
    if (!f) return moonbit_make_bytes_raw(0);

    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);

    moonbit_bytes_t result = moonbit_make_bytes_raw((int32_t)fsize);
    fread(result, 1, fsize, f);
    fclose(f);
    return result;
}

MOONBIT_FFI_EXPORT
void file_write_ffi(moonbit_bytes_t path, moonbit_bytes_t data) {
    char *path_s = bytes_to_cstr(path);
    int32_t data_len = Moonbit_array_length(data);

    FILE *f = fopen(path_s, "wb");
    free(path_s);
    if (f) {
        fwrite(data, 1, data_len, f);
        fclose(f);
    }
    moonbit_decref(data);
}

MOONBIT_FFI_EXPORT
int32_t file_exists_ffi(moonbit_bytes_t path) {
    char *path_s = bytes_to_cstr(path);
    int exists = (access(path_s, F_OK) == 0) ? 1 : 0;
    free(path_s);
    return exists;
}

MOONBIT_FFI_EXPORT
void file_delete_ffi(moonbit_bytes_t path) {
    char *path_s = bytes_to_cstr(path);
    unlink(path_s);
    free(path_s);
}

/* ========== Environment ========== */

MOONBIT_FFI_EXPORT
moonbit_bytes_t env_get_ffi(moonbit_bytes_t name) {
    char *name_s = bytes_to_cstr(name);
    const char *val = getenv(name_s);
    free(name_s);
    if (!val) return moonbit_make_bytes_raw(0);
    return cstr_to_bytes(val);
}

/* ========== Random ========== */

MOONBIT_FFI_EXPORT
moonbit_bytes_t random_hex_ffi(int32_t n) {
    static int seeded = 0;
    if (!seeded) {
        srand(time(NULL) ^ getpid());
        seeded = 1;
    }

    char *hex = (char *)malloc(2 * n + 1);
    for (int i = 0; i < n; i++) {
        int r = rand() & 0xFF;
        sprintf(hex + 2*i, "%02x", r);
    }
    hex[2*n] = '\0';

    moonbit_bytes_t result = cdata_to_bytes(hex, 2*n);
    free(hex);
    return result;
}

/* ========== Directory ========== */

MOONBIT_FFI_EXPORT
void mkdir_p_ffi(moonbit_bytes_t path) {
    char *path_s = bytes_to_cstr(path);
    char tmp[4096];
    snprintf(tmp, sizeof(tmp), "%s", path_s);
    size_t len = strlen(tmp);
    if (len > 0 && tmp[len-1] == '/') tmp[len-1] = '\0';

    for (char *p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            mkdir(tmp, 0755);
            *p = '/';
        }
    }
    mkdir(tmp, 0755);
    free(path_s);
}

/* ========== Logging ========== */

MOONBIT_FFI_EXPORT
void log_ffi(moonbit_bytes_t msg) {
    int32_t len = Moonbit_array_length(msg);
    fprintf(stderr, "%.*s\n", len, (const char *)msg);
    fflush(stderr);
    moonbit_decref(msg);
}
