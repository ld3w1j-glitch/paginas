from __future__ import annotations

import atexit
import difflib
import os
import re
import subprocess
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

_LOCK = threading.Lock()
_AI_PROCESS: subprocess.Popen | None = None
_AI_LOG = None
_AI_MODEL = ""


def _files(directory: Path, names: tuple[str, ...], pattern: str = "") -> list[Path]:
    if not directory.is_dir():
        return []
    found: list[Path] = []
    for name in names:
        found.extend(path for path in directory.rglob(name) if path.is_file())
    if pattern:
        found.extend(path for path in directory.rglob(pattern) if path.is_file())
    return sorted(set(found), key=lambda path: str(path).lower())


def discover_ai(directory: Path) -> dict:
    directory = directory.resolve()
    executables = _files(directory, ("llama-server.exe", "llama-server"))
    models = _files(directory, (), "*.gguf")
    return {
        "directory": str(directory),
        "executable_ready": bool(executables),
        "executable": str(executables[0]) if executables else "",
        "models": [
            {
                "name": str(path.relative_to(directory)),
                "file_name": path.name,
                "size_mb": round(path.stat().st_size / (1024 * 1024), 1),
            }
            for path in models
        ],
    }


def _local_health(url: str) -> bool:
    health_url = re.sub(r"/v1/chat/completions/?$", "/health", url.strip())
    if not health_url.startswith(("http://127.0.0.1", "http://localhost", "http://[::1]")):
        return False
    try:
        with urllib.request.urlopen(health_url, timeout=0.7) as response:
            return 200 <= response.status < 500
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return False


def ai_status(directory: Path, url: str) -> dict:
    global _AI_PROCESS
    discovery = discover_ai(directory)
    with _LOCK:
        managed_running = _AI_PROCESS is not None and _AI_PROCESS.poll() is None
        if _AI_PROCESS is not None and not managed_running:
            _AI_PROCESS = None
    responding = _local_health(url)
    return {
        **discovery,
        "running": managed_running or responding,
        "managed": managed_running,
        "responding": responding,
        "active_model": _AI_MODEL if managed_running else "",
    }


def _selected_model(directory: Path, requested: str) -> Path:
    models = _files(directory.resolve(), (), "*.gguf")
    if not models:
        raise ValueError("Nenhum modelo GGUF foi encontrado na pasta ia_local.")
    if requested:
        for path in models:
            if requested in {path.name, str(path.relative_to(directory.resolve()))}:
                return path
        raise ValueError("O modelo GGUF selecionado não foi encontrado.")
    return models[0]


