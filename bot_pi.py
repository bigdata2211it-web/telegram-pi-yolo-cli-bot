import json
import os
import re
import shlex
import signal
import subprocess
import threading
import time
from pathlib import Path

from bot_media import prompt_with_attachments
from bot_media import prompt_with_transcripts
from bot_media import transcribe_audio
from bot_state import append_history
from bot_state import clear_session_id
from bot_state import read_chat_workdir
from bot_state import read_session_id
from bot_state import read_stt_language
from bot_state import write_session_id


PI_SESSION_RE = re.compile(r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b", re.I)

state_lock = threading.Lock()
current_process = None
current_chat_id = None
current_started_at = None
current_task_cancelled = False


def command_config():
    command = os.environ.get("PI_COMMAND")
    if not command:
        return [
            "pi",
            "--mode",
            "json",
        ]
    return shlex.split(command)


def resume_command_config():
    command = os.environ.get("PI_RESUME_COMMAND")
    if not command:
        return [
            "pi",
            "--mode",
            "json",
        ]
    return shlex.split(command)


def add_files_to_command(cmd, file_paths):
    file_args = []
    for file_path in file_paths:
        file_args.append(f"@{Path(file_path).resolve()}")
    if not file_args:
        return cmd
    return cmd + file_args


def command_with_dir(cmd, workdir):
    cleaned = []
    skip_next = False
    for item in cmd:
        if skip_next:
            skip_next = False
            continue
        if item == "--dir":
            skip_next = True
            continue
        if item.startswith("--dir="):
            continue
        cleaned.append(item)
    return cleaned


def pi_session_command(session_id):
    cmd = resume_command_config()
    return cmd + ["--session", session_id]


def pi_resume_last_command():
    cmd = resume_command_config()
    return cmd + ["--continue"]


def assistant_message_text(message):
    if message.get("role") != "assistant":
        return ""
    texts = []
    for item in message.get("content") or []:
        if item.get("type") == "text" and item.get("text"):
            texts.append(item["text"])
    return "\n".join(texts).strip()


def extract_final_answer(output):
    text = (output or "").strip()
    if not text:
        return ""
    deltas = []
    parts = {}
    errors = []
    plain = []
    assistant_messages = []
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            plain.append(line)
            continue
        properties = event.get("properties") or {}
        message = event.get("message") or {}
        if event.get("type") in {"message", "message_end", "turn_end"}:
            response = assistant_message_text(message)
            if response:
                assistant_messages.append(response)
            continue
        if event.get("type") == "agent_end":
            for item in event.get("messages") or []:
                response = assistant_message_text(item)
                if response:
                    assistant_messages.append(response)
            continue
        if event.get("type") == "text":
            part = event.get("part") or {}
            if part.get("type") == "text" and part.get("text"):
                parts[part.get("id", str(len(parts)))] = part["text"]
            continue
        if event.get("type") == "message.part.delta" and properties.get("field") == "text":
            deltas.append(properties.get("delta", ""))
            continue
        if event.get("type") == "message.part.updated":
            part = properties.get("part") or {}
            if part.get("type") == "text" and part.get("text"):
                parts[part.get("id", str(len(parts)))] = part["text"]
            continue
        error = event.get("error") or properties.get("error")
        if error:
            message = (error.get("data") or {}).get("message") if isinstance(error, dict) else str(error)
            errors.append(message or str(error))
    if deltas:
        return "".join(deltas).strip()
    if assistant_messages:
        return assistant_messages[-1]
    if parts:
        return "\n".join(parts.values()).strip()
    if errors:
        return "\n".join(errors).strip()
    return "\n".join(plain).strip()


def parse_session_id(output):
    for line in (output or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "session" and event.get("id"):
            return event["id"]
    match = PI_SESSION_RE.search(output or "")
    return match.group(1) if match else ""


def valid_session_id(session_id):
    return bool(PI_SESSION_RE.fullmatch(session_id or ""))


def pi_timeout():
    return int(os.environ.get("PI_TIMEOUT_SECONDS", "1800"))


def popen_kwargs():
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def stop_process(process):
    if os.name == "nt":
        process.terminate()
        return
    os.killpg(process.pid, signal.SIGTERM)


def force_stop_process(process):
    if os.name == "nt":
        process.kill()
        return
    os.killpg(process.pid, signal.SIGKILL)


def format_duration(started_at):
    if not started_at:
        return "0s"
    seconds = int(time.time() - started_at)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def current_task_status():
    with state_lock:
        return current_started_at is not None, current_started_at


def has_running_task():
    with state_lock:
        return current_started_at is not None


def stop_current_task():
    global current_task_cancelled

    with state_lock:
        process = current_process
        had_task = current_started_at is not None
        if had_task:
            current_task_cancelled = True
    if process is None or process.poll() is not None:
        return had_task
    stop_process(process)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        force_stop_process(process)
    return True


def task_was_cancelled():
    with state_lock:
        return current_task_cancelled


def transcribe_voice_attachments(chat_id, attachments):
    language = read_stt_language(chat_id)
    transcripts = []
    rest = []
    for item in attachments:
        if item["kind"] not in {"voice", "audio"}:
            rest.append(item)
            continue
        payload = transcribe_audio(item["path"], language, pi_timeout())
        text = payload.get("text", "").strip()
        detected = payload.get("language", language)
        probability = payload.get("language_probability")
        transcripts.append(
            {
                "path": item["path"],
                "text": text,
                "language": detected,
                "language_probability": probability,
            }
        )
    return transcripts, rest


def run_pi(chat_id, prompt, attachments, send_message, t):
    global current_process, current_chat_id, current_started_at, current_task_cancelled

    with state_lock:
        if current_started_at is not None:
            send_message(chat_id, t(chat_id, "already_running"))
            return
        current_chat_id = chat_id
        current_started_at = time.time()
        current_task_cancelled = False

    attachments = attachments or []
    try:
        voice_items = [item for item in attachments if item["kind"] in {"voice", "audio"}]
        if voice_items:
            send_message(chat_id, t(chat_id, "transcribing", language=read_stt_language(chat_id)))
        transcripts, attachments = transcribe_voice_attachments(chat_id, attachments)
        prompt = prompt_with_transcripts(prompt, transcripts)
    except Exception as exc:
        if not task_was_cancelled():
            send_message(chat_id, t(chat_id, "transcribe_failed", error=exc))
        with state_lock:
            current_process = None
            current_chat_id = None
            current_started_at = None
            current_task_cancelled = False
        return

    if task_was_cancelled():
        with state_lock:
            current_process = None
            current_chat_id = None
            current_started_at = None
            current_task_cancelled = False
        return

    prompt = prompt_with_attachments(prompt, attachments)
    append_history(chat_id, "user", prompt)
    session_id = read_session_id(chat_id)
    if session_id and not valid_session_id(session_id):
        clear_session_id(chat_id)
        session_id = ""
    send_message(chat_id, t(chat_id, "continuing" if session_id else "starting"))
    workdir = read_chat_workdir(chat_id)
    cmd = pi_session_command(session_id) if session_id else command_config()
    cmd = command_with_dir(cmd, workdir)
    file_paths = [item["path"] for item in attachments]
    cmd = cmd + [prompt]
    cmd = add_files_to_command(cmd, file_paths)
    timeout = pi_timeout()

    try:
        process = subprocess.Popen(
            cmd,
            cwd=workdir,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            **popen_kwargs(),
        )
        with state_lock:
            current_process = process
        try:
            output, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop_process(process)
            output, _ = process.communicate(timeout=15)
            if not task_was_cancelled():
                send_message(chat_id, t(chat_id, "timeout", timeout=timeout, output=output[-3000:]))
            return

        if task_was_cancelled():
            return
        if process.returncode == 0:
            write_session_id(chat_id, parse_session_id(output))
            response = extract_final_answer(output) or t(chat_id, "empty_output")
            append_history(chat_id, "assistant", response)
            send_message(chat_id, response)
        else:
            send_message(chat_id, t(chat_id, "pi_exit", code=process.returncode, output=output[-3500:]))
    except Exception as exc:
        send_message(chat_id, t(chat_id, "bot_error", error=exc))
    finally:
        with state_lock:
            current_process = None
            current_chat_id = None
            current_started_at = None
            current_task_cancelled = False