def start_ai(directory: Path, requested_model: str, port: int = 8080) -> dict:
    global _AI_PROCESS, _AI_LOG, _AI_MODEL
    directory = directory.resolve()
    discovery = discover_ai(directory)
    if not discovery["executable_ready"]:
        raise ValueError("llama-server não foi encontrado na pasta ia_local.")
    model = _selected_model(directory, requested_model)
    with _LOCK:
        if _AI_PROCESS is not None and _AI_PROCESS.poll() is None:
            return {"started": False, "already_running": True, "model": _AI_MODEL}
        log_path = directory / "llama_server.log"
        _AI_LOG = log_path.open("a", encoding="utf-8")
        command = [
            discovery["executable"], "-m", str(model), "--host", "127.0.0.1",
            "--port", str(port), "-c", "4096", "-ngl", "20", "--threads", "6",
        ]
        kwargs = {
            "cwd": str(Path(discovery["executable"]).parent),
            "stdout": _AI_LOG,
            "stderr": subprocess.STDOUT,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            _AI_PROCESS = subprocess.Popen(command, **kwargs)
            _AI_MODEL = model.name
        except OSError:
            _AI_LOG.close()
            _AI_LOG = None
            _AI_PROCESS = None
            raise
    return {"started": True, "already_running": False, "model": model.name}


def stop_ai() -> dict:
    global _AI_PROCESS, _AI_LOG, _AI_MODEL
    with _LOCK:
        if _AI_PROCESS is None or _AI_PROCESS.poll() is not None:
            _AI_PROCESS = None
            return {"stopped": False, "managed": False}
        _AI_PROCESS.terminate()
        try:
            _AI_PROCESS.wait(timeout=6)
        except subprocess.TimeoutExpired:
            _AI_PROCESS.kill()
            _AI_PROCESS.wait(timeout=3)
        _AI_PROCESS = None
        _AI_MODEL = ""
        if _AI_LOG is not None:
            _AI_LOG.close()
            _AI_LOG = None
    return {"stopped": True, "managed": True}


def discover_voice(directory: Path) -> dict:
    directory = directory.resolve()
    executables = _files(directory, ("whisper-cli.exe", "main.exe", "whisper-cli", "main"))
    models = _files(directory, (), "ggml-*.bin")
    return {
        "directory": str(directory),
        "executable_ready": bool(executables),
        "executable": str(executables[0]) if executables else "",
        "models": [
            {
                "name": str(path.relative_to(directory)),
                "file_name": path.name,
                "size_mb": round(path.stat().st_size / (1024 * 1024), 1),
            }
            for path in models
        ],
        "ready": bool(executables and models),
    }


def transcribe_wav(directory: Path, wav_bytes: bytes, requested_model: str = "") -> str:
    directory = directory.resolve()
    discovery = discover_voice(directory)
    if not discovery["executable_ready"]:
        raise ValueError("whisper-cli não foi encontrado na pasta voz_local.")
    models = _files(directory, (), "ggml-*.bin")
    if not models:
        raise ValueError("Nenhum modelo Whisper foi encontrado na pasta voz_local.")
    model = next(
        (path for path in models if requested_model in {path.name, str(path.relative_to(directory))}),
        models[0],
    )
    if len(wav_bytes) < 44 or wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        raise ValueError("A gravação recebida não está em formato WAV válido.")
    if len(wav_bytes) > 16 * 1024 * 1024:
        raise ValueError("A gravação deve ter no máximo 16 MB.")
    with tempfile.TemporaryDirectory(prefix="english-study-voice-") as temp_name:
        temp = Path(temp_name)
        audio_path = temp / "speech.wav"
        output_base = temp / "transcript"
        audio_path.write_bytes(wav_bytes)
        command = [
            discovery["executable"], "-m", str(model), "-f", str(audio_path),
            "-l", "en", "-nt", "-otxt", "-of", str(output_base),
        ]
        result = subprocess.run(
            command,
            cwd=str(Path(discovery["executable"]).parent),
            capture_output=True,
            text=True,
            timeout=150,
            check=False,
        )
        transcript_path = output_base.with_suffix(".txt")
        if result.returncode != 0 or not transcript_path.is_file():
            detail = (result.stderr or result.stdout or "falha desconhecida").strip()[-1200:]
            raise RuntimeError(f"O Whisper local não conseguiu transcrever. {detail}")
        return re.sub(r"\s+", " ", transcript_path.read_text(encoding="utf-8", errors="replace")).strip()


def pronunciation_score(target: str, transcript: str) -> dict:
    def tokens(value: str) -> list[str]:
        return re.findall(r"[a-z0-9']+", value.lower())

    expected = tokens(target)
    heard = tokens(transcript)
    matcher = difflib.SequenceMatcher(a=expected, b=heard)
    missing: list[str] = []
    extra: list[str] = []
    matches: list[str] = []
    for tag, a1, a2, b1, b2 in matcher.get_opcodes():
        if tag == "equal":
            matches.extend(expected[a1:a2])
        elif tag == "delete":
            missing.extend(expected[a1:a2])
        elif tag == "insert":
            extra.extend(heard[b1:b2])
        elif tag == "replace":
            missing.extend(expected[a1:a2])
            extra.extend(heard[b1:b2])
    score = round(matcher.ratio() * 100) if expected else 0
    return {
        "score": score,
        "matched": matches,
        "missing": missing,
        "extra": extra,
        "target": target.strip(),
        "transcript": transcript.strip(),
    }


atexit.register(stop_ai)
